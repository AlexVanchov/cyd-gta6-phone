#include "services/timeline.h"

#include <ArduinoJson.h>

#include <algorithm>

#include "services/pack.h"
#include "ui/platform.h"

namespace svc {

bool Timeline::load(const Pack& pack, std::string& err) {
    events_.clear();
    const auto& chain = pack.chain();
    // Oldest ancestor first, so a child's event for the same ref replaces it.
    for (auto it = chain.rbegin(); it != chain.rend(); ++it) {
        std::string text;
        if (!ui::platform().readFile(Pack::packDir(*it) + "/timeline.json", text)) continue;
        JsonDocument d;
        if (deserializeJson(d, text)) {
            err = "timeline.json in " + *it + " is not valid JSON";
            return false;
        }
        for (JsonObjectConst e : d["events"].as<JsonArrayConst>()) {
            TimelineEvent ev{e["t"] | "", e["type"] | "", e["app"] | "", e["ref"] | ""};
            auto same = std::find_if(events_.begin(), events_.end(), [&](const TimelineEvent& x) {
                return !ev.ref.empty() && x.ref == ev.ref;
            });
            if (same != events_.end()) *same = ev;
            else events_.push_back(ev);
        }
    }
    // Captured order is the file order; stable sort by timestamp keeps it for ties.
    std::stable_sort(events_.begin(), events_.end(),
                     [](const TimelineEvent& a, const TimelineEvent& b) { return a.t < b.t; });
    return true;
}

}  // namespace svc
