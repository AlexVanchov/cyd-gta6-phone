// Screen JSON -> LVGL object tree. See schema/screen.schema.json for the format.
//
// Fidelity rules (PLAN.md §7.1) applied here:
//  * one scale factor: unit coordinates x (240 / unit_width), edges rounded to whole pixels;
//  * every object starts with all styles removed (no LVGL look), scrollbars off,
//    no elastic overscroll, no animations other than measured transitions;
//  * pressed states only where the pack provides one.
#include <cmath>
#include <map>

#include "hal/audio.h"
#include "ui/platform.h"
#include "ui/ui.h"

namespace ui {
namespace detail {

// ---------------------------------------------------------------- colours

static int hexv(char c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}

ParsedColor parseColor(JsonVariantConst v) {
    ParsedColor out;
    if (!v.is<const char*>()) return out;
    std::string s = v.as<const char*>();
    for (int depth = 0; depth < 4 && !s.empty() && s[0] == '$'; ++depth) {
        JsonVariantConst t = pack().token(s.substr(1));
        if (!t.is<const char*>()) {
            platform().log("unknown colour token " + s);
            return out;
        }
        s = t.as<const char*>();
    }
    if (s.size() != 7 && s.size() != 9) return out;
    if (s[0] != '#') return out;
    int b[4] = {0, 0, 0, 255};
    for (size_t i = 0; i < (s.size() - 1) / 2; ++i) {
        int hi = hexv(s[1 + i * 2]), lo = hexv(s[2 + i * 2]);
        if (hi < 0 || lo < 0) return out;
        b[i] = hi * 16 + lo;
    }
    out.ok = true;
    out.color = lv_color_make(b[0], b[1], b[2]);
    out.opa = static_cast<lv_opa_t>(b[3]);
    return out;
}

// ---------------------------------------------------------------- fonts

static std::map<std::string, lv_font_t*>& fontCache() {
    static std::map<std::string, lv_font_t*> m;
    return m;
}

const lv_font_t* font(const std::string& id) {
    auto& cache = fontCache();
    auto it = cache.find(id);
    if (it != cache.end()) return it->second ? it->second : LV_FONT_DEFAULT;
    JsonVariantConst f = pack().manifest()["fonts"][id];
    const char* file = f["file"] | "";
    lv_font_t* loaded = nullptr;
    std::string path = *file ? pack().resolveFile(file) : "";
    if (!path.empty()) loaded = lv_binfont_create((platform().lvRoot() + path).c_str());
    if (!loaded) platform().log("font '" + id + "' could not be loaded");
    cache[id] = loaded;
    if (loaded) {
        const char* fb = f["fallback"] | "";
        if (*fb && id != fb) loaded->fallback = font(fb);
    }
    return loaded ? loaded : LV_FONT_DEFAULT;
}

void clearFonts() {
    for (auto& kv : fontCache())
        if (kv.second) lv_binfont_destroy(kv.second);
    fontCache().clear();
}

// ---------------------------------------------------------------- paths & units

std::string lvPath(const std::string& appDir, const std::string& src) {
    // "<app>:path" refers to another app's directory; otherwise relative to this app.
    auto colon = src.find(':');
    if (colon != std::string::npos && colon > 0 && src.find('/') > colon) {
        std::string dir = pack().appDir(src.substr(0, colon));
        return platform().lvRoot() + dir + "/" + src.substr(colon + 1);
    }
    return platform().lvRoot() + appDir + "/" + src;
}

int px(const BuildCtx& c, float unit) { return static_cast<int>(std::lround(unit * c.scale)); }

// ---------------------------------------------------------------- per-object data

struct ElemData {
    std::string id;
    std::string action;       // compact JSON, empty if none (a JsonDocument per button costs ~0.5 KB)
    std::string src, pressedSrc;
    bool clockBound = false;
};

static void onDelete(lv_event_t* e) {
    auto* d = static_cast<ElemData*>(lv_event_get_user_data(e));
    delete d;
}

static ElemData* data(lv_obj_t* o) {
    auto* d = static_cast<ElemData*>(lv_obj_get_user_data(o));
    if (!d) {
        d = new ElemData();
        lv_obj_set_user_data(o, d);
        lv_obj_add_event_cb(o, onDelete, LV_EVENT_DELETE, d);
    }
    return d;
}

lv_obj_t* findById(lv_obj_t* root, const std::string& id) {
    if (!root) return nullptr;
    auto* d = static_cast<ElemData*>(lv_obj_get_user_data(root));
    if (d && d->id == id) return root;
    uint32_t n = lv_obj_get_child_count(root);
    for (uint32_t i = 0; i < n; ++i) {
        if (lv_obj_t* f = findById(lv_obj_get_child(root, i), id)) return f;
    }
    return nullptr;
}

// ---------------------------------------------------------------- clock binding

static std::vector<std::pair<lv_obj_t*, std::string>>& clockLabels() {
    static std::vector<std::pair<lv_obj_t*, std::string>> v;
    return v;
}

static void onClockLabelDelete(lv_event_t* e) {
    lv_obj_t* o = static_cast<lv_obj_t*>(lv_event_get_target(e));
    auto& v = clockLabels();
    for (auto it = v.begin(); it != v.end(); ++it)
        if (it->first == o) {
            v.erase(it);
            break;
        }
}

void bindClock(lv_obj_t* label, const std::string& fmt) {
    clockLabels().push_back({label, fmt});
    lv_obj_add_event_cb(label, onClockLabelDelete, LV_EVENT_DELETE, nullptr);
    lv_label_set_text(label, clockText(fmt).c_str());
}

void refreshClockLabels() {
    for (auto& kv : clockLabels()) {
        std::string t = clockText(kv.second);
        if (t != lv_label_get_text(kv.first)) lv_label_set_text(kv.first, t.c_str());
    }
}

// ---------------------------------------------------------------- styling helpers

static void bare(lv_obj_t* o) {
    lv_obj_remove_style_all(o);
    lv_obj_remove_flag(o, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_remove_flag(o, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_remove_flag(o, LV_OBJ_FLAG_CLICK_FOCUSABLE);
    lv_obj_remove_flag(o, LV_OBJ_FLAG_SCROLL_ELASTIC);
    lv_obj_add_flag(o, LV_OBJ_FLAG_EVENT_BUBBLE);
    lv_obj_set_scrollbar_mode(o, LV_SCROLLBAR_MODE_OFF);
}

static void applyBoxStyle(lv_obj_t* o, JsonObjectConst e, const BuildCtx& c, lv_style_selector_t sel) {
    ParsedColor bg = parseColor(e["bg"]);
    if (bg.ok) {
        lv_obj_set_style_bg_color(o, bg.color, sel);
        lv_obj_set_style_bg_opa(o, bg.opa, sel);
    }
    JsonObjectConst grad = e["bg_grad"];
    if (!grad.isNull()) {
        JsonArrayConst cols = grad["colors"];
        ParsedColor a = parseColor(cols[0]), b = parseColor(cols[1]);
        if (a.ok && b.ok) {
            lv_obj_set_style_bg_color(o, a.color, sel);
            lv_obj_set_style_bg_grad_color(o, b.color, sel);
            lv_obj_set_style_bg_opa(o, a.opa, sel);
            const char* dir = grad["dir"] | "ver";
            lv_obj_set_style_bg_grad_dir(o, std::string(dir) == "hor" ? LV_GRAD_DIR_HOR : LV_GRAD_DIR_VER, sel);
            JsonArrayConst stops = grad["stops"];
            if (stops.size() == 2) {
                lv_obj_set_style_bg_main_stop(o, stops[0].as<int>(), sel);
                lv_obj_set_style_bg_grad_stop(o, stops[1].as<int>(), sel);
            }
        }
    }
    if (e["radius"].is<float>()) {
        float r = e["radius"].as<float>();
        lv_obj_set_style_radius(o, r >= 9999 ? LV_RADIUS_CIRCLE : px(c, r), sel);
    }
    if (e["border_w"].is<float>()) {
        lv_obj_set_style_border_width(o, px(c, e["border_w"].as<float>()), sel);
        ParsedColor bc = parseColor(e["border_color"]);
        if (bc.ok) {
            lv_obj_set_style_border_color(o, bc.color, sel);
            lv_obj_set_style_border_opa(o, bc.opa, sel);
        }
    }
    if (e["opa"].is<int>()) lv_obj_set_style_opa(o, static_cast<lv_opa_t>(e["opa"].as<int>()), sel);
    if (e["clip"] | false) lv_obj_set_style_clip_corner(o, true, sel);
}

static void onPressSwap(lv_event_t* ev) {
    lv_obj_t* o = static_cast<lv_obj_t*>(lv_event_get_current_target(ev));
    auto* d = static_cast<ElemData*>(lv_obj_get_user_data(o));
    if (!d) return;
    // The image to swap may be the object itself or its first image child.
    lv_obj_t* img = o;
    if (d->pressedSrc.empty()) return;
    bool down = lv_event_get_code(ev) == LV_EVENT_PRESSED;
    lv_image_set_src(img, (down ? d->pressedSrc : d->src).c_str());
}

static void onClick(lv_event_t* ev) {
    lv_obj_t* o = static_cast<lv_obj_t*>(lv_event_get_current_target(ev));
    auto* d = static_cast<ElemData*>(lv_obj_get_user_data(o));
    if (!d || d->action.empty()) return;
    // Parse into a local document: the action may replace the page and delete o (and d).
    JsonDocument doc;
    if (deserializeJson(doc, d->action)) return;
    runAction(doc.as<JsonObjectConst>(), o);
}

static void makeInteractive(lv_obj_t* o, JsonObjectConst e, const BuildCtx& c, int wpx, int hpx) {
    JsonObjectConst action = e["action"];
    JsonObjectConst pressed = e["pressed"];
    if (action.isNull() && pressed.isNull()) return;
    lv_obj_add_flag(o, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_remove_flag(o, LV_OBJ_FLAG_EVENT_BUBBLE);
    if (!action.isNull()) {
        serializeJson(action, data(o)->action);
        lv_obj_add_event_cb(o, onClick, LV_EVENT_CLICKED, nullptr);
    }
    if (!pressed.isNull()) applyBoxStyle(o, pressed, c, LV_STATE_PRESSED);
    int small = wpx < hpx ? wpx : hpx;
    if (small < kMinTapPx) lv_obj_set_ext_click_area(o, (kMinTapPx - small + 1) / 2);
}

// ---------------------------------------------------------------- element builders

static void place(lv_obj_t* o, JsonObjectConst e, const BuildCtx& c, float ox, float oy, int& wpx, int& hpx) {
    float x = e["x"] | 0.0f, y = e["y"] | 0.0f;
    int x0 = px(c, x), y0 = px(c, y);
    lv_obj_set_pos(o, x0 - px(c, ox), y0 - px(c, oy));
    wpx = hpx = -1;
    if (e["w"].is<float>()) {
        wpx = px(c, x + e["w"].as<float>()) - x0;
        lv_obj_set_width(o, wpx);
    }
    if (e["h"].is<float>()) {
        hpx = px(c, y + e["h"].as<float>()) - y0;
        lv_obj_set_height(o, hpx);
    }
}

static void buildChildren(JsonArrayConst kids, lv_obj_t* parent, const BuildCtx& c, float ox, float oy) {
    for (JsonObjectConst k : kids) buildElement(k, parent, c, ox, oy);
}

// One label per text element (no wrapper box: LVGL objects cost ~0.3 KB each and
// there is no PSRAM). Vertical alignment becomes top padding computed from the
// measured text height.
static lv_obj_t* buildText(JsonObjectConst e, lv_obj_t* parent, const BuildCtx& c, float ox, float oy) {
    lv_obj_t* l = lv_label_create(parent);
    bare(l);
    int w, h;
    place(l, e, c, ox, oy, w, h);
    const lv_font_t* f = font(e["font"] | "");
    lv_obj_set_style_text_font(l, f, 0);
    ParsedColor col = parseColor(e["color"]);
    if (col.ok) {
        lv_obj_set_style_text_color(l, col.color, 0);
        lv_obj_set_style_text_opa(l, col.opa, 0);
    }
    std::string align = e["align"] | "left";
    lv_obj_set_style_text_align(l, align == "center" ? LV_TEXT_ALIGN_CENTER
                                   : align == "right" ? LV_TEXT_ALIGN_RIGHT
                                                      : LV_TEXT_ALIGN_LEFT, 0);
    int32_t ls = 0, lts = 0;
    if (e["line_space"].is<float>()) lv_obj_set_style_text_line_space(l, ls = px(c, e["line_space"].as<float>()), 0);
    if (e["letter_space"].is<float>()) lv_obj_set_style_text_letter_space(l, lts = px(c, e["letter_space"].as<float>()), 0);
    std::string mode = e["mode"] | "wrap";
    lv_label_set_long_mode(l, mode == "clip" ? LV_LABEL_LONG_CLIP
                              : mode == "dots" ? LV_LABEL_LONG_DOT
                                               : LV_LABEL_LONG_WRAP);
    if (w < 0) lv_obj_set_width(l, LV_SIZE_CONTENT);
    if (e["clock_format"].is<const char*>()) bindClock(l, e["clock_format"].as<const char*>());
    else lv_label_set_text(l, e["text"] | "");
    // Wrapped text without a background or action may grow past its measured
    // box (descenders, a slightly different wrap): size it to its content.
    bool boxed = !e["bg"].isNull() || !e["bg_grad"].isNull() || !e["action"].isNull() || !e["border_w"].isNull();
    if (h < 0 || (mode == "wrap" && !boxed)) lv_obj_set_height(l, LV_SIZE_CONTENT);
    std::string valign = e["valign"] | "top";
    if (h > 0 && valign != "top") {
        lv_point_t sz;
        lv_text_get_size(&sz, lv_label_get_text(l), f, lts, ls, w > 0 ? w : LV_COORD_MAX, LV_TEXT_FLAG_NONE);
        int32_t lh = lv_font_get_line_height(f);
        if (mode != "wrap" && sz.y > lh) sz.y = lh;  // clipped/dotted text shows one line
        int32_t pad = valign == "center" ? (h - sz.y) / 2 : h - sz.y;
        if (pad > 0) {
            lv_obj_set_style_pad_top(l, pad, 0);
            if (lv_obj_get_style_height(l, 0) != LV_SIZE_CONTENT) lv_obj_set_height(l, h);
        }
    }
    applyBoxStyle(l, e, c, 0);
    makeInteractive(l, e, c, w, h);
    return l;
}

static lv_obj_t* buildImage(JsonObjectConst e, lv_obj_t* parent, const BuildCtx& c, float ox, float oy) {
    lv_obj_t* img = lv_image_create(parent);
    bare(img);
    int w, h;
    place(img, e, c, ox, oy, w, h);
    ElemData* d = data(img);
    d->src = lvPath(c.appDir, e["src"] | "");
    if (e["pressed_src"].is<const char*>()) d->pressedSrc = lvPath(c.appDir, e["pressed_src"].as<const char*>());
    lv_image_set_src(img, d->src.c_str());
    // Assets are pre-sliced at device size; never scale at runtime.
    lv_image_set_inner_align(img, LV_IMAGE_ALIGN_TOP_LEFT);
    applyBoxStyle(img, e, c, 0);
    makeInteractive(img, e, c, w, h);
    if (!d->pressedSrc.empty()) {
        lv_obj_add_flag(img, LV_OBJ_FLAG_CLICKABLE);
        lv_obj_add_event_cb(img, onPressSwap, LV_EVENT_PRESSED, nullptr);
        lv_obj_add_event_cb(img, onPressSwap, LV_EVENT_RELEASED, nullptr);
        lv_obj_add_event_cb(img, onPressSwap, LV_EVENT_PRESS_LOST, nullptr);
    }
    return img;
}

static lv_obj_t* buildBox(JsonObjectConst e, lv_obj_t* parent, const BuildCtx& c, float ox, float oy) {
    lv_obj_t* o = lv_obj_create(parent);
    bare(o);
    int w, h;
    place(o, e, c, ox, oy, w, h);
    applyBoxStyle(o, e, c, 0);
    float x = e["x"] | 0.0f, y = e["y"] | 0.0f;
    buildChildren(e["children"], o, c, x, y);
    makeInteractive(o, e, c, w, h);
    return o;
}

static void onLoopScroll(lv_event_t* ev) {
    lv_obj_t* o = static_cast<lv_obj_t*>(lv_event_get_target(ev));
    // Captured feeds loop at the end (PLAN.md §6): jump back to the first item.
    if (lv_obj_get_scroll_bottom(o) <= 0 && lv_obj_get_scroll_y(o) > 0) lv_obj_scroll_to_y(o, 0, LV_ANIM_OFF);
}

static lv_obj_t* buildScroll(JsonObjectConst e, lv_obj_t* parent, const BuildCtx& c, float ox, float oy) {
    lv_obj_t* o = lv_obj_create(parent);
    bare(o);
    int w, h;
    place(o, e, c, ox, oy, w, h);
    applyBoxStyle(o, e, c, 0);
    lv_obj_add_flag(o, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_add_flag(o, LV_OBJ_FLAG_CLICKABLE);  // drag target for swipes
    lv_obj_add_flag(o, LV_OBJ_FLAG_SCROLL_MOMENTUM);
    lv_obj_remove_flag(o, LV_OBJ_FLAG_EVENT_BUBBLE);
    std::string dir = e["dir"] | "y";
    lv_obj_set_scroll_dir(o, dir == "x" ? LV_DIR_HOR : LV_DIR_VER);
    if (std::string(e["snap"] | "none") == "page") {
        if (dir == "x") lv_obj_set_scroll_snap_x(o, LV_SCROLL_SNAP_START);
        else lv_obj_set_scroll_snap_y(o, LV_SCROLL_SNAP_START);
        lv_obj_add_flag(o, LV_OBJ_FLAG_SCROLL_ONE);
    }
    float x = e["x"] | 0.0f, y = e["y"] | 0.0f;
    buildChildren(e["children"], o, c, x, y);
    if (e["loop"] | false) lv_obj_add_event_cb(o, onLoopScroll, LV_EVENT_SCROLL_END, nullptr);
    if (e["start"].is<float>()) {
        int s = px(c, e["start"].as<float>());
        lv_obj_update_layout(o);
        if (dir == "x") lv_obj_scroll_to_x(o, s, LV_ANIM_OFF);
        else lv_obj_scroll_to_y(o, s, LV_ANIM_OFF);
    }
    return o;
}

static lv_obj_t* buildList(JsonObjectConst e, lv_obj_t* parent, const BuildCtx& c, float ox, float oy) {
    lv_obj_t* o = lv_obj_create(parent);
    bare(o);
    int w, h;
    place(o, e, c, ox, oy, w, h);
    applyBoxStyle(o, e, c, 0);
    float x = e["x"] | 0.0f, y = e["y"] | 0.0f;
    for (JsonObjectConst item : e["items"].as<JsonArrayConst>()) {
        lv_obj_t* it = lv_obj_create(o);
        bare(it);
        int iw, ih;
        place(it, item, c, x, y, iw, ih);
        applyBoxStyle(it, item, c, 0);
        buildChildren(item["children"], it, c, item["x"] | 0.0f, item["y"] | 0.0f);
        makeInteractive(it, item, c, iw, ih);
        if (item["id"].is<const char*>()) data(it)->id = item["id"].as<const char*>();
    }
    return o;
}

static lv_obj_t* buildVideo(JsonObjectConst e, lv_obj_t* parent, const BuildCtx& c, float ox, float oy) {
    lv_obj_t* img = lv_image_create(parent);
    bare(img);
    int w, h;
    place(img, e, c, ox, oy, w, h);
    lv_image_set_inner_align(img, LV_IMAGE_ALIGN_TOP_LEFT);
    if (e["poster"].is<const char*>()) lv_image_set_src(img, lvPath(c.appDir, e["poster"].as<const char*>()).c_str());
    videoAttach(img, lvPath(c.appDir, e["src"] | ""), e["autoplay"] | false, e["loop"] | true);
    makeInteractive(img, e, c, w, h);
    return img;
}

static void onStation(lv_event_t* ev) {
    lv_obj_t* o = static_cast<lv_obj_t*>(lv_event_get_current_target(ev));
    auto* d = static_cast<ElemData*>(lv_obj_get_user_data(o));
    if (d) hal::audio().play(d->src);
}

static lv_obj_t* buildStation(JsonObjectConst e, lv_obj_t* parent, const BuildCtx& c, float ox, float oy) {
    // Reserved for the radio (PLAN.md §9): a tap area that calls the audio stub.
    lv_obj_t* o = buildBox(e, parent, c, ox, oy);
    data(o)->src = e["src"] | "";
    lv_obj_add_flag(o, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_remove_flag(o, LV_OBJ_FLAG_EVENT_BUBBLE);
    lv_obj_add_event_cb(o, onStation, LV_EVENT_CLICKED, nullptr);
    return o;
}

lv_obj_t* buildElement(JsonObjectConst e, lv_obj_t* parent, const BuildCtx& c, float ox, float oy) {
    std::string type = e["type"] | "";
    lv_obj_t* o = nullptr;
    if (type == "text") o = buildText(e, parent, c, ox, oy);
    else if (type == "image") o = buildImage(e, parent, c, ox, oy);
    else if (type == "rect" || type == "button") o = buildBox(e, parent, c, ox, oy);
    else if (type == "scroll") o = buildScroll(e, parent, c, ox, oy);
    else if (type == "list") o = buildList(e, parent, c, ox, oy);
    else if (type == "video") o = buildVideo(e, parent, c, ox, oy);
    else if (type == "station") o = buildStation(e, parent, c, ox, oy);
    else {
        platform().log("unknown element type '" + type + "' in " + c.screenId);
        return nullptr;
    }
    if (o && e["id"].is<const char*>()) data(o)->id = e["id"].as<const char*>();
    if (o && (e["hidden"] | false)) lv_obj_add_flag(o, LV_OBJ_FLAG_HIDDEN);
    return o;
}

// ---------------------------------------------------------------- screens

static lv_obj_t* region(lv_obj_t* page, int y, int h) {
    lv_obj_t* r = lv_obj_create(page);
    bare(r);
    lv_obj_set_pos(r, 0, y);
    lv_obj_set_size(r, kScreenW, h);
    return r;
}

bool buildScreen(const std::string& screenId, lv_obj_t* page, std::string& err, int& statusBarPx) {
    JsonDocument doc;
    BuildCtx c;
    c.screenId = screenId;
    if (!pack().loadScreen(screenId, doc, c.appDir, err)) return false;
    JsonObjectConst s = doc.as<JsonObjectConst>();

    float unitW = s["unit_width"] | pack().unitWidth();
    float height = s["height"] | (unitW * kScreenH / kScreenW);
    float topH = s["top_h"] | 0.0f, bottomH = s["bottom_h"] | 0.0f;

    // Optional system status bar fragment, pinned at the top.
    JsonDocument sbDoc;
    std::string sbDir;
    bool withSb = s["status_bar"] | false;
    std::string sbId = pack().systemScreen("status_bar");
    if (withSb && !sbId.empty()) {
        std::string e2;
        if (pack().loadScreen(sbId, sbDoc, sbDir, e2)) {
            float h = sbDoc["height"] | 0.0f;
            if (h > topH) topH = h;
        } else {
            platform().log(e2);
            withSb = false;
        }
    } else {
        withSb = false;
    }

    Fit fit = fitMode();
    c.scale = kScreenW / unitW;
    int offX = 0;
    if (fit == Fit::Letterbox) {
        float sh = kScreenH / height;
        if (sh < c.scale) {
            c.scale = sh;
            offX = (kScreenW - px(c, unitW)) / 2;
        }
    }

    lv_obj_set_style_bg_color(page, lv_color_black(), 0);
    lv_obj_set_style_bg_opa(page, LV_OPA_COVER, 0);
    lv_obj_t* canvas = page;
    if (offX > 0) {
        canvas = lv_obj_create(page);
        bare(canvas);
        lv_obj_set_pos(canvas, offX, 0);
        lv_obj_set_size(canvas, px(c, unitW), px(c, height));
        lv_obj_set_style_clip_corner(canvas, false, 0);
    }
    ParsedColor bg = parseColor(s["bg"]);
    if (bg.ok) {
        lv_obj_set_style_bg_color(canvas, bg.color, 0);
        lv_obj_set_style_bg_opa(canvas, LV_OPA_COVER, 0);
    }
    if (s["bg_image"].is<const char*>()) {
        lv_obj_t* wall = lv_image_create(canvas);
        bare(wall);
        lv_obj_set_pos(wall, 0, 0);
        lv_image_set_src(wall, lvPath(c.appDir, s["bg_image"].as<const char*>()).c_str());
    }

    int topPx = px(c, topH), bottomPx = px(c, bottomH), fullPx = px(c, height);
    int canvasH = fit == Fit::Letterbox ? fullPx : kScreenH;
    if (fit == Fit::Letterbox && fullPx < kScreenH) canvasH = fullPx;
    int bodyPx = canvasH - topPx - bottomPx;

    lv_obj_t* body = region(canvas, topPx, bodyPx);
    lv_obj_set_width(body, fit == Fit::Letterbox ? px(c, unitW) : kScreenW);
    int contentPx = px(c, height - bottomH) - topPx;
    if (contentPx > bodyPx) {
        lv_obj_add_flag(body, LV_OBJ_FLAG_SCROLLABLE);
        lv_obj_add_flag(body, LV_OBJ_FLAG_CLICKABLE);
        lv_obj_add_flag(body, LV_OBJ_FLAG_SCROLL_MOMENTUM);
        lv_obj_remove_flag(body, LV_OBJ_FLAG_EVENT_BUBBLE);
        lv_obj_set_scroll_dir(body, LV_DIR_VER);
        // Make the scroll range exactly the captured content height.
        lv_obj_t* spacer = lv_obj_create(body);
        bare(spacer);
        lv_obj_set_pos(spacer, 0, contentPx - 1);
        lv_obj_set_size(spacer, 1, 1);
    }
    lv_obj_t* top = topPx > 0 ? region(canvas, 0, topPx) : nullptr;
    lv_obj_t* bottom = bottomPx > 0 ? region(canvas, canvasH - bottomPx, bottomPx) : nullptr;
    if (top && fit == Fit::Letterbox) lv_obj_set_width(top, px(c, unitW));
    if (bottom && fit == Fit::Letterbox) lv_obj_set_width(bottom, px(c, unitW));

    for (JsonObjectConst e : s["elements"].as<JsonArrayConst>()) {
        float y = e["y"] | 0.0f;
        std::string reg = e["region"] | "";
        if (reg.empty()) reg = (top && y < topH) ? "top" : (bottom && y >= height - bottomH) ? "bottom" : "body";
        if (reg == "top" && top) buildElement(e, top, c, 0, 0);
        else if (reg == "bottom" && bottom) buildElement(e, bottom, c, 0, height - bottomH);
        else buildElement(e, body, c, 0, topH);
    }
    if (withSb && top) {
        BuildCtx sc = c;
        sc.appDir = sbDir;
        sc.screenId = sbId;
        for (JsonObjectConst e : sbDoc["elements"].as<JsonArrayConst>()) buildElement(e, top, sc, 0, 0);
    }
    statusBarPx = withSb ? px(c, sbDoc["height"] | 0.0f) : 0;
    return true;
}

}  // namespace detail
}  // namespace ui
