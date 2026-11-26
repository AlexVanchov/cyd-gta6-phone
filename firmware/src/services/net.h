// WiFi manager and the maintenance-mode upload endpoint (device only).
//
// Credentials live in NVS and are set from the hidden menu (or imported once
// from /config/wifi.json on the SD card). WiFi is off in normal use; it is
// only started for maintenance mode so the radio never costs RAM or power
// while showing the phone.
//
// HTTP API (port 80, mDNS name cyd-phone.local) used by tools/sync.py:
//   GET  /api/info                 device, snapshot, SD usage
//   GET  /api/ls?path=/packs       directory listing (JSON)
//   POST /api/upload?path=/x/y     multipart upload, streamed to SD (dirs created)
//   POST /api/mkdir?path=/x
//   POST /api/rm?path=/x           recursive delete
//   POST /api/reboot
#pragma once
#include <Arduino.h>

namespace svc {

class Net {
public:
    void loadCredentials();
    bool importFromSd();  // /config/wifi.json {"ssid": "...", "password": "..."}
    void setCredentials(const String& ssid, const String& pass);
    const String& ssid() const { return ssid_; }
    // Connects (blocking, up to timeoutMs) and starts the HTTP server.
    bool startMaintenance(String& info, uint32_t timeoutMs = 15000);
    void stop();
    bool active() const { return active_; }
    void loop();

private:
    String ssid_, pass_;
    bool active_ = false;
};

Net& net();

}  // namespace svc
