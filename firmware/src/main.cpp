// GTA 6 phone replica - device entry point.
//
// Boot: display, backlight, touch, SD. On first boot (no touch calibration in
// NVS) or when the BOOT button is held, the hardware test screen runs, then
// touch calibration. Then LVGL starts and the UI loads the newest snapshot.
//
// The serial port (115200) accepts maintenance commands, used for testing
// without touching the screen:
//   INFO | SHOT | TAP x y | HOLD x y ms | SWIPE x1 y1 x2 y2 ms | SCREEN app/screen
//   SNAP id | BACK | HOME | MENU | SKIP (leave test/calibration) | REBOOT
#include <Arduino.h>
#include <Preferences.h>
#include <SD.h>
#include <esp_heap_caps.h>
#include <lvgl.h>

#include <deque>

#include "hal/board.h"
#include "hal/display.h"
#include "hal/touch.h"
#include "services/net.h"
#include "ui/platform.h"
#include "ui/ui.h"

using hal::display;
using hal::touch;

namespace {

constexpr int kPinBoot = 0;
constexpr int kBufLines = 40;

Preferences g_prefs;
volatile bool g_skip = false;
String g_serialLine;

// ---------------------------------------------------------------- injected input

struct InjectStep {
    bool down;
    int16_t x, y;
    uint32_t ms;
};
std::deque<InjectStep> g_inject;
uint32_t g_injectUntil = 0;
bool g_injectDown = false;
int16_t g_injectX = 0, g_injectY = 0;

bool injected(int16_t& x, int16_t& y, bool& down) {
    uint32_t now = millis();
    if (g_injectUntil && now < g_injectUntil) {
        x = g_injectX;
        y = g_injectY;
        down = g_injectDown;
        return true;
    }
    if (g_inject.empty()) {
        g_injectUntil = 0;
        return false;
    }
    InjectStep s = g_inject.front();
    g_inject.pop_front();
    g_injectDown = s.down;
    g_injectX = s.x;
    g_injectY = s.y;
    g_injectUntil = now + s.ms;
    x = s.x;
    y = s.y;
    down = s.down;
    return true;
}

// ---------------------------------------------------------------- settings

void saveCal(const hal::TouchCal& c) {
    g_prefs.putBytes("cal", &c, sizeof c);
}

bool loadCal(hal::TouchCal& c) {
    if (!g_prefs.isKey("cal") || g_prefs.getBytesLength("cal") != sizeof c) return false;
    g_prefs.getBytes("cal", &c, sizeof c);
    return c.valid;
}

void applyDisplayOptions() {
    display().applyColourOptions(g_prefs.getBool("invert", false), g_prefs.getBool("swaprb", false));
}

// ---------------------------------------------------------------- system screens (LovyanGFX, not LVGL)

void waitRelease() {
    uint16_t x, y, z;
    while (touch().readRaw(x, y, z)) delay(10);
    delay(60);
}

void drawTestScreen() {
    auto& d = display();
    d.fillScreen(TFT_BLACK);
    // Colour bars: if these labels don't match their colours, flash the other variant
    // or use the menu's invert / swap options.
    struct Bar { uint16_t c; const char* name; uint16_t text; };
    const Bar bars[] = {{TFT_RED, "RED", TFT_WHITE}, {TFT_GREEN, "GREEN", TFT_BLACK}, {TFT_BLUE, "BLUE", TFT_WHITE},
                        {TFT_WHITE, "WHITE", TFT_BLACK}, {TFT_YELLOW, "YELLOW", TFT_BLACK}};
    for (int i = 0; i < 5; ++i) {
        d.fillRect(0, i * 24, 240, 24, bars[i].c);
        d.setTextColor(bars[i].text);
        d.setTextDatum(middle_center);
        d.setFont(&fonts::Font2);
        d.drawString(bars[i].name, 120, i * 24 + 12);
    }
    for (int x = 0; x < 240; ++x) d.drawFastVLine(x, 120, 12, d.color565(x * 255 / 239, x * 255 / 239, x * 255 / 239));
    d.setTextDatum(top_left);
    d.setTextColor(TFT_WHITE, TFT_BLACK);
    d.setFont(&fonts::Font0);
    int y = 140;
    auto line = [&](const String& s) {
        d.drawString(s, 6, y);
        y += 12;
    };
    line(String("Firmware: ") + hal::panelName() + " build " __DATE__);
    line("Panel ID " + hal::readPanelId());
    if (strcmp(hal::detectedPanel(), hal::panelName()) != 0 && strcmp(hal::detectedPanel(), "unknown") != 0)
        line(String("WRONG FIRMWARE: flash the ") + hal::detectedPanel() + " build");
    if (hal::sdMounted()) {
        line("SD: " + String((uint32_t)(hal::sdUsedBytes() >> 20)) + " / " +
             String((uint32_t)(hal::sdTotalBytes() >> 20)) + " MB");
        auto packs = svc::Pack::listSnapshots();
        line("Packs on SD: " + String((int)packs.size()));
    } else {
        line("SD: NOT FOUND (FAT32 card in slot?)");
    }
    line("Free heap: " + String(ESP.getFreeHeap() / 1024) + " KB");
    d.setTextColor(TFT_YELLOW, TFT_BLACK);
    d.drawString("Colours wrong? Flash the other", 6, 268);
    d.drawString("variant (README) or use the menu.", 6, 280);
    d.setTextColor(TFT_WHITE, TFT_BLACK);
    d.setTextDatum(bottom_center);
    d.setFont(&fonts::Font2);
    d.drawString("Tap anywhere to continue", 120, 318);
    d.setTextDatum(top_left);
}

void serialPoll();

void hardwareTest() {
    drawTestScreen();
    uint32_t t0 = millis(), lastInfo = 0;
    int ledStep = 0;
    g_skip = false;
    auto& d = display();
    d.setFont(&fonts::Font0);
    while (!g_skip) {
        uint16_t x, y, z;
        bool down = touch().readRaw(x, y, z);
        if (millis() - lastInfo > 200) {
            lastInfo = millis();
            d.setTextColor(TFT_CYAN, TFT_BLACK);
            char b[64];
            snprintf(b, sizeof b, "Touch raw %4u %4u z%4u  Light %4d   ", down ? x : 0, down ? y : 0, down ? z : 0,
                     hal::lightRaw());
            d.drawString(b, 6, 236);
            ledStep = (ledStep + 1) % 12;
            hal::led(ledStep / 4 == 0, ledStep / 4 == 1, ledStep / 4 == 2);
        }
        if (down && millis() - t0 > 500) {
            waitRelease();
            break;
        }
        serialPoll();
        delay(10);
    }
    hal::led(false, false, false);
}

void drawCross(int x, int y, uint16_t c) {
    auto& d = display();
    d.drawFastHLine(x - 10, y, 21, c);
    d.drawFastVLine(x, y - 10, 21, c);
    d.drawCircle(x, y, 4, c);
}

void calibrate() {
    auto& d = display();
    const int tx[5] = {20, 220, 220, 20, 120};
    const int ty[5] = {20, 20, 300, 300, 160};
    float rx[5], ry[5], sx[5], sy[5];
    g_skip = false;
    for (int i = 0; i < 5 && !g_skip; ++i) {
        d.fillScreen(TFT_BLACK);
        d.setTextColor(TFT_WHITE, TFT_BLACK);
        d.setFont(&fonts::Font2);
        d.setTextDatum(middle_center);
        d.drawString("Touch calibration", 120, 120);
        d.drawString(String("Tap the cross (") + (i + 1) + "/5)", 120, 140);
        d.setTextDatum(top_left);
        drawCross(tx[i], ty[i], TFT_YELLOW);
        // Collect a steady press.
        uint32_t sumX = 0, sumY = 0, n = 0;
        while (!g_skip) {
            uint16_t x, y, z;
            if (touch().readRaw(x, y, z)) {
                delay(40);
                while (touch().readRaw(x, y, z) && n < 64) {
                    sumX += x;
                    sumY += y;
                    ++n;
                    delay(8);
                }
                if (n >= 8) break;
                sumX = sumY = n = 0;
            }
            serialPoll();
            delay(10);
        }
        if (g_skip) break;
        rx[i] = static_cast<float>(sumX) / n;
        ry[i] = static_cast<float>(sumY) / n;
        sx[i] = tx[i];
        sy[i] = ty[i];
        drawCross(tx[i], ty[i], TFT_GREEN);
        waitRelease();
    }
    if (g_skip) return;
    hal::TouchCal c = hal::Touch::fit(rx, ry, sx, sy, 5);
    if (c.valid) {
        touch().setCalibration(c);
        saveCal(c);
    }
    d.fillScreen(TFT_BLACK);
    d.setTextDatum(middle_center);
    d.drawString(c.valid ? "Calibration saved" : "Calibration failed", 120, 160);
    d.setTextDatum(top_left);
    Serial.printf("calibration %s: x=%.4f*rx%+.4f*ry%+.1f  y=%.4f*rx%+.4f*ry%+.1f\n", c.valid ? "saved" : "failed",
                  c.ax, c.bx, c.cx, c.ay, c.by, c.cy);
    delay(700);
}

// ---------------------------------------------------------------- platform

class DevicePlatform : public ui::Platform {
public:
    std::string lvRoot() const override { return "S:"; }
    bool readFile(const std::string& path, std::string& out) override {
        File f = SD.open(path.c_str());
        if (!f || f.isDirectory()) return false;
        size_t n = f.size();
        out.resize(n);
        size_t got = f.read(reinterpret_cast<uint8_t*>(&out[0]), n);
        f.close();
        return got == n;
    }
    bool isDir(const std::string& path) override {
        File f = SD.open(path.c_str());
        bool r = f && f.isDirectory();
        if (f) f.close();
        return r;
    }
    bool isFile(const std::string& path) override {
        File f = SD.open(path.c_str());
        bool r = f && !f.isDirectory();
        if (f) f.close();
        return r;
    }
    std::vector<std::string> listDirs(const std::string& path) override {
        std::vector<std::string> out;
        File d = SD.open(path.c_str());
        if (!d || !d.isDirectory()) return out;
        while (File f = d.openNextFile()) {
            if (f.isDirectory()) {
                String n = f.name();
                out.push_back(n.substring(n.lastIndexOf('/') + 1).c_str());
            }
            f.close();
        }
        d.close();
        return out;
    }
    std::string getSetting(const std::string& k, const std::string& def) override {
        if (!g_prefs.isKey(k.c_str())) return def;
        return g_prefs.getString(k.c_str(), def.c_str()).c_str();
    }
    void setSetting(const std::string& k, const std::string& v) override {
        g_prefs.putString(k.c_str(), v.c_str());
        if (k == "auto_bl") autoBl_ = v == "1";
    }
    void loadCached() { autoBl_ = getSetting("auto_bl", "1") == "1"; }
    bool readPointer(int16_t& x, int16_t& y) override {
        bool down;
        if (injected(x, y, down)) return down;
        return touch().read(x, y);
    }
    void setBacklight(uint8_t level) override { hal::setBacklight(level); }
    uint8_t autoBrightness() override {
        // LDR: higher reading = darker. Smoothed, mapped to 60..255, steps of 8
        // so the backlight does not flicker.
        static float avg = -1;
        static uint32_t last = 0;
        static uint8_t level = 255;
        if (!autoBl_) return 255;
        if (millis() - last < 250) return level;
        last = millis();
        int raw = hal::lightRaw();
        avg = avg < 0 ? raw : avg * 0.9f + raw * 0.1f;
        float t = avg <= 50 ? 0.0f : avg >= 1500 ? 1.0f : (avg - 50) / 1450.0f;
        uint8_t target = static_cast<uint8_t>(255 - t * 195);
        target &= 0xF8;
        level = target;
        return level;
    }
    void calibrateTouch() override { calibrate(); }
    void hardwareTest() override {
        hardwareTest_();
    }
    void setWifi(const std::string& ssid, const std::string& pass) override {
        svc::net().setCredentials(ssid.c_str(), pass.c_str());
    }
    std::string wifiSsid() override { return svc::net().ssid().c_str(); }
    bool startMaintenance(std::string& info) override {
        String s;
        bool ok = svc::net().startMaintenance(s);
        info = s.c_str();
        return ok;
    }
    void stopMaintenance() override { svc::net().stop(); }
    void toggleDisplayInvert() override {
        g_prefs.putBool("invert", !g_prefs.getBool("invert", false));
        applyDisplayOptions();
    }
    void toggleDisplaySwapRB() override {
        g_prefs.putBool("swaprb", !g_prefs.getBool("swaprb", false));
        applyDisplayOptions();
        lv_obj_invalidate(lv_screen_active());
    }
    void reboot() override { ESP.restart(); }
    std::string deviceInfo() override {
        char b[96];
        snprintf(b, sizeof b, "%s | heap %u KB | SD %s", hal::panelName(), ESP.getFreeHeap() / 1024,
                 hal::sdMounted() ? "ok" : "missing");
        return b;
    }
    void log(const std::string& msg) override { Serial.printf("[ui] %s\n", msg.c_str()); }

private:
    static void hardwareTest_() { ::hardwareTest(); }
    bool autoBl_ = true;
};

DevicePlatform g_platform;

// ---------------------------------------------------------------- LVGL glue

void flushCb(lv_display_t* disp, const lv_area_t* a, uint8_t* px) {
    auto& d = display();
    uint32_t w = lv_area_get_width(a), h = lv_area_get_height(a);
    d.startWrite();
    d.setAddrWindow(a->x1, a->y1, w, h);
    d.writePixels(reinterpret_cast<uint16_t*>(px), w * h, true);
    d.endWrite();
    lv_display_flush_ready(disp);
}

uint32_t tickCb() { return millis(); }

void lvglLog(lv_log_level_t level, const char* buf) {
    (void)level;
    Serial.print(buf);
}

// ---------------------------------------------------------------- serial maintenance

void shot() {
    // Reads the panel's memory back over MISO: the actual pixels on the glass.
    auto& d = display();
    Serial.printf("SHOT 240 320 RGB888\n");
    static lgfx::rgb888_t line[240];
    for (int y = 0; y < 320; ++y) {
        d.readRect(0, y, 240, 1, line);
        Serial.write(reinterpret_cast<uint8_t*>(line), sizeof line);
    }
    Serial.printf("\nEND\n");
}

void queueTap(int x, int y, uint32_t ms = 80) {
    g_inject.push_back({true, (int16_t)x, (int16_t)y, ms});
    g_inject.push_back({false, (int16_t)x, (int16_t)y, 60});
}

void handleCommand(String cmd) {
    cmd.trim();
    if (cmd.isEmpty()) return;
    int a, b, c, dd, e;
    char s[96];
    if (cmd == "INFO") {
        Serial.printf("INFO panel=%s detected=%s heap=%u min_heap=%u largest=%u sd=%d snapshot=%s screen=%s cal=%d\n",
                      hal::panelName(), hal::detectedPanel(), ESP.getFreeHeap(), ESP.getMinFreeHeap(),
                      heap_caps_get_largest_free_block(MALLOC_CAP_8BIT), hal::sdMounted(), ui::pack().id().c_str(),
                      ui::currentScreen().c_str(), touch().calibration().valid);
    } else if (cmd == "SHOT") {
        shot();
    } else if (sscanf(cmd.c_str(), "TAP %d %d", &a, &b) == 2) {
        queueTap(a, b);
    } else if (sscanf(cmd.c_str(), "HOLD %d %d %d", &a, &b, &c) == 3) {
        g_inject.push_back({true, (int16_t)a, (int16_t)b, (uint32_t)c});
        g_inject.push_back({false, (int16_t)a, (int16_t)b, 60});
    } else if (sscanf(cmd.c_str(), "SWIPE %d %d %d %d %d", &a, &b, &c, &dd, &e) == 5) {
        int steps = e / 15 > 0 ? e / 15 : 1;
        for (int i = 0; i <= steps; ++i)
            g_inject.push_back({true, (int16_t)(a + (c - a) * i / steps), (int16_t)(b + (dd - b) * i / steps), 15});
        g_inject.push_back({false, (int16_t)c, (int16_t)dd, 60});
    } else if (sscanf(cmd.c_str(), "SCREEN %95s", s) == 1) {
        Serial.printf("SCREEN %s\n", ui::openScreen(s) ? "ok" : "failed");
    } else if (sscanf(cmd.c_str(), "SNAP %95s", s) == 1) {
        Serial.printf("SNAP %s\n", ui::switchSnapshot(s, true) ? "ok" : "failed");
    } else if (cmd == "BACK") {
        ui::back();
    } else if (cmd == "HOME") {
        ui::home();
    } else if (cmd == "MENU") {
        ui::openHiddenMenu();
    } else if (cmd == "SKIP") {
        g_skip = true;
    } else if (cmd == "REBOOT") {
        ESP.restart();
    } else {
        Serial.printf("ERR unknown command: %s\n", cmd.c_str());
    }
}

void serialPoll() {
    while (Serial.available()) {
        char ch = static_cast<char>(Serial.read());
        if (ch == '\n' || ch == '\r') {
            String c = g_serialLine;
            g_serialLine = "";
            handleCommand(c);
        } else if (g_serialLine.length() < 128) {
            g_serialLine += ch;
        }
    }
}

}  // namespace

void setup() {
    Serial.setRxBufferSize(512);
    Serial.begin(115200);
    delay(50);
    Serial.printf("\n[boot] cyd-phone %s build %s %s\n", hal::panelName(), __DATE__, __TIME__);
    pinMode(kPinBoot, INPUT_PULLUP);
    hal::ledBegin();
    hal::lightBegin();
    g_prefs.begin("phone", false);

    display().init();
    display().setRotation(0);
    applyDisplayOptions();
    display().fillScreen(TFT_BLACK);
    hal::backlightBegin();
    touch().begin();
    Serial.printf("[boot] panel id %s\n", hal::readPanelId().c_str());

    ui::setPlatform(&g_platform);
    g_platform.loadCached();
    bool sd = hal::sdBegin();
    Serial.printf("[boot] sd %s, %llu MB\n", sd ? "ok" : "MISSING", hal::sdTotalBytes() >> 20);
    svc::net().loadCredentials();
    if (sd && svc::net().importFromSd()) Serial.println("[boot] wifi credentials imported from SD");

    hal::TouchCal cal;
    bool haveCal = loadCal(cal);
    if (haveCal) touch().setCalibration(cal);
    if (!haveCal || digitalRead(kPinBoot) == LOW) {
        Serial.println("[boot] hardware test + calibration (send SKIP to leave)");
        hardwareTest();
        if (!g_skip) calibrate();
        g_skip = false;
    }

    lv_init();
    lv_tick_set_cb(tickCb);
    lv_log_register_print_cb(lvglLog);
    lv_display_t* disp = lv_display_create(240, 320);
    size_t bytes = 240 * kBufLines * 2;
    void* buf = heap_caps_malloc(bytes, MALLOC_CAP_DMA | MALLOC_CAP_8BIT);
    lv_display_set_buffers(disp, buf, nullptr, bytes, LV_DISPLAY_RENDER_MODE_PARTIAL);
    lv_display_set_flush_cb(disp, flushCb);

    ui::begin(disp);
    Serial.printf("[boot] ui ready in %lu ms, heap %u KB free\n", millis(), ESP.getFreeHeap() / 1024);
}

void loop() {
    lv_timer_handler();
    ui::loop();
    svc::net().loop();
    serialPoll();
    delay(2);
}
