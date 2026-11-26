#include "hal/audio.h"

namespace hal {

AudioService& audio() {
    static AudioService stub;
    return stub;
}

}  // namespace hal
