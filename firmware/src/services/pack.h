// Content pack loader: snapshots, parent inheritance, manifest merge, screen
// lookup. Portable (used by the device and the simulator).
#pragma once
#include <ArduinoJson.h>
#include <string>
#include <vector>

namespace svc {

class Pack {
public:
    // Snapshot ids found in /packs (directories containing manifest.json), sorted ascending.
    static std::vector<std::string> listSnapshots();
    // Newest snapshot = greatest id (ids start with the real capture date).
    static std::string newest();

    bool load(const std::string& snapshotId, std::string& err);
    bool loaded() const { return !chain_.empty(); }
    const std::string& id() const { return id_; }
    // Snapshot ids from this one up through its parents.
    const std::vector<std::string>& chain() const { return chain_; }

    // Merged manifest (parents first, children override).
    JsonObjectConst manifest() const { return manifest_.as<JsonObjectConst>(); }

    // Directory of an app: the first snapshot in the chain that has apps/<app>/.
    // Returns "" if no snapshot has it.
    std::string appDir(const std::string& app) const;
    // Resolve a pack-relative file (e.g. "fonts/x.bin") through the chain.
    std::string resolveFile(const std::string& rel) const;

    // Load "<app>/<screen>" into doc. appDir receives the directory assets are relative to.
    // Size of a screen's JSON file in bytes (0 if unknown), for memory estimates.
    size_t screenBytes(const std::string& screenId) const;
    bool loadScreen(const std::string& screenId, JsonDocument& doc, std::string& appDir,
                    std::string& err) const;

    // Theme token lookup: "color.bg" -> the manifest's theme.color.bg as JsonVariant.
    JsonVariantConst token(const std::string& path) const;

    // Home-screen order of apps.
    std::vector<std::string> apps() const;
    std::string systemScreen(const char* key, const std::string& def = "") const;
    float unitWidth() const;

    static std::string packDir(const std::string& snap) { return "/packs/" + snap; }

private:
    std::string id_;
    std::vector<std::string> chain_;
    JsonDocument manifest_;
};

// Deep-merge src into dst: objects merge key by key, everything else is replaced.
void deepMerge(JsonVariant dst, JsonVariantConst src);

}  // namespace svc
