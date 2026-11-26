// XPT2046 resistive touch on its own pins (bit-banged SPI, so it never
// contends with the display (HSPI) or the SD card (VSPI)).
// Pins: CLK 25, MOSI 32, MISO 39, CS 33, IRQ 36 (active low while touched).
#pragma once
#include <Arduino.h>

namespace hal {

struct TouchCal {
    // screen = a*raw_x + b*raw_y + c  (affine fit from the calibration taps)
    float ax = 0, bx = 0, cx = 0;
    float ay = 0, by = 0, cy = 0;
    bool valid = false;
};

class Touch {
public:
    void begin();
    // Raw 12-bit readings (median filtered). Returns true while pressed.
    bool readRaw(uint16_t& x, uint16_t& y, uint16_t& z);
    // Calibrated screen coordinates (0..239, 0..319).
    bool read(int16_t& x, int16_t& y);
    void setCalibration(const TouchCal& c) { cal_ = c; }
    const TouchCal& calibration() const { return cal_; }
    // Least-squares affine fit from n (raw, screen) pairs. n >= 3.
    static TouchCal fit(const float* rawX, const float* rawY, const float* sx, const float* sy, int n);

private:
    uint16_t xfer(uint8_t cmd);
    TouchCal cal_;
    // Resistive pressure dips for a read or two during a press; hold the last
    // point until several consecutive reads miss.
    bool down_ = false;
    uint8_t misses_ = 0;
    int16_t lastX_ = 0, lastY_ = 0;
};

Touch& touch();

}  // namespace hal
