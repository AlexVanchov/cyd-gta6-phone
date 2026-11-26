# Missing captures

Last updated 2026-11-26, end of the first build run.

reference/ was **empty** when this run started, so **no game screen could be built**. Per PLAN.md rule 3, the device ships with no game content. It boots into the synthetic test packs, which contain plain shapes and text only. CAPTURE_CHECKLIST.md is the step-by-step version of this list.

## Needed before any game screen can exist

| Area | What is needed | Blocks |
|---|---|---|
| Snapshot | A first capture session in `reference/<date>_<label>/` with notes.md (in-game date and time, story progress) | everything |
| System | Lock screen (if any), all home pages, status bar, notification/Reminders panel | phase 3 |
| System | Transition videos: phone open/close, app open/close, back, notification arrival | measured transitions (phase 7) |
| System | 2-minute clock video | clock rate (phase 5) |
| Typeface | Captures with plenty of text at several sizes, to identify the font | fonts (phase 4) |
| Apps | Every app the research lists: WAiNK, Contacts, Camera, Snapmatic, Gallery, Fitness, News, WhatUp, Settings, Weather, Scooter Bros, BuckMe, RydeMe, Vice City Real Estate | phase 4 |
| Apps (unverified) | Reminders, On Demand, radio: only if they are actually on your phone | phase 4 |
| Feeds | Two separate recordings of each feed (e.g. Snapmatic, News), to decide captured order vs shuffle | §6 |
| Flows | Calls, rides, deliveries, purchases: every phone screen up to the last one before the game world takes over | `run_sequence` flows |
| Map | If the phone has a map: a pan video across it, for stitching | §6 |
| Video | Any feed clips, recorded on the phone screen | phase 6 with real content |

## Changing content with no rule in PLAN.md §6

None found yet. Any found during ingest will be listed here and left static.
