#include "services/net.h"

#include <ArduinoJson.h>
#include <ESPmDNS.h>
#include <Preferences.h>
#include <SD.h>
#include <WebServer.h>
#include <WiFi.h>

#include "ui/ui.h"

namespace svc {

namespace {

WebServer* g_server = nullptr;
File g_upload;
String g_uploadPath;
bool g_uploadOk = false;

bool mkdirs(const String& path) {
    // Create every parent directory of path (path is a file or dir path).
    int from = 1;
    while (true) {
        int slash = path.indexOf('/', from);
        if (slash < 0) break;
        String d = path.substring(0, slash);
        if (!SD.exists(d) && !SD.mkdir(d)) return false;
        from = slash + 1;
    }
    return true;
}

bool rmrf(const String& path) {
    File f = SD.open(path);
    if (!f) return false;
    if (!f.isDirectory()) {
        f.close();
        return SD.remove(path);
    }
    while (true) {
        File c = f.openNextFile();
        if (!c) break;
        String child = path + "/" + String(c.name()).substring(String(c.name()).lastIndexOf('/') + 1);
        c.close();
        rmrf(child);
    }
    f.close();
    return SD.rmdir(path);
}

bool safePath(const String& p) { return p.startsWith("/") && p.indexOf("..") < 0; }

void sendJson(int code, JsonDocument& d) {
    String out;
    serializeJson(d, out);
    g_server->send(code, "application/json", out);
}

void handleInfo() {
    JsonDocument d;
    d["device"] = "cyd-phone";
    d["snapshot"] = ui::pack().id().c_str();
    d["screen"] = ui::currentScreen().c_str();
    d["heap_free"] = ESP.getFreeHeap();
    d["sd_total"] = SD.totalBytes();
    d["sd_used"] = SD.usedBytes();
    JsonArray packs = d["packs"].to<JsonArray>();
    for (const auto& p : Pack::listSnapshots()) packs.add(p.c_str());
    sendJson(200, d);
}

void handleLs() {
    String path = g_server->arg("path");
    if (path.isEmpty()) path = "/";
    JsonDocument d;
    if (!safePath(path)) {
        d["error"] = "bad path";
        return sendJson(400, d);
    }
    File dir = SD.open(path);
    if (!dir || !dir.isDirectory()) {
        d["error"] = "not a directory";
        return sendJson(404, d);
    }
    JsonArray arr = d["entries"].to<JsonArray>();
    while (File f = dir.openNextFile()) {
        JsonObject e = arr.add<JsonObject>();
        String n = f.name();
        e["name"] = n.substring(n.lastIndexOf('/') + 1);
        e["dir"] = f.isDirectory();
        e["size"] = f.size();
        f.close();
    }
    sendJson(200, d);
}

void handleUploadData() {
    HTTPUpload& up = g_server->upload();
    if (up.status == UPLOAD_FILE_START) {
        g_uploadPath = g_server->arg("path");
        g_uploadOk = safePath(g_uploadPath) && mkdirs(g_uploadPath);
        if (g_uploadOk) {
            if (SD.exists(g_uploadPath)) SD.remove(g_uploadPath);
            g_upload = SD.open(g_uploadPath, FILE_WRITE);
            g_uploadOk = static_cast<bool>(g_upload);
        }
    } else if (up.status == UPLOAD_FILE_WRITE) {
        if (g_uploadOk && g_upload.write(up.buf, up.currentSize) != up.currentSize) g_uploadOk = false;
    } else if (up.status == UPLOAD_FILE_END || up.status == UPLOAD_FILE_ABORTED) {
        if (g_upload) g_upload.close();
        if (up.status == UPLOAD_FILE_ABORTED) g_uploadOk = false;
    }
}

void handleUploadDone() {
    JsonDocument d;
    d["path"] = g_uploadPath;
    d["ok"] = g_uploadOk;
    sendJson(g_uploadOk ? 200 : 500, d);
}

void handleMkdir() {
    String p = g_server->arg("path");
    JsonDocument d;
    d["ok"] = safePath(p) && mkdirs(p + "/");
    sendJson(d["ok"] ? 200 : 400, d);
}

void handleRm() {
    String p = g_server->arg("path");
    JsonDocument d;
    d["ok"] = safePath(p) && p != "/" && rmrf(p);
    sendJson(d["ok"] ? 200 : 400, d);
}

void handleReboot() {
    g_server->send(200, "application/json", "{\"ok\":true}");
    delay(200);
    ESP.restart();
}

}  // namespace

void Net::loadCredentials() {
    Preferences p;
    p.begin("wifi", false);
    ssid_ = p.isKey("ssid") ? p.getString("ssid", "") : "";
    pass_ = p.isKey("pass") ? p.getString("pass", "") : "";
    p.end();
}

void Net::setCredentials(const String& ssid, const String& pass) {
    Preferences p;
    p.begin("wifi", false);
    p.putString("ssid", ssid);
    p.putString("pass", pass);
    p.end();
    ssid_ = ssid;
    pass_ = pass;
}

bool Net::importFromSd() {
    const char* path = "/config/wifi.json";
    if (!SD.exists(path)) return false;
    File f = SD.open(path);
    JsonDocument d;
    DeserializationError e = deserializeJson(d, f);
    f.close();
    if (e || !d["ssid"].is<const char*>()) return false;
    setCredentials(d["ssid"].as<const char*>(), d["password"] | "");
    // Don't leave the password readable on the card.
    SD.remove("/config/wifi.json.imported");
    SD.rename(path, "/config/wifi.json.imported");
    File g = SD.open("/config/wifi.json.imported", FILE_WRITE);
    if (g) {
        g.print("{\"ssid\":\"");
        g.print(ssid_);
        g.print("\",\"password\":\"(imported into device memory)\"}\n");
        g.close();
    }
    return true;
}

bool Net::startMaintenance(String& info, uint32_t timeoutMs) {
    if (active_) {
        info = "Upload mode: http://" + WiFi.localIP().toString() + "/";
        return true;
    }
    if (ssid_.isEmpty()) {
        info = "Set Wi-Fi first";
        return false;
    }
    WiFi.mode(WIFI_STA);
    WiFi.setHostname("cyd-phone");
    WiFi.begin(ssid_.c_str(), pass_.c_str());
    uint32_t t0 = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - t0 < timeoutMs) delay(100);
    if (WiFi.status() != WL_CONNECTED) {
        WiFi.disconnect(true);
        WiFi.mode(WIFI_OFF);
        info = "Wi-Fi connect failed (" + ssid_ + ")";
        return false;
    }
    MDNS.begin("cyd-phone");
    g_server = new WebServer(80);
    g_server->on("/api/info", HTTP_GET, handleInfo);
    g_server->on("/api/ls", HTTP_GET, handleLs);
    g_server->on("/api/upload", HTTP_POST, handleUploadDone, handleUploadData);
    g_server->on("/api/mkdir", HTTP_POST, handleMkdir);
    g_server->on("/api/rm", HTTP_POST, handleRm);
    g_server->on("/api/reboot", HTTP_POST, handleReboot);
    g_server->begin();
    MDNS.addService("http", "tcp", 80);
    active_ = true;
    info = "Upload mode: http://" + WiFi.localIP().toString() + "/ (cyd-phone.local)";
    Serial.println(info);
    return true;
}

void Net::stop() {
    if (!active_) return;
    g_server->stop();
    delete g_server;
    g_server = nullptr;
    MDNS.end();
    WiFi.disconnect(true);
    WiFi.mode(WIFI_OFF);
    active_ = false;
}

void Net::loop() {
    if (g_server) g_server->handleClient();
}

Net& net() {
    static Net n;
    return n;
}

}  // namespace svc
