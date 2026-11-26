# GTA 6 Phone Clone on ESP32 CYD: Build Plan

Nov 26, 2026 · Alex Vanchov

This is the owner's build plan, kept in the repo as the governing document.
Section numbers referenced throughout the code and docs refer to it.

## 1. Mission and hard rules

You are building the firmware and PC tools for a standalone replica of the in-game phone from GTA 6, running on an ESP32 "Cheap Yellow Display" (ESP32-2432S028R). It is a personal desk device for the owner. It does not connect to the PS5 or the game.

The owner's requirement is that apps and their content match the game exactly. You have no reliable knowledge of what the phone contains, so exactness can only come from the owner's own captures. These rules override everything else in this plan:

1. Captures are the only source of truth. Every app, icon, label, message, image, colour, and ordering comes from files in reference/. Do not use training knowledge, web articles, or guesses about what the GTA 6 phone contains.
2. Never invent, paraphrase, or improve. Copy text character for character, including typos, casing, emoji, and timestamps. Do not add placeholder content, sample data, or "reasonable" extras.
3. Missing means absent. If a screen or item was not captured, leave it out of the device and add a line to MISSING.md saying what is needed. The owner will capture it.
4. Record every deviation. Anything that cannot match the game (font substitute, scaled layout, silent video) goes in DEVIATIONS.md with the reason.
5. Content is data, not code. The firmware is a generic renderer. All app content lives in content packs on the SD card, so content can be updated without reflashing.
6. Every screen is verified. A screen is done only when its simulator render passes the visual diff against its reference capture.
7. Game assets stay local. reference/, content/, and sd/ are gitignored. The repository is private and nothing built from game assets is published or distributed.
8. Radio and audio are out of scope for now. Build only the hooks in section 9.

One run. Execute every phase in section 8 in a single run, without stopping for approval. Where this plan names a default, use it. Where something is unknown, choose the option that changes the game's look least, log it in DEVIATIONS.md, and continue. Stop early only if continuing would break a rule above. Finish with the final report described in section 10.

What the web can and cannot supply. You fetch facts about the phone from the web yourself (section 3.1). The pixel-exact design and the full app content exist only in the game, so they come from the owner's captures in reference/, which must be in place before the run starts. Do not download screenshots, artwork, icons, or video of the game from websites, and do not redraw the game's icons or logos from memory or from web images.

## 2. Hardware

The target is the 2.8 inch ESP32-2432S028R. Verify every pin below against the ESP32-Cheap-Yellow-Display repository before relying on it, and build both display variants (section 10).

| Part | Detail |
|---|---|
| MCU | ESP32-WROOM-32, dual core, 4 MB flash, no PSRAM |
| Display | 240×320, 16-bit colour, ILI9341 (some two-USB variants use ST7789) |
| Display pins | MOSI 13, MISO 12, SCK 14, CS 15, DC 2, backlight 21 |
| Touch | XPT2046 resistive, single touch, on its own SPI bus |
| Touch pins | CLK 25, MOSI 32, MISO 39, CS 33, IRQ 36 |
| SD card | MOSI 23, MISO 19, SCK 18, CS 5 |
| RGB LED | 4, 16, 17 (active low) |
| Light sensor | 34 |
| Speaker | 26 (onboard DAC and small amplifier) |

Constraints that shape the design:

- Memory. With no PSRAM, a full 240×320 frame buffer (about 150 KB) does not fit comfortably. Use partial draw buffers and stream images from SD in strips.
- Storage. 4 MB flash holds firmware only. All content lives on the SD card (FAT32, 8 GB or larger).
- Touch. Resistive, single touch. There is no pinch or multi-finger input. Calibrate on first boot and store the result in NVS.
- Orientation. Portrait, 240 wide by 320 tall.

## 3. Source of truth: the capture protocol

The owner records the in-game phone on the PS5 and puts the files in reference/ before starting the run. These captures are the design specification: the 1:1 look is whatever they show. If reference/ is empty when the run starts, complete phases 0 and 1, run the web research, write a capture checklist tailored to the real app list into CAPTURE_CHECKLIST.md, and end the run with the final report.

PS5 settings before capturing

- Screenshot format: PNG.
- Video clips: highest resolution available.
- HDR: off while capturing, so colours are true.
- Export to a USB drive and copy to the PC.

How to hold the phone in-game

- Use the closest, flattest view of the phone the game offers.
- Stand still in a bright, neutrally lit place so the game's lighting does not tint the screen.
- Keep the camera still during the whole session.

What to capture for every app

1. A screenshot of every distinct screen, including the lock screen, every home page, the status bar, and any notification panel.
2. A slow, one-direction scroll video of every scrollable list, from the very top to the very bottom.
3. Every item opened: each message thread, contact, photo, post, and settings page.
4. A video of each transition: opening and closing an app, going back, a notification arriving.
5. For the clock: a two-minute video of the phone's clock running, so the game's time rate can be measured.

Folder layout

```
reference/
  <snapshot-id>/            e.g. 2026-11-28_after-mission-12
    notes.md                in-game date and time, story progress, anything odd
    _system/                lock screen, home pages, status bar, notifications
    <app-name>/
      screens/*.png
      scroll/*.mp4
      transitions/*.mp4
```

A snapshot ID is the real date plus a short story-progress label. Each capture session is one snapshot (see section 6).

### 3.1 Web research: facts you fetch yourself

At the start of the run, search the web and open launch guides and wikis about the GTA 6 in-game phone. Write what you find to research/facts.md.

What to collect

- Every app's name, the home-screen order, and when each app unlocks in the story.
- The screens each app has and how you move between them.
- Behaviours: what updates over time, what is random, what depends on story progress.

Rules

- Record the source URL beside every fact.
- Accept a fact only when two independent sources agree or a capture confirms it. Captures always win over the web.
- Guides disagree on how some app names are spelled and capitalised. Take all spelling from the captures.
- Collect text facts only. Do not download images or video, and respect each site's robots.txt and terms.

What the facts are used for

- Cross-checking the inventory in section 5.
- Filling MISSING.md: anything the web says exists in the game that the captures do not show.
- Naming the story stages used for snapshots in section 6.

Unverified starting points: Beebom (GTA 6 phone apps), Overgear (how to use the phone in GTA 6), Neon Coast (GTA 6 phone apps), GTA BOOM (GTA 6 phone apps).

## 4. Architecture

The project has three parts: a generic renderer firmware, a PC simulator that runs the same UI code, and Python tools that turn captures into content packs.

```
repo/
  PLAN.md                 this document
  MISSING.md              captures still needed
  DEVIATIONS.md           every known difference from the game
  firmware/               PlatformIO project (Arduino framework)
    src/hal/              display, touch, SD, backlight, audio stub
    src/ui/               renderer, navigation stack, gestures (shared with simulator)
    src/services/         pack loader, clock, timeline, wifi, sync
  simulator/              LVGL + SDL build of src/ui, with headless screenshot mode
  tools/                  Python: rectify, stitch, slice, convert, pack, diff, sync
  schema/                 JSON schemas for packs and screens
  reference/              owner's captures (gitignored)
  content/                intermediate ingest output (gitignored)
  sd/                     final SD card image folder (gitignored)
```

Firmware stack

- PlatformIO, Arduino framework, LVGL 9, LovyanGFX for the display, an XPT2046 driver for touch.
- Partial LVGL draw buffers (about 240×32 pixels). No full frame buffer.
- Images stored as raw RGB565 with a small header and streamed from SD in strips. JPEG is allowed where SD speed makes raw too slow.
- UI code in src/ui/ must compile unchanged for both the device and the simulator.

Content pack format

```
sd/packs/<snapshot-id>/
  manifest.json           parent snapshot, app list in home order, theme tokens
  timeline.json           ordered events with in-game timestamps
  fonts/*.bin             LVGL binary fonts
  apps/<app>/
    screens/<screen>.json layout tree
    assets/*.rgb565       icons, photos, wallpapers, text slices
    video/*.mjpeg
```

A screen JSON is a tree of elements (image, text, list, button, video, scroll) with position, size, style, and an optional action. Actions are limited to open_screen, back, home, play_video, and run_sequence. Define the exact schema in schema/ and validate every pack against it.

Simulator: the simulator must support `sim --pack <dir> --screen <id> --out <file.png>` with no window, so you can render and check screens yourself without the hardware.

## 5. Ingest pipeline: captures to SD card

Each step is a script in tools/ and writes its output to content/<snapshot-id>/. Steps must be re-runnable on a single app.

1. Rectify. Find the phone screen's four corners in each capture, correct the perspective, and save a flat canonical image at four times the target width (960 pixels wide).
2. Stitch. Turn each scroll video into one tall image by aligning consecutive frames. Drop duplicate frames.
3. Inventory. Look at every canonical image and write inventory.md: the list of apps in home-screen order, every screen in each app, and which tap leads where. Cross-check it against the web research facts and list any disagreement in the final report.
4. Measure. Extract theme tokens from the canonical images: colours, spacing, corner radii, icon sizes, and text sizes.
5. Fonts. Identify the typeface. If it is not freely usable, pick the closest match by metrics and record it in DEVIATIONS.md. Convert to LVGL binary fonts at the sizes measured.
6. Transcribe. Copy all text exactly into the screen JSON files. Then render each screen in the simulator and compare it with the reference. Any text mismatch is a failure.
7. Slice. Crop icons, avatars, photos, and wallpapers from the canonical images, downscale with Lanczos, and convert to RGB565.
8. Video. Convert feed clips to MJPEG at the target width and 12 frames per second, silent.
9. Pack and validate. Build the pack folder, validate against the schemas, check that every referenced asset exists, and print a size report.
10. Sync. Copy the pack to the SD card, or push it over WiFi to the device's upload endpoint in maintenance mode.

Text rendering rule. Render text live with the matched font by default, because it stays sharp at 240 pixels wide. Where live text cannot match the reference (stylised logos, unusual lettering), ship that element as an image slice instead.

Verification. tools/diff.py renders a screen in the simulator, scales the reference to the same size, and reports a similarity score with a side-by-side image. The pass bar is 0.95 structural similarity. Rework any screen below it. A screen that still scores between 0.90 and 0.95 after rework is listed in the final report with its side-by-side image. The side-by-side images go into content/<snapshot-id>/report/ for the owner's review after the run.

## 6. Dynamic and changing content

The device cannot read the game, so changing content is handled with snapshots: each capture session becomes a complete, frozen copy of the phone at that point in the story. Within a snapshot, nothing is invented.

Snapshots

- Each snapshot is one content pack. The SD card can hold several.
- The device boots into the newest snapshot. A hidden menu (hold the status bar for three seconds) lists the snapshots and switches between them.
- A snapshot can declare a parent in its manifest. Apps the owner did not re-capture are inherited from the parent, so an update only needs captures of the apps that changed.
- Updating the device is: capture the changed apps, run ingest, sync the new pack.

| Content in the game | What the clone does |
|---|---|
| Story-driven changes: new messages, contacts, apps unlocking | A new snapshot per capture session |
| Order in which messages and notifications arrived | timeline.json keeps the captured order and in-game timestamps. The device shows the final state. A replay mode that delivers them one by one is optional and off by default |
| Endless or randomised feeds | The captured items, in captured order, looping at the end. Shuffle only if two recordings of the same feed show a different order |
| Clock | Starts at the in-game time captured in the snapshot and runs at the game's time rate, measured from the clock video |
| Date, weather, battery, signal | Frozen at the captured values |
| Actions that need the game world: calls, ordering a ride, purchases | Play the captured phone screens for that flow up to the last captured one, then return to the previous screen. If no flow was captured, the control shows its pressed state and does nothing |
| Camera | The captured viewfinder still or clip. The gallery shows the captured photos |
| Map | The captured map as a stitched image with pan. The player marker stays where it was captured |
| In-game web pages | Stitched page images with tap areas only for links whose targets were captured |
| Video clips | MJPEG playback, silent until audio is added |
| Text entry | The captured keyboard only. Typing never changes stored content |

If you meet a kind of changing content that this table does not cover, add it to MISSING.md and leave that element static. Do not design a behaviour on your own.

## 7. Screen fit and touch

The in-game phone screen is expected to be taller and narrower than the CYD's 3:4 display, so it cannot be shown pixel for pixel. Measure the real aspect ratio during the rectify step and record it in DEVIATIONS.md.

Default: fit-width mode

- Scale every screen so its width is exactly 240 pixels. Proportions are kept.
- Pin the status bar to the top and any bottom bar or dock to the bottom.
- The area between them scrolls vertically when it is taller than the space left.
- Nothing is cropped, rearranged, or resized relative to its neighbours.

Alternative: letterbox mode. A config flag shows the whole phone screen at once, with black bars at the sides. It is exact in proportion but much smaller. Build it only if the owner asks.

Touch

- Gestures: tap, long press, and vertical and horizontal swipe with inertia.
- Tap targets smaller than 28 pixels get an invisible enlarged hit area. Their drawn size does not change.
- Run touch calibration on first boot and from the hidden menu.

### 7.1 Design fidelity: the 1:1 rules

The design is not described in this plan. It is measured from the captures, and these rules make the result a 1:1 copy of what they show.

- One scale factor. Scale = 240 divided by the canonical image width. Every size, margin, radius, and text size is the measured value times this factor, rounded to whole pixels only.
- Sampled colours. Every colour and gradient is sampled from the captures and stored as a theme token.
- No framework look. No default LVGL theme, widget style, font, scrollbar, or animation may be visible anywhere.
- Sliced artwork. Icons, logos, wallpapers, avatars, and photos are cut from the captures. Never redraw, substitute, or regenerate them.
- Same layout. Order, alignment, line breaks, and truncation match the capture for every element.
- Captured states only. Pressed, selected, disabled, and empty states appear only as captured.
- Measured motion. Take each transition's duration and easing from its video, frame by frame, and match the duration within 50 milliseconds.
- Nothing added. No extra buttons, hints, loading indicators, or debug overlays in normal use. The hidden menu is the one exception and is logged in DEVIATIONS.md.
- Two checks per screen. The whole-screen diff must pass, and every text region must pass its own diff so small text errors cannot hide in a good overall score.

## 8. Build phases

Run all phases in order in one run. Commit at the end of each phase. You have no access to the hardware, so every check below runs in the simulator or the build system.

| Phase | Work | Done when |
|---|---|---|
| 0. Bring-up | Display, touch, SD card, backlight, touch calibration, for both display variants | Firmware compiles for both variants and a hardware test screen is included |
| 1. Renderer core | Pack loader, screen JSON to LVGL, navigation stack, gestures, simulator with headless screenshots | A synthetic test pack (plain shapes and text, no game content) renders correctly in the simulator |
| 2. Research and inventory | Web research, rectify, stitch, inventory | research/facts.md and inventory.md exist and their disagreements are listed |
| 3. System shell | Lock screen, home pages, status bar, notifications, app open and close transitions | Every shell screen passes both diffs |
| 4. Apps | Every app in home-screen order: measure, transcribe, slice, pack, diff | Every captured screen of every app passes both diffs |
| 5. Dynamic layer | Snapshot switching and inheritance, timeline, running clock | Simulator tests switch between two snapshots and load inherited apps |
| 6. Video | MJPEG playback in feeds | Clips decode in the simulator and the device build fits in memory |
| 7. Polish | Transition timing, sleep and wake, auto brightness, fast boot | Transition durations match the videos within 50 milliseconds in the simulator |
| 8. Handover | README covering flashing, SD card setup, capture, ingest, sync, and adding a snapshot | The final report in section 10 is written |

Working rules

- If reference/ is empty, finish phases 0 and 1 and the web research, then end the run as section 3 describes.
- Write unit tests for every tool in tools/ and run them before each commit.
- Keep MISSING.md and DEVIATIONS.md current at the end of every phase.
- Do not pause between phases. Note anything that needs the owner in the final report.

## 9. Later: radio hooks

Do not build radio playback now. Build only these hooks so it can be added without restructuring:

- Audio service stub. An interface in src/hal/ with play(source), stop(), set_volume(), and is_playing(). The stub does nothing and returns success.
- Radio app UI. Built from captures like any other app. Its station buttons call the audio stub.
- WiFi manager. Present from phase 1, because sync and the upload endpoint need it. Credentials are stored in NVS and set from the hidden menu.
- Pins. Keep GPIO 26 free for the onboard speaker. Note in the README that an external I2S audio board would need the RGB LED pins (4, 16, 17).
- Pack format. Reserve an audio/ folder per app and a station element type in the schema, both unused for now.

## 10. Defaults and final report

Do not ask the owner anything during the run. Use these defaults and list each one in the final report so the owner can change it afterwards.

| Decision | Default |
|---|---|
| Board variant | Build both ILI9341 and ST7789 firmware. The owner flashes the one that shows the test screen correctly |
| Screen fit | Fit-width. Letterbox is available as a config flag |
| Diff pass bar | 0.95, with 0.90 to 0.95 reported |
| Clock | Runs from the captured in-game time at the measured game rate |
| Replay mode for messages and notifications | Off |
| Typeface, if the game's font is not freely usable | Closest match by metrics, logged in DEVIATIONS.md |

Final report. End the run with REPORT.md containing:

1. What was built in each phase.
2. The diff score of every screen, with links to the side-by-side images for any below 0.95.
3. The contents of MISSING.md as a capture list for the owner.
4. The contents of DEVIATIONS.md.
5. The defaults used from the table above.
6. The owner's steps: flash the firmware, run the hardware test screen, calibrate touch, and copy the pack to the SD card.
