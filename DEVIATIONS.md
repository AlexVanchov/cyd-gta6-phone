# Deviations from the game

Every known way the device can or will differ from the in-game phone, and why (PLAN.md rule 4). Last updated 2026-11-26.

| # | Deviation | Why | Where |
|---|---|---|---|
| 1 | **Hidden maintenance menu.** Hold the status bar for 3 s. Uses LVGL's Montserrat font and plain grey styling. | Needed to switch snapshots, calibrate touch, set Wi-Fi and run upload mode. This is the one allowed addition (§7.1). | firmware/src/ui/menu.cpp |
| 2 | **System screens are not from the game:** hardware test, touch calibration, "No content pack" message. | They run before or without a content pack. They never appear in normal use once a pack is loaded and touch is calibrated. | firmware/src/main.cpp, ui/core.cpp |
| 3 | **16-bit colour (RGB565).** Gradients show banding the game doesn't have. | The panel is 16-bit. Diffs quantise the reference to RGB565 so this deviation is not scored as a rendering error. | whole device |
| 4 | **Fit-width scaling.** The phone screen is shown 240 px wide. Pinned bars stay put and the middle scrolls. The phone's real aspect ratio has **not been measured yet** (no captures). | The CYD is 3:4. The in-game phone is expected to be taller. It is measured during rectify and will be recorded here. | ui/render.cpp |
| 5 | **Controller buttons become edge gestures:** swipe right from the left edge = back (Circle); swipe up from the bottom edge = home. Touches that start in these 10 px edge zones don't reach the app. | A touch screen has no buttons. On-screen back controls that the game draws still work as captured. | ui/core.cpp |
| 6 | **Scroll inertia physics are LVGL's** (momentum on, elastic overscroll off). | There is no capture to measure the game's scroll deceleration against. It will be tuned when scroll videos exist. | ui/render.cpp |
| 7 | **Transitions are limited to fade, slide, cover and uncover** with a measured duration and cubic-bezier easing. A zoom or scale transition would be replaced by the nearest of these. | A full-screen zoom needs a 150 KB layer buffer, and there is no PSRAM. | ui/core.cpp |
| 8 | **Video is silent and at most 240×200 px per frame**, 12 fps MJPEG. | Silent per plan rule 8 (radio/audio out of scope). The frame size is a RAM limit without PSRAM. | ui/video.cpp |
| 9 | **Typeface: not identified yet.** If the game's font is not freely usable, the closest match by metrics will be used and named here. Text is rasterised by lv_font_conv, not by the game's renderer. | No captures yet. Even with the exact font, glyph rasterisation differs slightly. See the text-diff finding in REPORT.md. | fonts.py |
| 10 | **Emoji in text are not rendered yet.** | Not needed by any capture so far. If captures contain emoji, they will be added as an image-font fallback and noted here. | ui/render.cpp |
| 11 | **Clock text updates once per real second.** | The display refreshes once a second. At a fast game rate, a seconds display (if the game shows one) would skip values. | ui/core.cpp |
| 12 | **Screen sleeps after 120 s idle**, and the first touch only wakes it. The backlight follows the room light (LDR). | Desk-device behaviour from phase 7, not a game behaviour. Both can be changed in NVS settings (sleep_ms, auto_bl). | ui/core.cpp, main.cpp |
| 13 | **Looping feeds jump back to the first item** when scrolled to the end. | PLAN.md §6: captured items loop at the end. | ui/render.cpp |
| 14 | **Letterbox mode exists as a menu toggle** (default off: fit-width). | The §10 defaults table says it is "available as a config flag". It is off unless you turn it on. | ui/render.cpp, menu.cpp |
