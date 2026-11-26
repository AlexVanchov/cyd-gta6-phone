// Platform interface: everything the shared UI code needs from the outside
// world. The device firmware (src/platform_device.cpp) and the PC simulator
// (simulator/platform_sim.cpp) each provide one implementation, so src/ui and
// the portable services compile unchanged for both targets.
#pragma once
#include <cstdint>
#include <string>
#include <vector>

namespace ui {

class Platform {
public:
    virtual ~Platform() = default;

    // ---- storage (paths are absolute from the SD card root, e.g. "/packs/x") ----
    // Prefix that turns an SD path into an LVGL path: "S:" on the device,
    // "S:/abs/path/to/sd" in the simulator.
    virtual std::string lvRoot() const = 0;
    virtual bool readFile(const std::string& path, std::string& out) = 0;
    virtual bool isDir(const std::string& path) = 0;
    virtual bool isFile(const std::string& path) = 0;
    virtual std::vector<std::string> listDirs(const std::string& path) = 0;

    // ---- persistent settings (NVS on the device) ----
    virtual std::string getSetting(const std::string& key, const std::string& def) = 0;
    virtual void setSetting(const std::string& key, const std::string& value) = 0;

    // ---- input / output ----
    // Calibrated touch point in screen pixels. Returns true while pressed.
    virtual bool readPointer(int16_t& x, int16_t& y) = 0;
    virtual void setBacklight(uint8_t level) { (void)level; }
    virtual uint8_t autoBrightness() { return 255; }

    // ---- maintenance actions offered by the hidden menu ----
    virtual void calibrateTouch() {}
    virtual void hardwareTest() {}
    virtual void setWifi(const std::string& ssid, const std::string& pass) { (void)ssid; (void)pass; }
    virtual std::string wifiSsid() { return ""; }
    virtual bool startMaintenance(std::string& info) { info = "not available"; return false; }
    virtual void stopMaintenance() {}
    virtual void toggleDisplayInvert() {}
    virtual void toggleDisplaySwapRB() {}
    virtual void reboot() {}
    virtual std::string deviceInfo() { return ""; }

    virtual void log(const std::string& msg) = 0;
};

void setPlatform(Platform* p);
Platform& platform();

}  // namespace ui
