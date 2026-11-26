// Headless PC simulator: runs the firmware's src/ui code against an SD-card
// folder and writes screenshots. No window.
//
//   sim --pack <sd>/packs/<id> [--screen <app>/<screen>] --out shot.png
//       [--input "tap:x,y;swipe:x1,y1,x2,y2,ms;hold:x,y,ms;wait:ms"]
//       [--switch <snapshot-id>] [--advance ms] [--setting key=value]
//       [--regions regions.json] [--measure-transition] [--verbose]
//
// --pack may also be just the snapshot id when --sd <dir> is given.
#include <dirent.h>
#include <sys/stat.h>
#include <zlib.h>

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <map>
#include <sstream>
#include <string>
#include <vector>

#include "lvgl.h"
#include "ui/platform.h"
#include "ui/ui.h"

namespace {

uint32_t g_ms = 0;
uint32_t simTick() { return g_ms; }

uint16_t g_fb[ui::kScreenW * ui::kScreenH];
bool g_verbose = false;

struct Event {
    std::string kind;
    std::vector<int> v;
};

// Pointer script state
struct Touch {
    bool down = false;
    int16_t x = 0, y = 0;
} g_touch;

class SimPlatform : public ui::Platform {
public:
    std::string sd;
    std::map<std::string, std::string> settings;

    std::string lvRoot() const override { return "S:" + sd; }
    bool readFile(const std::string& path, std::string& out) override {
        std::ifstream f(sd + path, std::ios::binary);
        if (!f) return false;
        std::stringstream ss;
        ss << f.rdbuf();
        out = ss.str();
        return true;
    }
    bool isDir(const std::string& path) override {
        struct stat st;
        return stat((sd + path).c_str(), &st) == 0 && S_ISDIR(st.st_mode);
    }
    bool isFile(const std::string& path) override {
        struct stat st;
        return stat((sd + path).c_str(), &st) == 0 && S_ISREG(st.st_mode);
    }
    std::vector<std::string> listDirs(const std::string& path) override {
        std::vector<std::string> out;
        DIR* d = opendir((sd + path).c_str());
        if (!d) return out;
        while (dirent* e = readdir(d)) {
            std::string n = e->d_name;
            if (n == "." || n == "..") continue;
            if (isDir(path + "/" + n)) out.push_back(n);
        }
        closedir(d);
        return out;
    }
    std::string getSetting(const std::string& k, const std::string& def) override {
        auto it = settings.find(k);
        return it == settings.end() ? def : it->second;
    }
    void setSetting(const std::string& k, const std::string& v) override { settings[k] = v; }
    bool readPointer(int16_t& x, int16_t& y) override {
        x = g_touch.x;
        y = g_touch.y;
        return g_touch.down;
    }
    void log(const std::string& msg) override {
        if (g_verbose) std::fprintf(stderr, "[ui] %s\n", msg.c_str());
    }
    void calibrateTouch() override { log("calibrateTouch (device only)"); }
    void hardwareTest() override { log("hardwareTest (device only)"); }
    std::string deviceInfo() override { return "Simulator"; }
};

SimPlatform g_platform;

void flush(lv_display_t* disp, const lv_area_t* a, uint8_t* px) {
    const uint16_t* src = reinterpret_cast<const uint16_t*>(px);
    for (int y = a->y1; y <= a->y2; ++y)
        for (int x = a->x1; x <= a->x2; ++x) g_fb[y * ui::kScreenW + x] = *src++;
    lv_display_flush_ready(disp);
}

void step(uint32_t ms) {
    for (uint32_t t = 0; t < ms; t += 5) {
        g_ms += 5;
        lv_timer_handler();
    }
}

// ---- PNG ----
void putU32(std::vector<uint8_t>& v, uint32_t x) {
    v.push_back(x >> 24);
    v.push_back(x >> 16);
    v.push_back(x >> 8);
    v.push_back(x);
}

void chunk(std::vector<uint8_t>& out, const char* type, const std::vector<uint8_t>& data) {
    putU32(out, static_cast<uint32_t>(data.size()));
    std::vector<uint8_t> td(type, type + 4);
    td.insert(td.end(), data.begin(), data.end());
    out.insert(out.end(), td.begin(), td.end());
    putU32(out, static_cast<uint32_t>(crc32(0, td.data(), static_cast<uInt>(td.size()))));
}

bool writePng(const std::string& path) {
    const int W = ui::kScreenW, H = ui::kScreenH;
    std::vector<uint8_t> raw;
    raw.reserve((W * 3 + 1) * H);
    for (int y = 0; y < H; ++y) {
        raw.push_back(0);
        for (int x = 0; x < W; ++x) {
            uint16_t c = g_fb[y * W + x];
            uint8_t r = (c >> 11) & 0x1F, g = (c >> 5) & 0x3F, b = c & 0x1F;
            raw.push_back(static_cast<uint8_t>((r << 3) | (r >> 2)));
            raw.push_back(static_cast<uint8_t>((g << 2) | (g >> 4)));
            raw.push_back(static_cast<uint8_t>((b << 3) | (b >> 2)));
        }
    }
    uLongf zlen = compressBound(static_cast<uLong>(raw.size()));
    std::vector<uint8_t> z(zlen);
    if (compress2(z.data(), &zlen, raw.data(), static_cast<uLong>(raw.size()), 9) != Z_OK) return false;
    z.resize(zlen);
    std::vector<uint8_t> out = {0x89, 'P', 'N', 'G', '\r', '\n', 0x1A, '\n'};
    std::vector<uint8_t> ihdr;
    putU32(ihdr, W);
    putU32(ihdr, H);
    ihdr.insert(ihdr.end(), {8, 2, 0, 0, 0});
    chunk(out, "IHDR", ihdr);
    chunk(out, "IDAT", z);
    chunk(out, "IEND", {});
    FILE* f = std::fopen(path.c_str(), "wb");
    if (!f) return false;
    std::fwrite(out.data(), 1, out.size(), f);
    std::fclose(f);
    return true;
}

// ---- text regions (for per-text diffs) ----
std::string jsonEscape(const char* s) {
    std::string o;
    for (; *s; ++s) {
        unsigned char c = static_cast<unsigned char>(*s);
        if (c == '"' || c == '\\') { o += '\\'; o += static_cast<char>(c); }
        else if (c == '\n') o += "\\n";
        else if (c < 0x20) { char b[8]; std::snprintf(b, sizeof b, "\\u%04x", c); o += b; }
        else o += static_cast<char>(c);
    }
    return o;
}

void collectLabels(lv_obj_t* o, std::vector<std::string>& out) {
    if (lv_obj_has_flag(o, LV_OBJ_FLAG_HIDDEN)) return;
    if (lv_obj_check_type(o, &lv_label_class)) {
        lv_area_t a;
        lv_obj_get_coords(o, &a);
        lv_area_t vis = {a.x1 < 0 ? 0 : a.x1, a.y1 < 0 ? 0 : a.y1,
                         a.x2 > ui::kScreenW - 1 ? ui::kScreenW - 1 : a.x2,
                         a.y2 > ui::kScreenH - 1 ? ui::kScreenH - 1 : a.y2};
        if (vis.x1 <= vis.x2 && vis.y1 <= vis.y2) {
            char b[160];
            std::snprintf(b, sizeof b, "{\"x\":%d,\"y\":%d,\"w\":%d,\"h\":%d,\"text\":\"", (int)vis.x1, (int)vis.y1,
                          (int)lv_area_get_width(&vis), (int)lv_area_get_height(&vis));
            out.push_back(std::string(b) + jsonEscape(lv_label_get_text(o)) + "\"}");
        }
    }
    uint32_t n = lv_obj_get_child_count(o);
    for (uint32_t i = 0; i < n; ++i) collectLabels(lv_obj_get_child(o, i), out);
}

std::vector<Event> parseInput(const std::string& s) {
    std::vector<Event> ev;
    std::stringstream ss(s);
    std::string item;
    while (std::getline(ss, item, ';')) {
        if (item.empty()) continue;
        auto colon = item.find(':');
        Event e;
        e.kind = item.substr(0, colon);
        std::stringstream vs(colon == std::string::npos ? "" : item.substr(colon + 1));
        std::string n;
        while (std::getline(vs, n, ',')) e.v.push_back(std::atoi(n.c_str()));
        ev.push_back(e);
    }
    return ev;
}

void runEvent(const Event& e) {
    auto at = [](int x, int y) { g_touch.x = static_cast<int16_t>(x); g_touch.y = static_cast<int16_t>(y); };
    if (e.kind == "tap" && e.v.size() >= 2) {
        at(e.v[0], e.v[1]);
        g_touch.down = true;
        step(80);
        g_touch.down = false;
        step(40);
    } else if (e.kind == "hold" && e.v.size() >= 3) {
        at(e.v[0], e.v[1]);
        g_touch.down = true;
        step(static_cast<uint32_t>(e.v[2]));
        g_touch.down = false;
        step(40);
    } else if (e.kind == "swipe" && e.v.size() >= 5) {
        int steps = e.v[4] / 10 > 0 ? e.v[4] / 10 : 1;
        g_touch.down = true;
        for (int i = 0; i <= steps; ++i) {
            at(e.v[0] + (e.v[2] - e.v[0]) * i / steps, e.v[1] + (e.v[3] - e.v[1]) * i / steps);
            step(10);
        }
        g_touch.down = false;
        step(40);
    } else if (e.kind == "wait" && !e.v.empty()) {
        step(static_cast<uint32_t>(e.v[0]));
    } else {
        std::fprintf(stderr, "bad input event '%s'\n", e.kind.c_str());
    }
}

int usage() {
    std::fprintf(stderr,
                 "usage: sim --pack <sd>/packs/<id> [--screen app/screen] --out file.png\n"
                 "           [--input \"tap:x,y;swipe:x1,y1,x2,y2,ms;hold:x,y,ms;wait:ms\"]\n"
                 "           [--switch id] [--advance ms] [--scroll y] [--setting k=v] [--regions out.json]\n"
                 "           [--measure-transition] [--verbose]\n");
    return 2;
}

}  // namespace

int main(int argc, char** argv) {
    std::string packArg, sdArg, screen, out, input, switchTo, regions;
    uint32_t advance = 0;
    int scrollY = -1;
    bool measure = false;
    for (int i = 1; i < argc; ++i) {
        std::string a = argv[i];
        auto next = [&]() -> std::string { return i + 1 < argc ? argv[++i] : ""; };
        if (a == "--pack") packArg = next();
        else if (a == "--sd") sdArg = next();
        else if (a == "--screen") screen = next();
        else if (a == "--out") out = next();
        else if (a == "--input") input = next();
        else if (a == "--switch") switchTo = next();
        else if (a == "--advance") advance = static_cast<uint32_t>(std::atol(next().c_str()));
        else if (a == "--regions") regions = next();
        else if (a == "--scroll") scrollY = std::atoi(next().c_str());
        else if (a == "--measure-transition") measure = true;
        else if (a == "--verbose") g_verbose = true;
        else if (a == "--setting") {
            std::string kv = next();
            auto eq = kv.find('=');
            if (eq != std::string::npos) g_platform.settings[kv.substr(0, eq)] = kv.substr(eq + 1);
        } else return usage();
    }
    if (packArg.empty() && sdArg.empty()) return usage();

    std::string packId;
    if (!sdArg.empty()) {
        g_platform.sd = sdArg;
        packId = packArg;
    } else {
        // <sd>/packs/<id>
        while (!packArg.empty() && packArg.back() == '/') packArg.pop_back();
        auto p1 = packArg.rfind('/');
        packId = packArg.substr(p1 + 1);
        std::string packsDir = packArg.substr(0, p1);
        g_platform.sd = packsDir.substr(0, packsDir.rfind('/'));
        if (g_platform.sd.empty()) g_platform.sd = ".";
    }
    if (g_platform.sd[0] != '/') {
        char cwd[4096];
        if (getcwd(cwd, sizeof cwd)) g_platform.sd = std::string(cwd) + "/" + g_platform.sd;
    }
    if (!packId.empty()) {
        g_platform.settings["snapshot"] = packId;
        g_platform.settings["snapshot_newest"] = "";  // filled below
    }

    ui::setPlatform(&g_platform);
    lv_init();
    lv_tick_set_cb(simTick);
    lv_display_t* disp = lv_display_create(ui::kScreenW, ui::kScreenH);
    alignas(64) static uint8_t buf[ui::kScreenW * 32 * 2];
    lv_display_set_buffers(disp, buf, nullptr, sizeof buf, LV_DISPLAY_RENDER_MODE_PARTIAL);
    lv_display_set_flush_cb(disp, flush);

    // Make the requested pack count as the user's pick.
    if (!packId.empty()) g_platform.settings["snapshot_newest"] = svc::Pack::newest();
    ui::begin(disp);
    step(50);
    if (!switchTo.empty() && !ui::switchSnapshot(switchTo, true)) {
        std::fprintf(stderr, "switch to %s failed\n", switchTo.c_str());
        return 1;
    }
    if (!screen.empty() && screen != ui::currentScreen() && !ui::openScreen(screen, ui::NavKind::None)) {
        std::fprintf(stderr, "screen %s could not be built\n", screen.c_str());
        return 1;
    }
    step(100);

    auto events = parseInput(input);
    std::vector<uint16_t> prev(g_fb, g_fb + ui::kScreenW * ui::kScreenH);
    int firstChange = -1, lastChange = -1;
    for (size_t i = 0; i < events.size(); ++i) {
        if (measure && i + 1 == events.size()) {
            // Measure how long the screen keeps changing after the last input.
            const Event& e = events[i];
            uint32_t t0 = g_ms;
            if (e.kind == "tap" && e.v.size() >= 2) {
                g_touch.x = static_cast<int16_t>(e.v[0]);
                g_touch.y = static_cast<int16_t>(e.v[1]);
                g_touch.down = true;
                step(80);
                g_touch.down = false;
                t0 = g_ms;
            } else {
                runEvent(e);
                t0 = g_ms;
            }
            for (int t = 0; t < 3000; t += 5) {
                step(5);
                lv_refr_now(disp);
                if (std::memcmp(prev.data(), g_fb, sizeof g_fb) != 0) {
                    if (firstChange < 0) firstChange = static_cast<int>(g_ms - t0);
                    lastChange = static_cast<int>(g_ms - t0);
                    prev.assign(g_fb, g_fb + ui::kScreenW * ui::kScreenH);
                }
            }
        } else {
            runEvent(events[i]);
            prev.assign(g_fb, g_fb + ui::kScreenW * ui::kScreenH);
        }
    }
    if (scrollY >= 0) ui::scrollBodyTo(scrollY);
    step(advance + 600);
    lv_refr_now(disp);

    if (measure) {
        int dur = firstChange < 0 ? 0 : lastChange - firstChange + 5;
        std::printf("{\"first_change_ms\":%d,\"last_change_ms\":%d,\"duration_ms\":%d}\n", firstChange, lastChange,
                    firstChange < 0 ? 0 : dur);
    }
    std::printf("screen=%s depth=%zu snapshot=%s\n", ui::currentScreen().c_str(), ui::navDepth(), ui::pack().id().c_str());

    if (!regions.empty()) {
        std::vector<std::string> items;
        collectLabels(lv_screen_active(), items);
        collectLabels(lv_layer_top(), items);
        std::ofstream f(regions);
        f << "[";
        for (size_t i = 0; i < items.size(); ++i) f << (i ? ",\n" : "\n") << items[i];
        f << "\n]\n";
    }
    if (!out.empty() && !writePng(out)) {
        std::fprintf(stderr, "could not write %s\n", out.c_str());
        return 1;
    }
    return 0;
}
