#include "hal/touch.h"

#include <algorithm>

namespace hal {

namespace {
constexpr int kClk = 25, kMosi = 32, kMiso = 39, kCs = 33, kIrq = 36;
constexpr uint16_t kPressureMin = 300;
}  // namespace

void Touch::begin() {
    pinMode(kClk, OUTPUT);
    pinMode(kMosi, OUTPUT);
    pinMode(kCs, OUTPUT);
    pinMode(kMiso, INPUT);
    pinMode(kIrq, INPUT);
    digitalWrite(kCs, HIGH);
    digitalWrite(kClk, LOW);
    xfer(0x80);  // power down, PENIRQ enabled
}

uint16_t Touch::xfer(uint8_t cmd) {
    digitalWrite(kCs, LOW);
    for (int i = 7; i >= 0; --i) {
        digitalWrite(kMosi, (cmd >> i) & 1);
        delayMicroseconds(1);
        digitalWrite(kClk, HIGH);
        delayMicroseconds(1);
        digitalWrite(kClk, LOW);
    }
    uint16_t v = 0;
    for (int i = 0; i < 16; ++i) {
        delayMicroseconds(1);
        digitalWrite(kClk, HIGH);
        delayMicroseconds(1);
        v = static_cast<uint16_t>((v << 1) | digitalRead(kMiso));
        digitalWrite(kClk, LOW);
    }
    digitalWrite(kCs, HIGH);
    return static_cast<uint16_t>(v >> 3) & 0x0FFF;
}

bool Touch::readRaw(uint16_t& x, uint16_t& y, uint16_t& z) {
    // 12-bit differential reads, power down between conversions (PENIRQ on).
    uint16_t z1 = xfer(0xB1), z2 = xfer(0xC1);
    int p = static_cast<int>(z1) + 4095 - static_cast<int>(z2);
    z = static_cast<uint16_t>(p < 0 ? 0 : p > 4095 ? 4095 : p);
    if (z < kPressureMin || z1 == 0) {
        xfer(0x80);
        return false;
    }
    uint16_t xs[5], ys[5];
    for (int i = 0; i < 5; ++i) {
        xs[i] = xfer(0xD1);
        ys[i] = xfer(0x91);
    }
    xfer(0x80);
    std::sort(xs, xs + 5);
    std::sort(ys, ys + 5);
    x = xs[2];
    y = ys[2];
    return true;
}

bool Touch::read(int16_t& x, int16_t& y) {
    uint16_t rx, ry, rz;
    if (!readRaw(rx, ry, rz) || !cal_.valid) return false;
    float fx = cal_.ax * rx + cal_.bx * ry + cal_.cx;
    float fy = cal_.ay * rx + cal_.by * ry + cal_.cy;
    x = static_cast<int16_t>(std::min(239.0f, std::max(0.0f, fx)));
    y = static_cast<int16_t>(std::min(319.0f, std::max(0.0f, fy)));
    return true;
}

// Solve the 3x3 normal equations for one output axis.
static bool solve3(double m[3][3], double v[3], double out[3]) {
    double a[3][4];
    for (int i = 0; i < 3; ++i) {
        for (int j = 0; j < 3; ++j) a[i][j] = m[i][j];
        a[i][3] = v[i];
    }
    for (int c = 0; c < 3; ++c) {
        int piv = c;
        for (int r = c + 1; r < 3; ++r)
            if (std::abs(a[r][c]) > std::abs(a[piv][c])) piv = r;
        if (std::abs(a[piv][c]) < 1e-9) return false;
        for (int k = 0; k < 4; ++k) std::swap(a[c][k], a[piv][k]);
        for (int r = 0; r < 3; ++r) {
            if (r == c) continue;
            double f = a[r][c] / a[c][c];
            for (int k = c; k < 4; ++k) a[r][k] -= f * a[c][k];
        }
    }
    for (int i = 0; i < 3; ++i) out[i] = a[i][3] / a[i][i];
    return true;
}

TouchCal Touch::fit(const float* rx, const float* ry, const float* sx, const float* sy, int n) {
    TouchCal c;
    double m[3][3] = {{0}}, vx[3] = {0}, vy[3] = {0};
    for (int i = 0; i < n; ++i) {
        double r[3] = {rx[i], ry[i], 1.0};
        for (int a = 0; a < 3; ++a) {
            for (int b = 0; b < 3; ++b) m[a][b] += r[a] * r[b];
            vx[a] += r[a] * sx[i];
            vy[a] += r[a] * sy[i];
        }
    }
    double ox[3], oy[3];
    if (!solve3(m, vx, ox) || !solve3(m, vy, oy)) return c;
    c.ax = ox[0]; c.bx = ox[1]; c.cx = ox[2];
    c.ay = oy[0]; c.by = oy[1]; c.cy = oy[2];
    c.valid = true;
    return c;
}

Touch& touch() {
    static Touch t;
    return t;
}

}  // namespace hal
