#include "services/pack.h"

#include <algorithm>

#include "ui/platform.h"

namespace svc {

using ui::platform;

void deepMerge(JsonVariant dst, JsonVariantConst src) {
    if (src.is<JsonObjectConst>() && dst.is<JsonObject>()) {
        JsonObject d = dst.as<JsonObject>();
        for (JsonPairConst kv : src.as<JsonObjectConst>()) {
            JsonVariant child = d[kv.key()];
            if (kv.value().is<JsonObjectConst>() && child.is<JsonObject>()) {
                deepMerge(child, kv.value());
            } else {
                d[kv.key()] = kv.value();
            }
        }
    } else {
        dst.set(src);
    }
}

std::vector<std::string> Pack::listSnapshots() {
    std::vector<std::string> out;
    for (const auto& d : platform().listDirs("/packs")) {
        if (!d.empty() && d[0] != '.' && platform().isFile(packDir(d) + "/manifest.json")) out.push_back(d);
    }
    std::sort(out.begin(), out.end());
    return out;
}

std::string Pack::newest() {
    auto all = listSnapshots();
    return all.empty() ? "" : all.back();
}

bool Pack::load(const std::string& snapshotId, std::string& err) {
    chain_.clear();
    manifest_.clear();
    id_.clear();

    // Walk the parent chain, child first.
    std::vector<JsonDocument> docs;
    std::string cur = snapshotId;
    while (!cur.empty()) {
        if (std::find(chain_.begin(), chain_.end(), cur) != chain_.end()) {
            err = "parent cycle at " + cur;
            chain_.clear();
            return false;
        }
        std::string text;
        if (!platform().readFile(packDir(cur) + "/manifest.json", text)) {
            err = "missing manifest for snapshot '" + cur + "'";
            chain_.clear();
            return false;
        }
        JsonDocument d;
        DeserializationError e = deserializeJson(d, text);
        if (e) {
            err = "manifest " + cur + ": " + e.c_str();
            chain_.clear();
            return false;
        }
        chain_.push_back(cur);
        const char* parent = d["parent"] | "";
        docs.push_back(std::move(d));
        cur = parent;
    }

    // Merge oldest ancestor first so children override.
    manifest_.to<JsonObject>();
    for (auto it = docs.rbegin(); it != docs.rend(); ++it) deepMerge(manifest_.as<JsonVariant>(), it->as<JsonVariantConst>());
    manifest_["id"] = snapshotId;  // never inherited
    id_ = snapshotId;
    return true;
}

std::string Pack::appDir(const std::string& app) const {
    for (const auto& s : chain_) {
        std::string d = packDir(s) + "/apps/" + app;
        if (platform().isDir(d)) return d;
    }
    return "";
}

std::string Pack::resolveFile(const std::string& rel) const {
    for (const auto& s : chain_) {
        std::string f = packDir(s) + "/" + rel;
        if (platform().isFile(f)) return f;
    }
    return "";
}

bool Pack::loadScreen(const std::string& screenId, JsonDocument& doc, std::string& dir,
                      std::string& err) const {
    auto slash = screenId.find('/');
    if (slash == std::string::npos) {
        err = "screen id must be <app>/<screen>: " + screenId;
        return false;
    }
    std::string app = screenId.substr(0, slash), screen = screenId.substr(slash + 1);
    dir = appDir(app);
    if (dir.empty()) {
        err = "app not in pack: " + app;
        return false;
    }
    std::string text;
    if (!platform().readFile(dir + "/screens/" + screen + ".json", text)) {
        err = "screen not found: " + screenId;
        return false;
    }
    DeserializationError e = deserializeJson(doc, text);
    if (e) {
        err = "screen " + screenId + ": " + e.c_str();
        return false;
    }
    return true;
}

JsonVariantConst Pack::token(const std::string& path) const {
    JsonVariantConst v = manifest_["theme"];
    size_t start = 0;
    while (start <= path.size()) {
        size_t dot = path.find('.', start);
        std::string part = path.substr(start, dot == std::string::npos ? std::string::npos : dot - start);
        v = v[part];
        if (v.isNull() || dot == std::string::npos) break;
        start = dot + 1;
    }
    return v;
}

std::vector<std::string> Pack::apps() const {
    std::vector<std::string> out;
    for (JsonVariantConst a : manifest_["apps"].as<JsonArrayConst>()) {
        if (a.is<const char*>()) out.push_back(a.as<const char*>());
        else if (a["id"].is<const char*>()) out.push_back(a["id"].as<const char*>());
    }
    return out;
}

std::string Pack::systemScreen(const char* key, const std::string& def) const {
    const char* v = manifest_["system"][key] | "";
    return *v ? std::string(v) : def;
}

float Pack::unitWidth() const { return manifest_["unit_width"] | 240.0f; }

}  // namespace svc
