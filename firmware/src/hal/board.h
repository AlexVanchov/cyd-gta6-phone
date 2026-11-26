// Small board peripherals: SD card, RGB LED, light sensor.
#pragma once
#include <Arduino.h>

namespace hal {

// SD card on VSPI: MOSI 23, MISO 19, SCK 18, CS 5.
bool sdBegin();
bool sdBeginOnce(uint32_t hz);
bool sdMounted();
uint64_t sdTotalBytes();
uint64_t sdUsedBytes();

// RGB LED on 4 (red), 16 (green), 17 (blue), active low. Kept off in normal use.
// An external I2S audio board would need these pins (README).
void ledBegin();
void led(bool r, bool g, bool b);

// Light sensor (LDR) on GPIO 34. Higher = darker on this board.
void lightBegin();
int lightRaw();

// Speaker on GPIO 26 is reserved for the audio service (PLAN.md §9).
constexpr int kPinSpeaker = 26;

}  // namespace hal
