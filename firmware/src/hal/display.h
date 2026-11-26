// Display: LovyanGFX driver for the CYD panel (ILI9341 or ST7789 variant,
// chosen at build time by the PlatformIO environment).
// Pins (verified against witnessmenow/ESP32-Cheap-Yellow-Display PINS.md):
//   HSPI  MOSI 13, MISO 12, SCK 14, CS 15, DC 2, RST -1 (tied to EN), backlight 21
#pragma once
#include <Arduino.h>

#define LGFX_USE_V1
#include <LovyanGFX.hpp>

namespace hal {

constexpr int kPinBacklight = 21;

class Display : public lgfx::LGFX_Device {
public:
    Display();
    void applyColourOptions(bool invert, bool swapRB);
    // Orientation preset, applied before init(). 0..5, see kOrientations in
    // display.cpp. Returns false for an unknown preset.
    bool setOrientation(int preset);
    int orientation() const { return orientation_; }
    uint32_t rawRead(uint8_t cmd);

private:
#if defined(PANEL_ST7789)
    lgfx::Panel_ST7789 panel_;
#else
    lgfx::Panel_ILI9341 panel_;
#endif
    lgfx::Bus_SPI bus_;
    int orientation_ = 0;
};

constexpr int kOrientationCount = 6;

Display& display();
const char* panelName();
// Panel type read from the controller ("ILI9341", "ST7789" or "unknown").
const char* detectedPanel();
// Reads the controller's ID registers (needs MISO). Returns a short text such
// as "ID 04: 85 85 52 / D3: 00 93 41" for the hardware test screen and the log.
String readPanelId();

// Backlight PWM (0 = off).
void backlightBegin();
void setBacklight(uint8_t level);

}  // namespace hal
