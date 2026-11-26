#include "hal/display.h"

namespace hal {

Display::Display() {
    {
        auto cfg = bus_.config();
        cfg.spi_host = HSPI_HOST;
        cfg.spi_mode = 0;
        cfg.freq_write = 40000000;
        cfg.freq_read = 16000000;
        cfg.spi_3wire = false;
        cfg.use_lock = true;
        cfg.dma_channel = SPI_DMA_CH_AUTO;
        cfg.pin_sclk = 14;
        cfg.pin_mosi = 13;
        cfg.pin_miso = 12;
        cfg.pin_dc = 2;
        bus_.config(cfg);
        panel_.setBus(&bus_);
    }
    {
        auto cfg = panel_.config();
        cfg.pin_cs = 15;
        cfg.pin_rst = -1;
        cfg.pin_busy = -1;
        cfg.panel_width = 240;
        cfg.panel_height = 320;
        cfg.memory_width = 240;
        cfg.memory_height = 320;
        cfg.offset_x = 0;
        cfg.offset_y = 0;
#if defined(PANEL_ST7789)
        cfg.offset_rotation = 0;
#else
        cfg.offset_rotation = 2;  // the CYD's ILI9341 is mounted rotated (LovyanGFX board autodetect)
#endif
        cfg.dummy_read_pixel = 8;
        cfg.dummy_read_bits = 1;
        cfg.readable = true;
        cfg.invert = false;
#if defined(PANEL_ST7789)
        // CYD2USB: ST7789 with BGR order (DisplayConfig/CYD2USB/User_Setup.h).
        cfg.rgb_order = true;
#else
        cfg.rgb_order = false;
#endif
        cfg.dlen_16bit = false;
        cfg.bus_shared = false;  // touch and SD have their own buses
        panel_.config(cfg);
    }
    setPanel(&panel_);
}

void Display::applyColourOptions(bool invert, bool swapRB) {
    auto cfg = panel_.config();
#if defined(PANEL_ST7789)
    cfg.rgb_order = !swapRB;
#else
    cfg.rgb_order = swapRB;
#endif
    panel_.config(cfg);
    invertDisplay(invert);
    // Re-apply the memory access control (colour order lives there).
    setRotation(getRotation());
}

Display& display() {
    static Display d;
    return d;
}

const char* panelName() {
#if defined(PANEL_ST7789)
    return "ST7789";
#else
    return "ILI9341";
#endif
}

uint32_t Display::rawRead(uint8_t cmd) {
    // Same raw read LovyanGFX's board autodetect uses: no dummy bits; the low
    // byte is 0x00 on the CYD's ILI9341 and 0x85 on the CYD2USB's ST7789.
    bus_.beginTransaction();
    digitalWrite(15, LOW);
    bus_.writeCommand(cmd, 8);
    bus_.beginRead();
    uint32_t r = bus_.readData(32);
    bus_.endTransaction();
    digitalWrite(15, HIGH);
    return r;
}

const char* detectedPanel() {
    uint32_t id = display().rawRead(0x04);
    if ((id & 0xFF) == 0x85) return "ST7789";
    if ((id & 0xFF) == 0x00) return "ILI9341";
    return "unknown";
}

String readPanelId() {
    uint32_t id04 = display().rawRead(0x04);
    char b[64];
    snprintf(b, sizeof b, "%08lX (looks like %s)", (unsigned long)id04, detectedPanel());
    return String(b);
}

static constexpr int kBlChannel = 7;

void backlightBegin() {
    ledcSetup(kBlChannel, 5000, 8);
    ledcAttachPin(kPinBacklight, kBlChannel);
    ledcWrite(kBlChannel, 255);
}

void setBacklight(uint8_t level) { ledcWrite(kBlChannel, level); }

}  // namespace hal
