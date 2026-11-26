// Audio service hook (PLAN.md §9). Radio playback is out of scope: this stub
// does nothing and reports success. GPIO 26 stays reserved for the onboard
// speaker. Portable so the simulator links the same stub.
#pragma once
#include <cstdint>
#include <string>

namespace hal {

class AudioService {
public:
    virtual ~AudioService() = default;
    virtual bool play(const std::string& source) { (void)source; return true; }
    virtual bool stop() { return true; }
    virtual bool set_volume(uint8_t volume) { (void)volume; return true; }
    virtual bool is_playing() const { return false; }
};

AudioService& audio();

}  // namespace hal
