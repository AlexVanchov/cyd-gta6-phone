"""Build the synthetic test packs (phase 1 / phase 5).

Plain shapes and text only: no game content of any kind. Two snapshots:

  0000-00-00_test-a   full pack: lock, home (2 pages + dock), status bar,
                      apps alpha (scroll list -> detail), beta (video),
                      gamma (run_sequence flow), delta
  0000-00-00_test-b   child of test-a: overrides only app beta, inherits the rest

The ids sort before any real snapshot id (which starts with the real capture
date), so a real snapshot always wins as "newest" on the device.

  python tools/make_test_pack.py [--out sd/packs]
"""
from __future__ import annotations

import argparse
import math
import shutil
from pathlib import Path

from PIL import Image, ImageDraw

from common import ROOT, SD, write_json
import convert
import fonts
import video

A = "0000-00-00_test-a"
B = "0000-00-00_test-b"
UW = 960  # unit width: canonical 4x target (PLAN.md §5)
H = 1280  # 960 x 1280 = 3:4, the CYD's own aspect

FONT_SRC = ROOT / "firmware/.pio/libdeps/ili9341/lvgl/scripts/built_in_font/Montserrat-Medium.ttf"

COLORS = {
    "bg": "#101418",
    "fg": "#F2F4F7",
    "muted": "#8A94A3",
    "accent": "#2F80ED",
    "row": "#1B2129",
    "row_pressed": "#2A3340",
    "a1": "#E5484D",
    "a2": "#30A46C",
    "a3": "#F5A524",
    "a4": "#8E4EC6",
}


def status_bar():
    return {
        "schema": 1, "id": "status_bar", "height": 80,
        "elements": [
            {"type": "text", "id": "sb_time", "x": 40, "y": 16, "w": 300, "h": 56, "font": "sans_14",
             "color": "$color.fg", "text": "09:41", "clock_format": "%H:%M"},
            {"type": "rect", "x": 820, "y": 28, "w": 92, "h": 36, "radius": 8, "border_w": 4,
             "border_color": "$color.fg"},
            {"type": "rect", "x": 828, "y": 36, "w": 60, "h": 20, "radius": 4, "bg": "$color.fg"},
        ],
    }


def lock():
    return {
        "schema": 1, "id": "lock", "height": H, "status_bar": True, "top_h": 80,
        "bg": "$color.bg",
        "elements": [
            {"type": "rect", "x": 0, "y": 80, "w": 960, "h": 1200,
             "bg_grad": {"dir": "ver", "colors": ["#16324F", "#101418"]}},
            {"type": "text", "x": 0, "y": 300, "w": 960, "h": 120, "font": "sans_20", "align": "center",
             "color": "$color.fg", "text": "09:41", "clock_format": "%H:%M"},
            {"type": "text", "x": 0, "y": 430, "w": 960, "h": 80, "font": "sans_14", "align": "center",
             "color": "$color.muted", "text": "Test pack A"},
            {"type": "button", "id": "unlock", "x": 280, "y": 1080, "w": 400, "h": 120, "radius": 60,
             "bg": "$color.accent", "pressed": {"bg": "#1C5FB8"},
             "action": {"type": "open_screen", "target": "_system/home"},
             "children": [
                 {"type": "text", "x": 280, "y": 1110, "w": 400, "h": 60, "font": "sans_14",
                  "align": "center", "color": "#FFFFFF", "text": "Unlock"}]},
        ],
    }


def icon(app, label, color, x, y):
    return {
        "type": "button", "id": f"icon_{app}", "x": x, "y": y, "w": 200, "h": 260,
        "action": {"type": "open_screen", "target": f"{app}/main"},
        "children": [
            {"type": "rect", "x": x + 20, "y": y, "w": 160, "h": 160, "radius": 40, "bg": color},
            {"type": "text", "x": x - 30, "y": y + 180, "w": 260, "h": 60, "font": "sans_14", "align": "center",
             "color": "$color.fg", "text": label},
        ],
    }


def home():
    page1 = {"type": "rect", "x": 0, "y": 80, "w": 960, "h": 900, "children": [
        icon("alpha", "Alpha", "$color.a1", 80, 160),
        icon("beta", "Beta", "$color.a2", 380, 160),
        icon("gamma", "Gamma", "$color.a3", 680, 160),
        icon("delta", "Delta", "$color.a4", 80, 480),
    ]}
    page2 = {"type": "rect", "x": 960, "y": 80, "w": 960, "h": 900, "children": [
        {"type": "text", "x": 960, "y": 400, "w": 960, "h": 80, "font": "sans_14", "align": "center",
         "color": "$color.muted", "text": "Page 2"},
    ]}
    return {
        "schema": 1, "id": "home", "height": H, "status_bar": True, "top_h": 80, "bottom_h": 300,
        "bg": "$color.bg",
        "elements": [
            {"type": "scroll", "id": "pages", "dir": "x", "snap": "page", "x": 0, "y": 80, "w": 960, "h": 900,
             "children": [page1, page2]},
            {"type": "rect", "x": 40, "y": 1000, "w": 880, "h": 240, "radius": 60, "bg": "#1F2630",
             "children": [
                 {"type": "rect", "x": 100, "y": 1040, "w": 160, "h": 160, "radius": 40, "bg": "$color.a2",
                  "action": {"type": "open_screen", "target": "beta/main"}},
                 {"type": "rect", "x": 700, "y": 1040, "w": 160, "h": 160, "radius": 40, "bg": "$color.a1",
                  "action": {"type": "open_screen", "target": "alpha/main"}},
             ]},
        ],
    }


def header(title, back=True):
    els = [{"type": "rect", "x": 0, "y": 80, "w": 960, "h": 140, "bg": "#161B22"},
           {"type": "text", "x": 0, "y": 120, "w": 960, "h": 80, "font": "sans_20", "align": "center",
            "color": "$color.fg", "text": title}]
    if back:
        els.append({"type": "button", "id": "back", "x": 30, "y": 110, "w": 90, "h": 90,
                    "action": {"type": "back"},
                    "children": [{"type": "text", "x": 30, "y": 120, "w": 90, "h": 80, "font": "sans_20",
                                  "align": "center", "color": "$color.accent", "text": "<"}]})
    return els


def alpha_main():
    rows = []
    for i in range(20):
        y = 240 + i * 152
        rows.append({
            "id": f"row{i+1}", "x": 0, "y": y, "w": 960, "h": 144, "bg": "$color.row",
            "pressed": {"bg": "$color.row_pressed"},
            "action": {"type": "open_screen", "target": "alpha/detail"},
            "children": [
                {"type": "rect", "x": 40, "y": y + 30, "w": 80, "h": 80, "radius": 9999, "bg": "$color.a1"},
                {"type": "text", "x": 160, "y": y + 16, "w": 760, "h": 56, "font": "sans_14",
                 "color": "$color.fg", "text": f"Row {i+1}"},
                {"type": "text", "x": 160, "y": y + 68, "w": 760, "h": 48, "font": "sans_14",
                 "color": "$color.muted", "text": "Synthetic list item"},
            ]})
    content_h = 240 + 20 * 152 + 40
    return {
        "schema": 1, "id": "main", "height": content_h, "status_bar": True, "top_h": 220, "bg": "$color.bg",
        "elements": header("Alpha") + [
            {"type": "list", "id": "rows", "x": 0, "y": 240, "w": 960, "h": 20 * 152, "items": rows}],
    }


def alpha_detail():
    return {
        "schema": 1, "id": "detail", "height": H, "status_bar": True, "top_h": 220, "bg": "$color.bg",
        "elements": header("Detail") + [
            {"type": "image", "x": 80, "y": 260, "w": 800, "h": 480, "src": "assets/pattern.bin"},
            {"type": "text", "x": 80, "y": 780, "w": 800, "h": 300, "font": "sans_14", "color": "$color.fg",
             "text": "Plain synthetic text that wraps across several lines to test the label layout."},
        ],
    }


def beta_main(title, bg):
    return {
        "schema": 1, "id": "main", "height": H, "status_bar": True, "top_h": 220, "bg": bg,
        "elements": header(title) + [
            {"type": "video", "id": "clip", "x": 0, "y": 300, "w": 960, "h": 540, "src": "video/bars.mjpeg",
             "autoplay": True, "loop": True},
            {"type": "text", "x": 80, "y": 900, "w": 800, "h": 80, "font": "sans_14", "align": "center",
             "color": "$color.muted", "text": "Synthetic clip"},
        ],
    }


def gamma_main():
    return {
        "schema": 1, "id": "main", "height": H, "status_bar": True, "top_h": 220, "bg": "$color.bg",
        "elements": header("Gamma") + [
            {"type": "button", "id": "flow", "x": 180, "y": 500, "w": 600, "h": 140, "radius": 24,
             "bg": "$color.a3",
             "action": {"type": "run_sequence", "end": "back",
                        "steps": [{"screen": "gamma/step1", "ms": 600}, {"screen": "gamma/step2", "ms": 600}]},
             "children": [{"type": "text", "x": 180, "y": 540, "w": 600, "h": 60, "font": "sans_14",
                           "align": "center", "color": "#101418", "text": "Run flow"}]},
        ],
    }


def gamma_step(n):
    return {"schema": 1, "id": f"step{n}", "height": H, "status_bar": True, "top_h": 220, "bg": "$color.bg",
            "elements": header(f"Step {n}", back=False)}


def delta_main():
    return {"schema": 1, "id": "main", "height": H, "status_bar": True, "top_h": 220, "bg": "$color.bg",
            "elements": header("Delta") + [
                {"type": "rect", "x": 160, "y": 400, "w": 640, "h": 400, "radius": 80, "bg": "$color.a4",
                 "border_w": 12, "border_color": "$color.fg"}]}


def pattern_image(w=200, h=120) -> Image.Image:
    img = Image.new("RGB", (w, h))
    px = img.load()
    for y in range(h):
        for x in range(w):
            px[x, y] = (int(255 * x / (w - 1)), int(255 * y / (h - 1)), 160)
    d = ImageDraw.Draw(img)
    d.ellipse((70, 30, 130, 90), fill=(255, 255, 255))
    d.rectangle((10, 10, 40, 40), fill=(0, 0, 0))
    return img


def bars_frames(w=240, h=135, n=24):
    cols = [(255, 255, 255), (255, 255, 0), (0, 255, 255), (0, 255, 0), (255, 0, 255), (255, 0, 0), (0, 0, 255)]
    frames = []
    for i in range(n):
        img = Image.new("RGB", (w, h))
        d = ImageDraw.Draw(img)
        bw = w / len(cols)
        for k, c in enumerate(cols):
            d.rectangle((int(k * bw), 0, int((k + 1) * bw), h), fill=c)
        x = int((w - 30) * (0.5 + 0.5 * math.sin(2 * math.pi * i / n)))
        d.rectangle((x, h - 40, x + 30, h - 10), fill=(0, 0, 0))
        frames.append(img)
    return frames


def manifest(pid, parent=None, label="A"):
    m = {
        "schema": 1, "id": pid, "parent": parent, "unit_width": UW,
        "label": f"Synthetic test pack {label} (no game content)",
        "apps": [{"id": "alpha", "entry": "main"}, {"id": "beta", "entry": "main"},
                 {"id": "gamma", "entry": "main"}, {"id": "delta", "entry": "main"}],
        "system": {"boot": "_system/lock", "home": "_system/home", "status_bar": "_system/status_bar"},
        "theme": {"color": COLORS},
        "fonts": {"sans_14": {"file": "fonts/sans_14.bin", "source": "Montserrat-Medium.ttf@14"},
                  "sans_20": {"file": "fonts/sans_20.bin", "source": "Montserrat-Medium.ttf@20"}},
        "clock": {"start": "2026-01-01T09:41:00", "rate": 1.0},
        "transitions": {
            "open_app": {"type": "fade_in", "ms": 250, "bezier": [0.25, 0.1, 0.25, 1.0]},
            "push": {"type": "slide_left", "ms": 300, "bezier": [0.4, 0.0, 0.2, 1.0]},
            "pop": {"type": "slide_right", "ms": 300, "bezier": [0.4, 0.0, 0.2, 1.0]},
            "close_app": {"type": "fade_out", "ms": 200, "bezier": [0.25, 0.1, 0.25, 1.0]},
        },
    }
    return m


def build(out: Path) -> list[Path]:
    a, b = out / A, out / B
    for d in (a, b):
        if d.exists():
            shutil.rmtree(d)
    # ---- pack A ----
    write_json(a / "manifest.json", manifest(A))
    write_json(a / "timeline.json", {"schema": 1, "events": [
        {"t": "2026-01-01T09:30:00", "type": "notification", "app": "alpha", "ref": "alpha/detail"}]})
    fonts.convert(FONT_SRC, [14], a / "fonts", "sans")
    fonts.convert(FONT_SRC, [20], a / "fonts", "sans")
    sysd = a / "apps/_system/screens"
    write_json(sysd / "status_bar.json", status_bar())
    write_json(sysd / "lock.json", lock())
    write_json(sysd / "home.json", home())
    write_json(a / "apps/alpha/screens/main.json", alpha_main())
    write_json(a / "apps/alpha/screens/detail.json", alpha_detail())
    (a / "apps/alpha/assets").mkdir(parents=True, exist_ok=True)
    (a / "apps/alpha/assets/pattern.bin").write_bytes(convert.encode(pattern_image()))
    write_json(a / "apps/beta/screens/main.json", beta_main("Beta", "$color.bg"))
    video.write_container(a / "apps/beta/video/bars.mjpeg", bars_frames(), 12.0)
    write_json(a / "apps/gamma/screens/main.json", gamma_main())
    write_json(a / "apps/gamma/screens/step1.json", gamma_step(1))
    write_json(a / "apps/gamma/screens/step2.json", gamma_step(2))
    write_json(a / "apps/delta/screens/main.json", delta_main())
    # ---- pack B: only beta re-captured ----
    mb = {"schema": 1, "id": B, "parent": A, "label": "Synthetic test pack B (no game content)",
          "theme": {"color": {"accent": "#E5484D"}}}
    write_json(b / "manifest.json", mb)
    write_json(b / "apps/beta/screens/main.json", beta_main("Beta B", "#1A1020"))
    video.write_container(b / "apps/beta/video/bars.mjpeg", bars_frames(n=12), 12.0)
    return [a, b]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=SD / "packs")
    a = ap.parse_args(argv)
    for p in build(a.out):
        print(p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
