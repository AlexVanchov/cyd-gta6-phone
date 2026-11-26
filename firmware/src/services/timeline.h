// timeline.json: captured order of messages and notifications with in-game
// timestamps. The device shows the final state; replay is off by default
// (PLAN.md §6) and only the ordered event list is exposed here.
#pragma once
#include <string>
#include <vector>

namespace svc {

struct TimelineEvent {
    std::string t;      // in-game timestamp, "YYYY-MM-DDTHH:MM[:SS]"
    std::string type;   // e.g. "message", "notification"
    std::string app;
    std::string ref;    // screen or element the event belongs to
};

class Pack;

class Timeline {
public:
    // Loads the timeline of every snapshot in the chain; child entries win for the same ref.
    bool load(const Pack& pack, std::string& err);
    const std::vector<TimelineEvent>& events() const { return events_; }

private:
    std::vector<TimelineEvent> events_;
};

}  // namespace svc
