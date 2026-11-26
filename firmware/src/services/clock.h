// In-game clock: starts at the captured in-game time and advances at the
// measured game rate (game seconds per real second). Portable.
#pragma once
#include <cstdint>
#include <string>

namespace svc {

struct DateTime {
    int year = 2000, month = 1, day = 1, hour = 0, minute = 0, second = 0;
};

// Parse "YYYY-MM-DDTHH:MM[:SS]". Returns false on malformed input.
bool parseDateTime(const std::string& s, DateTime& out);
// Days since 1970-01-01 (proleptic Gregorian) and back.
int64_t toEpochSeconds(const DateTime& t);
DateTime fromEpochSeconds(int64_t s);
// Day of week, 0 = Sunday.
int weekday(const DateTime& t);

// strftime subset: %Y %y %m %d %e %H %I %l %M %S %p %P %A %a %B %b %n %%
// plus %-m %-d %-H %-I (no leading zero). Names come from the manifest's
// clock.names so the game's exact spelling is used; English is the fallback.
struct ClockNames {
    std::string weekday[7];
    std::string weekdayShort[7];
    std::string month[12];
    std::string monthShort[12];
    std::string am = "AM", pm = "PM";
};
std::string formatDateTime(const DateTime& t, const std::string& fmt, const ClockNames& names);

class GameClock {
public:
    // rate: game seconds per real second (1.0 = real time).
    void start(const DateTime& gameStart, double rate, uint32_t nowMs);
    DateTime now(uint32_t nowMs) const;
    bool running() const { return running_; }
    double rate() const { return rate_; }

private:
    bool running_ = false;
    int64_t startEpoch_ = 0;
    uint32_t startMs_ = 0;
    double rate_ = 1.0;
};

}  // namespace svc
