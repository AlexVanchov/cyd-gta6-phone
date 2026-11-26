# Capture checklist

reference/ was empty when the build ran, so the device has no game content yet. This list tells you what to capture. It follows PLAN.md §3 and is tailored to the apps the web research found (research/facts.md).

**Spelling note:** the app names below are as guides spell them. The device will use whatever your captures show. If an app is missing or named differently in your game, capture what you see and note it in notes.md.

## Before you start (PS5)

- [ ] Screenshot format: **PNG**. Video clips: **highest resolution**.
- [ ] **HDR off.**
- [ ] Stand still in a bright, neutral spot. Use the closest, flattest phone view. Don't move the camera during the session.
- [ ] Create `reference/<YYYY-MM-DD>_<story-label>/notes.md` with the in-game date and time (from the phone), your story progress (chapter, last mission), and anything odd.
  - Suggested labels from the research: `start-ch1`, `after-buck-me`, `ch2-after-moses`.

## System (`reference/<id>/_system/`)

- [ ] Lock screen, if the phone has one
- [ ] Every home page (swipe through all of them), each as a screenshot
- [ ] The status bar, close up, in a screenshot where it is not covered
- [ ] Notification panel or Reminders view, if any (research suggests a Reminders count on the home screen)
- [ ] `transitions/`: open the phone, close the phone, open an app from home, go back to home, a notification arriving
- [ ] `clock.mp4`: **two minutes** of the phone clock running, without touching anything

## Apps (`reference/<id>/<app>/screens|scroll|transitions/`)

For every app: a screenshot of each distinct screen, a slow one-direction scroll video (top to bottom) of each list, every item opened, and an open/close transition video.

| App (guide spelling) | Must capture |
|---|---|
| WAiNK | Main screen; a scan result on a parked car; any detail page |
| Contacts | The full A–Z list (scroll video); the Suggested list; **every** contact opened; a call flow, screen by screen, up to the last screen the phone shows |
| Camera | Viewfinder still and a short clip; each mode the UI shows (selfie, grid, filter, light) |
| Snapmatic | Feed (scroll video, recorded **twice** in separate sessions to check whether the order is random); a profile; a post opened |
| Gallery | Grid (scroll video); every photo opened; the options and select menus |
| Fitness | Every screen, with the stat values readable |
| News | List (scroll video); every article opened (scroll video if long) |
| WhatUp | Thread list (scroll video); **every** thread opened and scrolled from top to bottom |
| Settings | Every page: wallpaper, ringtone, third-party plugins |
| Weather | Every screen |
| Scooter Bros | Every screen, including the request flow up to the last phone screen before the game world takes over |
| BuckMe | Every screen: checking, Family Savings, any history list (scroll video) |
| RydeMe | Every screen; the booking flow up to the last phone screen |
| Vice City Real Estate | Every screen and listing (scroll videos) |
| Anything else on your phone | Same as above. The research could not confirm On Demand, Reminders or a radio app; capture them if they are there |

## After capturing

- [ ] Copy everything into `reference/<snapshot-id>/` using the layout above.
- [ ] Run the ingest (README, "Adding a snapshot"). Anything you didn't capture stays off the device and is listed in MISSING.md.
