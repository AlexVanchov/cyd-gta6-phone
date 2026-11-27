"""Render README screenshots of the GatorPhone pack with the headless simulator.

    tools/.venv/bin/python tools/make_screenshots.py   # -> docs/screenshots/*.png

Needs simulator/build/sim (make -C simulator) and the built pack
(tools/make_parody_pack.py). Output is 240x320, the device's own resolution.
"""
import subprocess
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SIM = ROOT / "simulator/build/sim"
PACK = ROOT / "sd/packs/2026-11-26_gatorphone"
OUT = ROOT / "docs/screenshots"

# name -> (screen, scripted input)
SHOTS = {
    "lock": ("_system/lock", None),
    "home": ("_system/home", None),
    "home_widgets": ("_system/home", "swipe:180,150,40,150,300;wait:1500"),
    "phone_main": ("phone/main", None),
    "phone_call_mom": ("phone/call_mom", None),
    "txtz_mom": ("txtz/mom", None),
    "clout_main": ("clout/main", None),
    "news_main": ("news/main", None),
    "news_gator5g": ("news/gator5g", None),
    "facts_main": ("facts/main", None),
    "facts_delays": ("facts/delays", None),
    "hailr_main": ("hailr/main", None),
    "hailr_arriving": ("hailr/arriving", None),
    "grub_main": ("grub/main", None),
    "moola_main": ("moola/main", None),
    "humid_main": ("humid/main", None),
    "condos_main": ("condos/main", None),
    "maps_main": ("maps/main", None),
    "radio_main": ("radio/main", None),
    "wanted_main": ("wanted/main", None),
    "pics_main": ("pics/main", None),
    "settings_about": ("settings/about", None),
}
OVERVIEW = ["lock", "home", "home_widgets", "facts_main", "facts_delays", "news_main",
            "txtz_mom", "hailr_arriving", "moola_main", "humid_main"]


def render(name, screen, inp):
    cmd = [str(SIM), "--pack", str(PACK), "--screen", screen, "--out", str(OUT / f"{name}.png"), "--advance", "600"]
    if inp:
        cmd += ["--input", inp]
    subprocess.run(cmd, check=True, capture_output=True)


def overview(names, cols=5, gap=16, bg=(18, 16, 24)):
    w, h = 240, 320
    rows = (len(names) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * w + (cols + 1) * gap, rows * h + (rows + 1) * gap), bg)
    for i, n in enumerate(names):
        r, c = divmod(i, cols)
        sheet.paste(Image.open(OUT / f"{n}.png").convert("RGB"), (gap + c * (w + gap), gap + r * (h + gap)))
    sheet.save(OUT / "overview.png", optimize=True)


def main():
    if not SIM.exists():
        sys.exit("build the simulator first: make -C simulator")
    if not PACK.exists():
        sys.exit("build the pack first: tools/make_parody_pack.py")
    OUT.mkdir(parents=True, exist_ok=True)
    for name, (screen, inp) in SHOTS.items():
        render(name, screen, inp)
    overview(OVERVIEW)
    print(f"{len(SHOTS)} screenshots + overview.png -> {OUT}")


if __name__ == "__main__":
    main()
