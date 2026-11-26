#include "services/clock.h"

#include <cstdio>
#include <cstdlib>

namespace svc {

static const char* kWd[7] = {"Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"};
static const char* kMo[12] = {"January", "February", "March",     "April",   "May",      "June",
                              "July",    "August",   "September", "October", "November", "December"};

bool parseDateTime(const std::string& s, DateTime& o) {
    int Y, M, D, h = 0, m = 0, sec = 0;
    int n = std::sscanf(s.c_str(), "%d-%d-%dT%d:%d:%d", &Y, &M, &D, &h, &m, &sec);
    if (n < 5) return false;
    if (M < 1 || M > 12 || D < 1 || D > 31 || h < 0 || h > 23 || m < 0 || m > 59 || sec < 0 || sec > 59) return false;
    o = DateTime{Y, M, D, h, m, sec};
    return true;
}

// Howard Hinnant's days_from_civil / civil_from_days.
static int64_t daysFromCivil(int64_t y, unsigned m, unsigned d) {
    y -= m <= 2;
    const int64_t era = (y >= 0 ? y : y - 399) / 400;
    const unsigned yoe = static_cast<unsigned>(y - era * 400);
    const unsigned doy = (153 * (m + (m > 2 ? -3 : 9)) + 2) / 5 + d - 1;
    const unsigned doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
    return era * 146097 + static_cast<int64_t>(doe) - 719468;
}

int64_t toEpochSeconds(const DateTime& t) {
    return daysFromCivil(t.year, t.month, t.day) * 86400 + t.hour * 3600 + t.minute * 60 + t.second;
}

DateTime fromEpochSeconds(int64_t s) {
    int64_t z = (s >= 0 ? s : s - 86399) / 86400;
    int64_t secs = s - z * 86400;
    z += 719468;
    const int64_t era = (z >= 0 ? z : z - 146096) / 146097;
    const unsigned doe = static_cast<unsigned>(z - era * 146097);
    const unsigned yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365;
    const int64_t y = static_cast<int64_t>(yoe) + era * 400;
    const unsigned doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    const unsigned mp = (5 * doy + 2) / 153;
    const unsigned d = doy - (153 * mp + 2) / 5 + 1;
    const unsigned m = mp + (mp < 10 ? 3 : -9);
    DateTime t;
    t.year = static_cast<int>(y + (m <= 2));
    t.month = static_cast<int>(m);
    t.day = static_cast<int>(d);
    t.hour = static_cast<int>(secs / 3600);
    t.minute = static_cast<int>((secs % 3600) / 60);
    t.second = static_cast<int>(secs % 60);
    return t;
}

int weekday(const DateTime& t) {
    int64_t days = daysFromCivil(t.year, t.month, t.day);
    return static_cast<int>(((days % 7) + 11) % 7);  // 1970-01-01 was a Thursday (4)
}

static std::string num(int v, int width, bool pad) {
    char b[16];
    if (pad) std::snprintf(b, sizeof b, "%0*d", width, v);
    else std::snprintf(b, sizeof b, "%d", v);
    return b;
}

std::string formatDateTime(const DateTime& t, const std::string& fmt, const ClockNames& n) {
    std::string out;
    int wd = weekday(t);
    int h12 = t.hour % 12 == 0 ? 12 : t.hour % 12;
    auto pick = [](const std::string& custom, const std::string& fallback) { return custom.empty() ? fallback : custom; };
    for (size_t i = 0; i < fmt.size(); ++i) {
        if (fmt[i] != '%' || i + 1 >= fmt.size()) {
            out += fmt[i];
            continue;
        }
        char c = fmt[++i];
        bool pad = true;
        if (c == '-' && i + 1 < fmt.size()) {
            pad = false;
            c = fmt[++i];
        }
        switch (c) {
            case 'Y': out += num(t.year, 4, pad); break;
            case 'y': out += num(t.year % 100, 2, pad); break;
            case 'm': out += num(t.month, 2, pad); break;
            case 'd': out += num(t.day, 2, pad); break;
            case 'e': out += num(t.day, 1, false); break;
            case 'H': out += num(t.hour, 2, pad); break;
            case 'I': out += num(h12, 2, pad); break;
            case 'l': out += num(h12, 1, false); break;
            case 'M': out += num(t.minute, 2, pad); break;
            case 'S': out += num(t.second, 2, pad); break;
            case 'p': out += t.hour < 12 ? n.am : n.pm; break;
            case 'P': {
                std::string s = t.hour < 12 ? n.am : n.pm;
                for (auto& ch : s) ch = static_cast<char>(ch >= 'A' && ch <= 'Z' ? ch + 32 : ch);
                out += s;
                break;
            }
            case 'A': out += pick(n.weekday[wd], kWd[wd]); break;
            case 'a': out += pick(n.weekdayShort[wd], std::string(kWd[wd]).substr(0, 3)); break;
            case 'B': out += pick(n.month[t.month - 1], kMo[t.month - 1]); break;
            case 'b': out += pick(n.monthShort[t.month - 1], std::string(kMo[t.month - 1]).substr(0, 3)); break;
            case 'n': out += '\n'; break;
            case '%': out += '%'; break;
            default: out += '%'; out += c; break;
        }
    }
    return out;
}

void GameClock::start(const DateTime& gameStart, double rate, uint32_t nowMs) {
    startEpoch_ = toEpochSeconds(gameStart);
    startMs_ = nowMs;
    rate_ = rate > 0 ? rate : 1.0;
    running_ = true;
}

DateTime GameClock::now(uint32_t nowMs) const {
    uint32_t elapsed = nowMs - startMs_;
    int64_t gameSecs = static_cast<int64_t>(static_cast<double>(elapsed) / 1000.0 * rate_);
    return fromEpochSeconds(startEpoch_ + gameSecs);
}

}  // namespace svc
