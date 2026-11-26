// Shared UI core: turns content packs into LVGL screens. Compiles unchanged for
// the device and the simulator; everything platform-specific goes through
// ui::Platform (platform.h).
#pragma once
#include <ArduinoJson.h>
#include <lvgl.h>

#include <string>
#include <vector>

#include "services/clock.h"
#include "services/pack.h"
#include "services/timeline.h"

namespace ui {

constexpr int kScreenW = 240;
constexpr int kScreenH = 320;
// Tap targets smaller than this get an invisible enlarged hit area (PLAN.md §7).
constexpr int kMinTapPx = 28;

enum class Fit { Width, Letterbox };

// ---- lifecycle ----
// Call once after lv_init() and display creation. Creates the touch input
// device, loads the selected/newest snapshot and shows its boot screen.
void begin(lv_display_t* disp);
// Call from the main loop (after lv_timer_handler) to run sleep/brightness logic.
void loop();

// ---- snapshots ----
bool switchSnapshot(const std::string& id, bool persist);
const svc::Pack& pack();
const svc::Timeline& timeline();
const svc::GameClock& gameClock();
std::string clockText(const std::string& fmt);

// ---- navigation ----
enum class NavKind { None, OpenApp, Push, Pop, CloseApp };
bool openScreen(const std::string& screenId, NavKind kind = NavKind::Push);
void back();
void home();
std::string currentScreen();
size_t navDepth();
// Scroll the current screen's body region (simulator/diff use).
bool scrollBodyTo(int y);
bool transitionActive();

// ---- settings ----
Fit fitMode();
void setFitMode(Fit f);

// ---- hidden menu (maintenance; the one allowed addition, see DEVIATIONS.md) ----
void openHiddenMenu();
void closeHiddenMenu();
bool hiddenMenuOpen();

// ---- internals shared between ui/*.cpp ----
namespace detail {

struct ParsedColor {
    bool ok = false;
    lv_color_t color{};
    lv_opa_t opa = LV_OPA_COVER;
};
ParsedColor parseColor(JsonVariantConst v);  // "#RRGGBB", "#RRGGBBAA" or "$token.path"
const lv_font_t* font(const std::string& id);
void clearFonts();
std::string lvPath(const std::string& appDir, const std::string& src);

struct BuildCtx {
    float scale = 1.0f;
    std::string appDir;
    std::string screenId;
};
int px(const BuildCtx& c, float unit);
// Build one element (and its children) under parent. ox/oy: parent's origin in
// unit coordinates (element coordinates are absolute within the captured screen).
lv_obj_t* buildElement(JsonObjectConst e, lv_obj_t* parent, const BuildCtx& c, float ox, float oy);
// Build a whole screen into page (240x320). Returns false with err on failure.
bool buildScreen(const std::string& screenId, lv_obj_t* page, std::string& err, int& statusBarPx);

// Clock-bound labels are refreshed every second.
void bindClock(lv_obj_t* label, const std::string& fmt);
void refreshClockLabels();

// Video
void videoAttach(lv_obj_t* img, const std::string& lvSrc, bool autoplay, bool loop);
void videoPlay(lv_obj_t* img);
void videoStopAll();

// Actions
void runAction(JsonObjectConst action, lv_obj_t* source);
lv_obj_t* findById(lv_obj_t* root, const std::string& id);

void showMessage(const std::string& text);  // system message page (no pack / errors)
lv_obj_t* stage();

}  // namespace detail
}  // namespace ui
