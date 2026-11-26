#include "hal/board.h"

#include <SD.h>
#include <SPI.h>

namespace hal {

static SPIClass g_sdSpi(VSPI);
static bool g_sdOk = false;

bool sdBegin() {
    g_sdSpi.begin(18, 19, 23, 5);
    // Try a fast clock first, fall back for slow or long-wired cards.
    const uint32_t speeds[] = {25000000, 16000000, 4000000};
    for (uint32_t hz : speeds) {
        if (SD.begin(5, g_sdSpi, hz, "/sd", 8)) {
            g_sdOk = SD.cardType() != CARD_NONE;
            if (g_sdOk) return true;
            SD.end();
        }
    }
    return false;
}

bool sdMounted() { return g_sdOk; }
uint64_t sdTotalBytes() { return g_sdOk ? SD.totalBytes() : 0; }
uint64_t sdUsedBytes() { return g_sdOk ? SD.usedBytes() : 0; }

void ledBegin() {
    pinMode(4, OUTPUT);
    pinMode(16, OUTPUT);
    pinMode(17, OUTPUT);
    led(false, false, false);
}

void led(bool r, bool g, bool b) {
    digitalWrite(4, r ? LOW : HIGH);
    digitalWrite(16, g ? LOW : HIGH);
    digitalWrite(17, b ? LOW : HIGH);
}

void lightBegin() {
    analogSetPinAttenuation(34, ADC_0db);
    pinMode(34, INPUT);
}

int lightRaw() { return analogRead(34); }

}  // namespace hal
