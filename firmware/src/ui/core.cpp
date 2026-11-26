// UI core: input device, gestures, navigation stack, transitions, snapshots,
// clock, sleep. Shared by the device and the simulator.
#include <cmath>

#include "ui/platform.h"
#include "ui/ui.h"

namespace ui {

static Platform* g_platform = nullptr;
void setPlatform(Platform* p) { g_platform = p; }
Platform& platform() { return *g_platform; }

namespace {

struct NavEntry {
    std::string screen;
    int scrollY = 0;
};

struct State {
    lv_display_t* disp = nullptr;
    lv_indev_t* indev = nullptr;
    lv_obj_t* stage = nullptr;
    lv_obj_t* page = nullptr;      // current page (child of stage)
    lv_obj_t* outgoing = nullptr;  // page being animated away
    std::vector<NavEntry> stack;
    svc::Pack pack;
    svc::Timeline timeline;
    svc::GameClock clock;
    svc::ClockNames names;
    int statusBarPx = 0;
    bool transition = false;
    Fit fit = Fit::Width;

    // gestures
    bool pressed = false;
    int16_t startX = 0, startY = 0, lastX = 0, lastY = 0;
    uint32_t pressStart = 0;
    bool swallow = false;  // current press is not delivered to LVGL
    bool menuTriggered = false;

    // sleep
    uint32_t lastActivity = 0;
    bool asleep = false;
    uint32_t sleepMs = 0;
    uint8_t brightness = 255;

    // run_sequence
    lv_timer_t* seqTimer = nullptr;
    std::vector<std::pair<std::string, uint32_t>> seqSteps;
    size_t seqIndex = 0;
    size_t seqBaseDepth = 0;
    std::string seqEnd;
};

State& S() {
    static State s;
    return s;
}

constexpr int kEdgePx = 10;            // edge-swipe start zone
constexpr int kSwipeMinPx = 50;        // minimum travel for an edge swipe
constexpr uint32_t kMenuHoldMs = 3000; // hold status bar this long for the hidden menu
constexpr int kHoldSlopPx = 12;

std::string appOf(const std::string& screen) {
    auto p = screen.find('/');
    return p == std::string::npos ? screen : screen.substr(0, p);
}

// ------------------------------------------------------------------ input

void indevRead(lv_indev_t*, lv_indev_data_t* data) {
    State& s = S();
    int16_t x = 0, y = 0;
    bool down = platform().readPointer(x, y);
    uint32_t now = lv_tick_get();
    data->point.x = down ? x : s.lastX;
    data->point.y = down ? y : s.lastY;
    data->state = LV_INDEV_STATE_RELEASED;

    if (down) s.lastActivity = now;
    if (s.asleep) {
        // First touch only wakes the screen.
        if (down) {
            s.asleep = false;
            platform().setBacklight(s.brightness);
            s.swallow = true;
            s.pressed = true;
        }
        return;
    }

    if (down && !s.pressed) {
        s.pressed = true;
        s.startX = x;
        s.startY = y;
        s.pressStart = now;
        s.menuTriggered = false;
        // Edge zones are reserved for the back/home gestures (controller buttons
        // have no on-screen equivalent; see DEVIATIONS.md).
        s.swallow = !hiddenMenuOpen() && (x < kEdgePx || y >= kScreenH - kEdgePx);
    }
    if (down) {
        s.lastX = x;
        s.lastY = y;
        int sbZone = s.statusBarPx > 0 ? s.statusBarPx : 24;
        if (!s.menuTriggered && !hiddenMenuOpen() && s.startY < sbZone &&
            std::abs(x - s.startX) < kHoldSlopPx && std::abs(y - s.startY) < kHoldSlopPx &&
            now - s.pressStart >= kMenuHoldMs) {
            s.menuTriggered = true;
            s.swallow = true;
            openHiddenMenu();
        }
    }
    if (!down && s.pressed) {
        s.pressed = false;
        if (s.swallow && !s.menuTriggered && !s.transition) {
            int dx = s.lastX - s.startX, dy = s.lastY - s.startY;
            if (s.startX < kEdgePx && dx > kSwipeMinPx && std::abs(dy) < dx) back();
            else if (s.startY >= kScreenH - kEdgePx && -dy > kSwipeMinPx && std::abs(dx) < -dy) home();
        }
        s.swallow = false;
        return;
    }
    if (down && !s.swallow && !s.transition) data->state = LV_INDEV_STATE_PRESSED;
}

// ------------------------------------------------------------------ transitions

struct Bezier {
    float x1 = 0, y1 = 0, x2 = 1, y2 = 1;
};

float bezierAt(float a, float b, float t) {
    float u = 1 - t;
    return 3 * u * u * t * a + 3 * u * t * t * b + t * t * t;
}

// Solve the x(t) = progress for t, return y(t). CSS cubic-bezier semantics.
float cubicBezier(const Bezier& bz, float x) {
    float lo = 0, hi = 1, t = x;
    for (int i = 0; i < 24; ++i) {
        float cx = bezierAt(bz.x1, bz.x2, t);
        if (std::fabs(cx - x) < 1e-4f) break;
        if (cx < x) lo = t;
        else hi = t;
        t = (lo + hi) / 2;
    }
    return bezierAt(bz.y1, bz.y2, t);
}

struct TransAnim {
    Bezier bz;
    std::string type;
    lv_obj_t* in = nullptr;
    lv_obj_t* out = nullptr;
};

int32_t pathBezier(const lv_anim_t* a) {
    auto* t = static_cast<TransAnim*>(lv_anim_get_user_data(a));
    float p = a->duration ? static_cast<float>(a->act_time) / static_cast<float>(a->duration) : 1.0f;
    if (p < 0) p = 0;
    if (p > 1) p = 1;
    float v = cubicBezier(t->bz, p);
    return a->start_value + static_cast<int32_t>(std::lround(v * (a->end_value - a->start_value)));
}

// Animated value v runs 0..1024.
void transStep(void* var, int32_t v) {
    auto* t = static_cast<TransAnim*>(var);
    const std::string& ty = t->type;
    int W = kScreenW, H = kScreenH;
    auto lerp = [](int a, int b, int32_t v) { return a + (b - a) * v / 1024; };
    if (ty == "fade_in") lv_obj_set_style_opa(t->in, static_cast<lv_opa_t>(lerp(0, 255, v)), 0);
    else if (ty == "fade_out" && t->out) lv_obj_set_style_opa(t->out, static_cast<lv_opa_t>(lerp(255, 0, v)), 0);
    else if (ty == "slide_left") {
        lv_obj_set_x(t->in, lerp(W, 0, v));
        if (t->out) lv_obj_set_x(t->out, lerp(0, -W, v));
    } else if (ty == "slide_right") {
        lv_obj_set_x(t->in, lerp(-W, 0, v));
        if (t->out) lv_obj_set_x(t->out, lerp(0, W, v));
    } else if (ty == "slide_up") {
        lv_obj_set_y(t->in, lerp(H, 0, v));
        if (t->out) lv_obj_set_y(t->out, lerp(0, -H, v));
    } else if (ty == "slide_down") {
        lv_obj_set_y(t->in, lerp(-H, 0, v));
        if (t->out) lv_obj_set_y(t->out, lerp(0, H, v));
    } else if (ty == "cover_up") lv_obj_set_y(t->in, lerp(H, 0, v));
    else if (ty == "cover_left") lv_obj_set_x(t->in, lerp(W, 0, v));
    else if (ty == "uncover_down" && t->out) lv_obj_set_y(t->out, lerp(0, H, v));
    else if (ty == "uncover_right" && t->out) lv_obj_set_x(t->out, lerp(0, W, v));
}

void transDone(lv_anim_t* a) {
    auto* t = static_cast<TransAnim*>(lv_anim_get_user_data(a));
    if (t->out) lv_obj_delete(t->out);
    lv_obj_set_pos(t->in, 0, 0);
    lv_obj_set_style_opa(t->in, LV_OPA_COVER, 0);
    S().outgoing = nullptr;
    S().transition = false;
    delete t;
}

void startTransition(lv_obj_t* in, lv_obj_t* out, JsonObjectConst spec) {
    State& s = S();
    std::string type = spec["type"] | "none";
    uint32_t ms = spec["ms"] | 0;
    if (type == "none" || ms == 0) {
        if (out) lv_obj_delete(out);
        return;
    }
    auto* t = new TransAnim();
    t->type = type;
    t->in = in;
    t->out = out;
    JsonArrayConst bz = spec["bezier"];
    if (bz.size() == 4) t->bz = Bezier{bz[0].as<float>(), bz[1].as<float>(), bz[2].as<float>(), bz[3].as<float>()};
    // Pages that are covered/uncovered must be stacked correctly.
    if (type.rfind("uncover", 0) == 0 || type == "fade_out") {
        if (out) lv_obj_move_foreground(out);
    } else {
        lv_obj_move_foreground(in);
    }
    s.transition = true;
    s.outgoing = out;
    transStep(t, 0);
    lv_anim_t a;
    lv_anim_init(&a);
    lv_anim_set_var(&a, t);
    lv_anim_set_user_data(&a, t);
    lv_anim_set_values(&a, 0, 1024);
    lv_anim_set_duration(&a, ms);
    lv_anim_set_exec_cb(&a, transStep);
    lv_anim_set_path_cb(&a, pathBezier);
    lv_anim_set_completed_cb(&a, transDone);
    lv_anim_start(&a);
}

const char* kindName(NavKind k) {
    switch (k) {
        case NavKind::OpenApp: return "open_app";
        case NavKind::Push: return "push";
        case NavKind::Pop: return "pop";
        case NavKind::CloseApp: return "close_app";
        default: return "";
    }
}

lv_obj_t* newPage() {
    lv_obj_t* p = lv_obj_create(S().stage);
    lv_obj_remove_style_all(p);
    lv_obj_remove_flag(p, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_remove_flag(p, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_set_pos(p, 0, 0);
    lv_obj_set_size(p, kScreenW, kScreenH);
    return p;
}

lv_obj_t* findBody(lv_obj_t* page) {
    // The body region is the first scrollable direct child (or nested canvas child).
    if (!page) return nullptr;
    uint32_t n = lv_obj_get_child_count(page);
    for (uint32_t i = 0; i < n; ++i) {
        lv_obj_t* c = lv_obj_get_child(page, i);
        if (lv_obj_has_flag(c, LV_OBJ_FLAG_SCROLLABLE)) return c;
        if (lv_obj_t* d = findBody(c)) return d;
    }
    return nullptr;
}

// Builds screenId into a fresh page and makes it current, with the transition for kind.
bool show(const std::string& screenId, NavKind kind, JsonObjectConst override, int restoreScroll) {
    State& s = S();
    detail::videoStopAll();
    lv_obj_t* page = newPage();
    std::string err;
    int sb = 0;
    if (!detail::buildScreen(screenId, page, err, sb)) {
        lv_obj_delete(page);
        platform().log(err);
        return false;
    }
    if (restoreScroll > 0) {
        if (lv_obj_t* body = findBody(page)) {
            lv_obj_update_layout(page);
            lv_obj_scroll_to_y(body, restoreScroll, LV_ANIM_OFF);
        }
    }
    lv_obj_t* old = s.page;
    if (s.outgoing) {  // a previous transition is still running: finish it now
        lv_anim_delete_all();
        s.transition = false;
    }
    s.page = page;
    s.statusBarPx = sb;
    JsonObjectConst spec = override.isNull() ? s.pack.manifest()["transitions"][kindName(kind)].as<JsonObjectConst>() : override;
    if (old && !spec.isNull() && kind != NavKind::None) startTransition(page, old, spec);
    else if (old) lv_obj_delete(old);
    platform().log("screen " + screenId);
    return true;
}

int currentScroll() {
    lv_obj_t* body = findBody(S().page);
    return body ? lv_obj_get_scroll_y(body) : 0;
}

// ------------------------------------------------------------------ timers

void clockTimer(lv_timer_t*) { detail::refreshClockLabels(); }

void seqTimerCb(lv_timer_t*) {
    State& s = S();
    if (s.seqIndex < s.seqSteps.size()) {
        auto& st = s.seqSteps[s.seqIndex++];
        openScreen(st.first, NavKind::Push);
        lv_timer_set_period(s.seqTimer, st.second ? st.second : 1);
        return;
    }
    lv_timer_delete(s.seqTimer);
    s.seqTimer = nullptr;
    if (s.seqEnd != "stay") {
        // Return to the screen the flow started from.
        while (s.stack.size() > s.seqBaseDepth + 1) s.stack.pop_back();
        NavEntry e = s.stack.back();
        s.stack.pop_back();
        s.stack.push_back(e);
        show(e.screen, NavKind::Pop, JsonObjectConst(), e.scrollY);
    }
}

void loadClockFromManifest() {
    State& s = S();
    JsonObjectConst c = s.pack.manifest()["clock"];
    svc::DateTime t;
    if (svc::parseDateTime(c["start"] | "", t)) s.clock.start(t, c["rate"] | 1.0, lv_tick_get());
    s.names = svc::ClockNames();
    JsonObjectConst n = c["names"];
    for (int i = 0; i < 7; ++i) {
        s.names.weekday[i] = n["weekday"][i] | "";
        s.names.weekdayShort[i] = n["weekday_short"][i] | "";
    }
    for (int i = 0; i < 12; ++i) {
        s.names.month[i] = n["month"][i] | "";
        s.names.monthShort[i] = n["month_short"][i] | "";
    }
    if (n["am"].is<const char*>()) s.names.am = n["am"].as<const char*>();
    if (n["pm"].is<const char*>()) s.names.pm = n["pm"].as<const char*>();
}

}  // namespace

// ==================================================================== public API

namespace detail {
lv_obj_t* stage() { return S().stage; }

void showMessage(const std::string& text) {
    State& s = S();
    if (s.page) lv_obj_delete(s.page);
    s.page = newPage();
    lv_obj_set_style_bg_color(s.page, lv_color_black(), 0);
    lv_obj_set_style_bg_opa(s.page, LV_OPA_COVER, 0);
    lv_obj_t* l = lv_label_create(s.page);
    lv_obj_set_style_text_color(l, lv_color_white(), 0);
    lv_obj_set_width(l, kScreenW - 24);
    lv_label_set_long_mode(l, LV_LABEL_LONG_WRAP);
    lv_obj_set_style_text_align(l, LV_TEXT_ALIGN_CENTER, 0);
    lv_label_set_text(l, text.c_str());
    lv_obj_center(l);
    s.statusBarPx = 0;
}

void runAction(JsonObjectConst a, lv_obj_t* source) {
    State& s = S();
    if (s.transition || s.seqTimer) return;
    std::string type = a["type"] | "";
    if (type == "open_screen") {
        std::string target = a["target"] | "";
        NavKind k = appOf(target) != appOf(currentScreen()) ? NavKind::OpenApp : NavKind::Push;
        if (!s.stack.empty()) s.stack.back().scrollY = currentScroll();
        s.stack.push_back({target, 0});
        if (!show(target, k, a["transition"], 0)) s.stack.pop_back();
    } else if (type == "back") {
        back();
    } else if (type == "home") {
        home();
    } else if (type == "play_video") {
        lv_obj_t* v = findById(s.page, a["target"] | "");
        if (v) videoPlay(v);
        else if (source) videoPlay(source);
    } else if (type == "run_sequence") {
        s.seqSteps.clear();
        for (JsonObjectConst st : a["steps"].as<JsonArrayConst>())
            s.seqSteps.push_back({st["screen"] | "", st["ms"] | 0u});
        if (s.seqSteps.empty()) return;
        if (!s.stack.empty()) s.stack.back().scrollY = currentScroll();
        s.seqBaseDepth = s.stack.size() - 1;
        s.seqEnd = a["end"] | "back";
        s.seqIndex = 0;
        s.seqTimer = lv_timer_create(seqTimerCb, 1, nullptr);
    } else {
        platform().log("unknown action " + type);
    }
}
}  // namespace detail

void begin(lv_display_t* disp) {
    State& s = S();
    s.disp = disp;
    s.stage = lv_screen_active();
    lv_obj_remove_style_all(s.stage);
    lv_obj_set_style_bg_color(s.stage, lv_color_black(), 0);
    lv_obj_set_style_bg_opa(s.stage, LV_OPA_COVER, 0);
    lv_obj_remove_flag(s.stage, LV_OBJ_FLAG_SCROLLABLE);

    s.indev = lv_indev_create();
    lv_indev_set_type(s.indev, LV_INDEV_TYPE_POINTER);
    lv_indev_set_read_cb(s.indev, indevRead);
    lv_indev_set_display(s.indev, disp);

    s.fit = platform().getSetting("fit", "width") == "letterbox" ? Fit::Letterbox : Fit::Width;
    s.sleepMs = static_cast<uint32_t>(std::atol(platform().getSetting("sleep_ms", "120000").c_str()));
    s.lastActivity = lv_tick_get();
    lv_timer_create(clockTimer, 1000, nullptr);

    // Boot into the newest snapshot, unless the owner picked another one in the
    // hidden menu since the newest was added.
    std::string newest = svc::Pack::newest();
    std::string picked = platform().getSetting("snapshot", "");
    std::string pickedNewest = platform().getSetting("snapshot_newest", "");
    std::string id = (!picked.empty() && pickedNewest == newest && platform().isFile(svc::Pack::packDir(picked) + "/manifest.json")) ? picked : newest;
    if (id.empty()) {
        detail::showMessage("No content pack on the SD card.\n\nCopy sd/packs/<snapshot> to the card.\nHold the top edge for 3 s for the menu.");
        return;
    }
    if (!switchSnapshot(id, false)) {
        detail::showMessage("Content pack '" + id + "' could not be loaded.\nHold the top edge for 3 s for the menu.");
    }
}

void loop() {
    State& s = S();
    uint32_t now = lv_tick_get();
    uint8_t b = platform().autoBrightness();
    if (b != s.brightness) {
        s.brightness = b;
        if (!s.asleep) platform().setBacklight(b);
    }
    if (!s.asleep && s.sleepMs > 0 && !hiddenMenuOpen() && now - s.lastActivity > s.sleepMs) {
        s.asleep = true;
        platform().setBacklight(0);
    }
}

bool switchSnapshot(const std::string& id, bool persist) {
    State& s = S();
    std::string err;
    detail::videoStopAll();
    if (s.page) {
        lv_obj_delete(s.page);
        s.page = nullptr;
    }
    s.stack.clear();
    detail::clearFonts();
    svc::Pack p;
    if (!p.load(id, err)) {
        platform().log("snapshot " + id + ": " + err);
        return false;
    }
    s.pack = std::move(p);
    std::string terr;
    if (!s.timeline.load(s.pack, terr)) platform().log(terr);
    loadClockFromManifest();
    if (persist) {
        platform().setSetting("snapshot", id);
        platform().setSetting("snapshot_newest", svc::Pack::newest());
    }
    std::string boot = s.pack.systemScreen("boot", s.pack.systemScreen("home"));
    if (boot.empty()) {
        auto apps = s.pack.apps();
        if (!apps.empty()) boot = apps.front() + "/" + (s.pack.manifest()["apps"][0]["entry"] | "main");
    }
    if (boot.empty()) {
        detail::showMessage("Snapshot " + id + " has no boot screen.");
        return true;
    }
    s.stack.push_back({boot, 0});
    if (!show(boot, NavKind::None, JsonObjectConst(), 0)) {
        detail::showMessage("Boot screen " + boot + " could not be built.\nHold the top edge for 3 s for the menu.");
    }
    platform().log("snapshot " + id + " loaded (" + std::to_string(s.pack.chain().size()) + " in chain)");
    return true;
}

const svc::Pack& pack() { return S().pack; }
const svc::Timeline& timeline() { return S().timeline; }
const svc::GameClock& gameClock() { return S().clock; }

std::string clockText(const std::string& fmt) {
    State& s = S();
    if (!s.clock.running()) return "";
    return svc::formatDateTime(s.clock.now(lv_tick_get()), fmt, s.names);
}

bool openScreen(const std::string& screenId, NavKind kind) {
    State& s = S();
    if (!s.stack.empty()) s.stack.back().scrollY = currentScroll();
    s.stack.push_back({screenId, 0});
    if (show(screenId, kind, JsonObjectConst(), 0)) return true;
    s.stack.pop_back();
    return false;
}

void back() {
    State& s = S();
    if (s.stack.size() <= 1 || s.transition) return;
    std::string from = s.stack.back().screen;
    s.stack.pop_back();
    const NavEntry& to = s.stack.back();
    std::string homeId = s.pack.systemScreen("home");
    NavKind k = (to.screen == homeId && appOf(from) != appOf(homeId)) ? NavKind::CloseApp : NavKind::Pop;
    show(to.screen, k, JsonObjectConst(), to.scrollY);
}

void home() {
    State& s = S();
    std::string homeId = s.pack.systemScreen("home");
    if (homeId.empty() || s.transition || currentScreen() == homeId) return;
    // Keep the stack below home (e.g. the lock screen), drop everything above it.
    while (!s.stack.empty() && s.stack.back().screen != homeId) s.stack.pop_back();
    if (s.stack.empty()) s.stack.push_back({homeId, 0});
    show(homeId, NavKind::CloseApp, JsonObjectConst(), s.stack.back().scrollY);
}

std::string currentScreen() {
    State& s = S();
    return s.stack.empty() ? "" : s.stack.back().screen;
}
size_t navDepth() { return S().stack.size(); }
bool scrollBodyTo(int y) {
    lv_obj_t* body = findBody(S().page);
    if (!body) return false;
    lv_obj_update_layout(body);
    lv_obj_scroll_to_y(body, y, LV_ANIM_OFF);
    return true;
}
bool transitionActive() { return S().transition; }

Fit fitMode() { return S().fit; }
void setFitMode(Fit f) {
    S().fit = f;
    platform().setSetting("fit", f == Fit::Letterbox ? "letterbox" : "width");
}

}  // namespace ui
