# Final report: first build run (2026-11-26)

**Bottom line:** reference/ was empty when this run started, so PLAN.md §3 applied. Phases 0 and 1 and the web research are done, the capture checklist is written, and the run ends here. **The device has no game content yet.** It boots into two synthetic test packs (plain shapes and text) until you add captures. Phases 3, 4 and parts of 2 and 5–7 have to wait for captures.

## 1. What was built, by phase

| Phase | Status | What exists |
|---|---|---|
| 0. Bring-up | ✅ done | LovyanGFX display driver for **both** variants (`ili9341`, `st7789`; both compile). Bit-banged XPT2046 touch with a 5-point least-squares calibration saved in NVS. SD on VSPI with speed fallback. Backlight PWM, light sensor, RGB LED. Hardware test screen (colour bars, panel ID, SD, heap, live touch and light readings). Serial maintenance commands (INFO, SHOT, TAP, HOLD, SWIPE, SCREEN, SNAP, BACK, HOME, MENU, SKIP). **The ILI9341 build was flashed to the connected board and boots:** UI ready in about 3.6 s, 264 KB heap free, largest free block 110 KB, hidden menu opens from a 3 s hold. |
| 1. Renderer core | ✅ done | Pack loader with parent-chain inheritance and deep-merged manifests. Screen JSON to LVGL using one scale factor with edge rounding, pinned top and bottom regions and a scrolling body. Elements: text, image, rect/button, list, scroll (paged or looping), video, station. Actions: open_screen, back, home, play_video, run_sequence. Navigation stack with scroll restore. Measured transitions with cubic-bezier easing. Gestures (tap, long press, swipes with inertia, edge back/home, 3 s status-bar hold). Enlarged hit areas below 28 px. Headless simulator `sim --pack --screen --out` with scripted input, `--regions`, `--scroll` and `--measure-transition`. JSON schemas. **The synthetic test pack renders and navigates correctly** (see §2). |
| 2. Research and inventory | ◐ research done | research/facts.md has 14 accepted apps, unlock stages, screens and behaviours, all with sources. rectify.py, stitch.py and inventory.py are built and tested. **inventory.md waits for captures.** |
| 3. System shell | ⏸ needs captures | The renderer supports it (lock, home pages, status-bar fragment, transitions). No game screens exist to diff. |
| 4. Apps | ⏸ needs captures | measure.py, fonts.py, slice.py and pack.py are ready. |
| 5. Dynamic layer | ✅ mechanics done | Snapshot switching (hidden menu; boots newest unless you picked another since), inheritance, timeline loading, running clock with a game rate and the game's own day/month names. Simulator tests switch test-a ↔ test-b and load apps inherited from the parent. |
| 6. Video | ✅ mechanics done | MJPEG container, decoded with TJpgDec into one RGB565 frame buffer. Clips decode in the simulator (frames advance). The device build fits: 1.23 MB of 3 MB flash, 52 KB static RAM, and the 96 KB frame limit fits the 110 KB largest free block. |
| 7. Polish | ◐ | Transitions are timed from the manifest and checked in the simulator (below). Sleep after 120 s with tap-to-wake, LDR auto-brightness, lazy font loading. Matching game timings needs the transition videos. |
| 8. Handover | ✅ | README, CAPTURE_CHECKLIST.md, MISSING.md, DEVIATIONS.md, this report. |

Tests: `pytest tools/tests` gives **29 passed**. They cover every tool plus end-to-end simulator runs (navigation, run_sequence, snapshot switch and inheritance, video, transition timing, diff).

Transition timing in the simulator vs the manifest (tolerance 50 ms): push 305 ms vs 300 ✅, open_app 230 ms vs 250 ✅, pop 285 ms vs 300 ✅. Game timings will replace these once videos exist.

## 2. Diff scores

**No game screens exist, so no game diff scores exist.** To check the renderer itself, each synthetic screen was also drawn by an independent Pillow renderer (tools/refrender.py) and compared with tools/diff.py. Side-by-side images are in `content/0000-00-00_test-a/report/`.

| Screen | Whole-screen SSIM | Grade | Worst text region | Text regions ≥ 0.95 |
|---|---|---|---|---|
| _system/home | 0.962 | pass | 0.726 | 0/5 |
| _system/lock | 0.951 | pass | 0.854 | 0/4 |
| delta/main | 0.986 | pass | 0.932 | 0/3 |
| gamma/main | 0.978 | pass | 0.880 | 0/4 |
| alpha/main | 0.777 | below 0.90 | 0.481 | 7/17 |
| alpha/detail | 0.868 | below 0.90 | 0.469 | 0/4 |
| beta/main | 0.754 | below 0.90 | 0.721 | 0/4 |

What the low scores are, after inspecting the side-by-side images:

- Layout, scale, rounding, colours, tokens, images and pinned regions line up in every screen. One real renderer bug was found this way and fixed: wrapped text was being clipped at its box.
- beta/main plays video, so the simulator shows a later frame than the reference's first frame.
- **The text gap is rasterisation, not layout.** lv_font_conv and Pillow/FreeType rasterise the same Montserrat font differently: kerning, hinting at 14 px, and a 1 px baseline offset. Small grey-on-dark text scores lowest.

**Finding for the owner:** with live text, a per-text-region SSIM of 0.95 will probably not be reachable against the game either, even with the exact font, because the game uses its own rasteriser. Choices for later: (a) keep 0.95 and ship text that fails as image slices (§5 allows this), (b) lower the text bar (e.g. 0.85) and rely on the exact-string check, or (c) score text as greyscale. The tool currently keeps your 0.95 bar and reports these as fail.

## 3. Capture list for the owner (MISSING.md)

Nothing has been captured yet, so everything is needed. The full list is in MISSING.md and the step-by-step version in CAPTURE_CHECKLIST.md:

- The first snapshot folder with notes.md (in-game date and time, story progress)
- System: lock screen, all home pages, status bar, notification/Reminders panel, transition videos, a 2-minute clock video
- Text-heavy captures to identify the typeface
- Every app: WAiNK, Contacts, Camera, Snapmatic, Gallery, Fitness, News, WhatUp, Settings, Weather, Scooter Bros, BuckMe, RydeMe, Vice City Real Estate (plus Reminders, On Demand or radio, only if present)
- Two recordings of each feed; full call, ride and delivery flows up to the last phone screen; a map pan if there is a map

## 4. Deviations (DEVIATIONS.md)

1. Hidden maintenance menu (the one allowed addition)
2. System screens (hardware test, calibration, "no pack" message) are not from the game
3. 16-bit colour (gradient banding)
4. Fit-width scaling; the real aspect ratio is not measured yet
5. Controller buttons become edge gestures (left-edge swipe = back, bottom-edge swipe = home)
6. Scroll inertia uses LVGL's physics; no elastic overscroll
7. Transitions limited to fade, slide, cover and uncover (no zoom: RAM)
8. Video is silent, at most 240×200 per frame, 12 fps
9. Typeface not identified yet; text rasterised by lv_font_conv
10. Emoji not rendered yet
11. Clock text updates once per real second
12. Sleep after 120 s and LDR auto-brightness (desk-device behaviour)
13. Looping feeds jump back to the top at the end
14. Letterbox mode exists as a menu toggle, off by default

## 5. Defaults used (PLAN.md §10)

| Decision | Used |
|---|---|
| Board variant | Both builds compile. The **ILI9341** build was flashed: it is the standard CYD, and the identical board running the vacuum remote uses an ILI9341 driver. If the test-screen colours look wrong, flash `st7789` (README §1). |
| Screen fit | Fit-width; letterbox is a hidden-menu toggle |
| Diff pass bar | 0.95, with 0.90–0.95 reported as review (see the text finding in §2) |
| Clock | Runs from manifest `clock.start` at `clock.rate`. Test packs use 2026-01-01 09:41 at 1.0, until you measure the real start and rate |
| Replay mode | Off. The timeline is loaded and ordered; the final state is shown |
| Typeface | Not chosen yet (no captures). The test packs use Montserrat (OFL) |

Other decisions made during the run:

- Image assets use LVGL's own `.bin` format (12-byte header + RGB565 / RGB565A8) instead of a `.rgb565` extension. LVGL's decoder only streams files named `.bin`.
- Touch is bit-banged, so the display (HSPI) and SD (VSPI) keep their own buses.
- Test-pack ids start with `0000-00-00`, so any real snapshot sorts newer and boots first.

## 6. Owner's steps

1. **Firmware:** already flashed (ILI9341). To reflash: `cd firmware && uvx --from platformio pio run -e ili9341 -t upload` over micro-USB.
2. **SD card:** already formatted FAT32 (label CYDPHONE) and loaded with the test packs, config/wifi.json.example and README.txt. Eject it, put it in the CYD and reset.
3. **Hardware test screen** (first boot): check each colour bar matches its label. If not, flash `st7789` or use the menu's colour fixes.
4. **Calibrate touch:** tap anywhere, then tap the 5 crosses.
5. The device boots into test pack B (inherits from A). Tap *Unlock*, open apps, swipe home pages, hold the top edge 3 s for the menu.
6. **For game content:** follow CAPTURE_CHECKLIST.md, put the captures in reference/, then run the ingest (README §5) and copy the new pack to the card.

## 7. After handover (2026-11-26, on the device)

- **Mirrored, then sideways picture.** This board's controller is wired landscape (320×240 memory). The vacuum remote's board and LovyanGFX's CYD autodetect both assume portrait. Calibration taps showed the UI's x axis running along the long side and the rows wrapping after about 240. The firmware now has orientation presets (README §2). This board uses **preset 1** (MADCTL MV|MX|MY on a 320×240 memory), which the owner confirmed reads upright and fills the screen.
- **Touch calibration** recorded one cross twice when the pressure dipped mid-press, which squashed the y axis. It now needs a 150 ms release between crosses, rejects a repeated spot, and repeats if any cross is off by more than 15 px. The owner's calibration has a worst error of 1.9 px.
- **SD card**: at first the card did not answer at all (no reply to CMD0). Re-seating fixed it. The firmware now retries every 3 s and restarts when a card appears.
- **Video**: opening a video screen right after a transition could fail with "out of memory for video frame", because both pages are alive during a transition. The frame allocation now retries after the old page is freed.
- Verified on the device over serial (injected taps go through the same input path as touch):
  - lock → Unlock → home; alpha → detail → back; beta video, with frames changing in the panel readback; gamma.
  - Edge-swipe back, home, the 3 s status-bar hold opens the hidden menu.
  - Reboot keeps the orientation and calibration.
  - No heap leak over repeated navigation: home returns to 158 KB each time.
