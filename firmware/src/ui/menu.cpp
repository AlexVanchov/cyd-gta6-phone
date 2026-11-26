// Hidden maintenance menu: hold the status bar (top edge) for 3 s.
// This is the one UI element that is not from the game (DEVIATIONS.md). It uses
// LVGL's built-in Montserrat 14 font and plain styling.
#include "ui/platform.h"
#include "ui/ui.h"

namespace ui {

namespace {

lv_obj_t* g_menu = nullptr;
lv_obj_t* g_list = nullptr;
lv_obj_t* g_status = nullptr;

lv_obj_t* panel(lv_obj_t* parent) {
    lv_obj_t* o = lv_obj_create(parent);
    lv_obj_remove_style_all(o);
    lv_obj_set_scrollbar_mode(o, LV_SCROLLBAR_MODE_OFF);
    return o;
}

void setStatus(const std::string& s) {
    if (g_status) lv_label_set_text(g_status, s.c_str());
}

using Handler = void (*)(const std::string& arg);

struct Item {
    Handler fn;
    std::string arg;
};

void onItem(lv_event_t* e) {
    auto* it = static_cast<Item*>(lv_event_get_user_data(e));
    if (it && it->fn) it->fn(it->arg);
}

void onItemDelete(lv_event_t* e) { delete static_cast<Item*>(lv_event_get_user_data(e)); }

void addRow(const std::string& text, Handler fn, const std::string& arg = "", bool highlight = false) {
    lv_obj_t* b = panel(g_list);
    lv_obj_set_size(b, lv_pct(100), 34);
    lv_obj_set_style_bg_color(b, highlight ? lv_color_hex(0x2d5be3) : lv_color_hex(0x222222), 0);
    lv_obj_set_style_bg_color(b, lv_color_hex(0x444444), LV_STATE_PRESSED);
    lv_obj_set_style_bg_opa(b, LV_OPA_COVER, 0);
    lv_obj_set_style_radius(b, 6, 0);
    lv_obj_set_style_pad_left(b, 10, 0);
    lv_obj_add_flag(b, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_t* l = lv_label_create(b);
    lv_obj_set_style_text_color(l, lv_color_white(), 0);
    lv_obj_set_width(l, 200);
    lv_label_set_long_mode(l, LV_LABEL_LONG_DOT);
    lv_label_set_text(l, text.c_str());
    lv_obj_align(l, LV_ALIGN_LEFT_MID, 0, 0);
    auto* it = new Item{fn, arg};
    lv_obj_add_event_cb(b, onItem, LV_EVENT_CLICKED, it);
    lv_obj_add_event_cb(b, onItemDelete, LV_EVENT_DELETE, it);
}

void addHeading(const std::string& text) {
    lv_obj_t* l = lv_label_create(g_list);
    lv_obj_set_style_text_color(l, lv_color_hex(0x9a9a9a), 0);
    lv_obj_set_style_pad_top(l, 6, 0);
    lv_label_set_text(l, text.c_str());
}

void rebuild();

// ---- WiFi editor ----
lv_obj_t* g_wifi = nullptr;
lv_obj_t* g_ssid = nullptr;
lv_obj_t* g_pass = nullptr;
lv_obj_t* g_kb = nullptr;

void closeWifi() {
    if (g_wifi) lv_obj_delete(g_wifi);
    g_wifi = g_ssid = g_pass = g_kb = nullptr;
}

void onTaFocus(lv_event_t* e) {
    if (g_kb) lv_keyboard_set_textarea(g_kb, static_cast<lv_obj_t*>(lv_event_get_target(e)));
}

void onKb(lv_event_t* e) {
    lv_event_code_t code = lv_event_get_code(e);
    if (code == LV_EVENT_READY) {
        platform().setWifi(lv_textarea_get_text(g_ssid), lv_textarea_get_text(g_pass));
        closeWifi();
        rebuild();
        setStatus("Wi-Fi saved");
    } else if (code == LV_EVENT_CANCEL) {
        closeWifi();
    }
}

lv_obj_t* textarea(lv_obj_t* parent, const char* placeholder, bool password) {
    lv_obj_t* ta = lv_textarea_create(parent);
    lv_obj_set_size(ta, 220, 34);
    lv_textarea_set_one_line(ta, true);
    lv_textarea_set_placeholder_text(ta, placeholder);
    lv_textarea_set_password_mode(ta, password);
    lv_obj_set_style_bg_color(ta, lv_color_white(), 0);
    lv_obj_set_style_bg_opa(ta, LV_OPA_COVER, 0);
    lv_obj_set_style_pad_all(ta, 6, 0);
    lv_obj_set_style_border_width(ta, 2, LV_STATE_FOCUSED);
    lv_obj_set_style_border_color(ta, lv_color_hex(0x2d5be3), LV_STATE_FOCUSED);
    lv_obj_add_event_cb(ta, onTaFocus, LV_EVENT_FOCUSED, nullptr);
    lv_obj_add_event_cb(ta, onTaFocus, LV_EVENT_CLICKED, nullptr);
    return ta;
}

void openWifi(const std::string&) {
    g_wifi = panel(lv_layer_top());
    lv_obj_set_size(g_wifi, kScreenW, kScreenH);
    lv_obj_set_style_bg_color(g_wifi, lv_color_hex(0x111111), 0);
    lv_obj_set_style_bg_opa(g_wifi, LV_OPA_COVER, 0);
    lv_obj_add_flag(g_wifi, LV_OBJ_FLAG_CLICKABLE);
    g_ssid = textarea(g_wifi, "Wi-Fi name (SSID)", false);
    lv_obj_set_pos(g_ssid, 10, 8);
    lv_textarea_set_text(g_ssid, platform().wifiSsid().c_str());
    g_pass = textarea(g_wifi, "Password", false);
    lv_obj_set_pos(g_pass, 10, 48);
    g_kb = lv_keyboard_create(g_wifi);
    lv_obj_set_size(g_kb, kScreenW, 230);
    lv_obj_align(g_kb, LV_ALIGN_BOTTOM_MID, 0, 0);
    lv_obj_set_style_bg_color(g_kb, lv_color_hex(0x222222), 0);
    lv_obj_set_style_bg_opa(g_kb, LV_OPA_COVER, 0);
    lv_obj_set_style_bg_color(g_kb, lv_color_hex(0x444444), LV_PART_ITEMS);
    lv_obj_set_style_bg_opa(g_kb, LV_OPA_COVER, LV_PART_ITEMS);
    lv_obj_set_style_text_color(g_kb, lv_color_white(), LV_PART_ITEMS);
    lv_obj_set_style_radius(g_kb, 4, LV_PART_ITEMS);
    lv_obj_set_style_pad_all(g_kb, 3, 0);
    lv_obj_set_style_pad_gap(g_kb, 3, 0);
    lv_keyboard_set_textarea(g_kb, g_ssid);
    lv_obj_add_event_cb(g_kb, onKb, LV_EVENT_ALL, nullptr);
}

// ---- actions ----
void doSnapshot(const std::string& id) {
    closeHiddenMenu();
    if (!switchSnapshot(id, true)) {
        openHiddenMenu();
        setStatus("Could not load " + id);
    }
}
void doCalibrate(const std::string&) {
    closeHiddenMenu();
    platform().calibrateTouch();
    lv_obj_invalidate(lv_screen_active());
}
void doHwTest(const std::string&) {
    closeHiddenMenu();
    platform().hardwareTest();
    lv_obj_invalidate(lv_screen_active());
}
void doMaint(const std::string&) {
    std::string info;
    setStatus("Starting upload mode...");
    lv_refr_now(nullptr);
    platform().startMaintenance(info);
    setStatus(info);
}
void doInvert(const std::string&) { platform().toggleDisplayInvert(); }
void doSwap(const std::string&) { platform().toggleDisplaySwapRB(); }
void doFit(const std::string&) {
    setFitMode(fitMode() == Fit::Width ? Fit::Letterbox : Fit::Width);
    std::string id = pack().id();
    closeHiddenMenu();
    if (!id.empty()) switchSnapshot(id, false);
}
void doReboot(const std::string&) { platform().reboot(); }
void doClose(const std::string&) { closeHiddenMenu(); }

void rebuild() {
    if (!g_list) return;
    lv_obj_clean(g_list);
    g_status = lv_label_create(g_list);
    lv_obj_set_width(g_status, lv_pct(100));
    lv_label_set_long_mode(g_status, LV_LABEL_LONG_WRAP);
    lv_obj_set_style_text_color(g_status, lv_color_hex(0xffd24a), 0);
    std::string info = platform().deviceInfo();
    lv_label_set_text(g_status, info.empty() ? "Maintenance" : info.c_str());

    addHeading("Snapshots");
    auto snaps = svc::Pack::listSnapshots();
    if (snaps.empty()) addHeading("  (none on SD card)");
    for (auto it = snaps.rbegin(); it != snaps.rend(); ++it) addRow(*it, doSnapshot, *it, *it == pack().id());
    addHeading("Device");
    addRow("Calibrate touch", doCalibrate);
    addRow("Hardware test screen", doHwTest);
    addRow("Invert colours", doInvert);
    addRow("Swap red/blue", doSwap);
    addRow(fitMode() == Fit::Width ? "Fit: width (tap: letterbox)" : "Fit: letterbox (tap: width)", doFit);
    addHeading("Wi-Fi / sync");
    std::string ssid = platform().wifiSsid();
    addRow("Wi-Fi: " + (ssid.empty() ? std::string("not set") : ssid), openWifi);
    addRow("Start upload mode", doMaint);
    addRow("Reboot", doReboot);
    addRow("Close", doClose);
}

}  // namespace

void openHiddenMenu() {
    if (g_menu) return;
    g_menu = panel(lv_layer_top());
    lv_obj_set_size(g_menu, kScreenW, kScreenH);
    lv_obj_set_style_bg_color(g_menu, lv_color_black(), 0);
    lv_obj_set_style_bg_opa(g_menu, LV_OPA_COVER, 0);
    lv_obj_add_flag(g_menu, LV_OBJ_FLAG_CLICKABLE);
    g_list = panel(g_menu);
    lv_obj_set_size(g_list, kScreenW, kScreenH);
    lv_obj_set_style_pad_all(g_list, 8, 0);
    lv_obj_set_style_pad_row(g_list, 5, 0);
    lv_obj_set_flex_flow(g_list, LV_FLEX_FLOW_COLUMN);
    lv_obj_add_flag(g_list, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_set_scroll_dir(g_list, LV_DIR_VER);
    rebuild();
    platform().log("hidden menu opened");
}

void closeHiddenMenu() {
    closeWifi();
    if (!g_menu) return;
    platform().stopMaintenance();
    lv_obj_delete(g_menu);
    g_menu = g_list = g_status = nullptr;
}

bool hiddenMenuOpen() { return g_menu != nullptr; }

}  // namespace ui
