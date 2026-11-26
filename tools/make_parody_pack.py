"""Build the GatorPhone VI parody pack: an original, in-universe-style phone.

Everything here is original: app names, jokes, layout, icons and the generated
pictures. No game assets, screenshots, logos or icons are used. The "VI Facts"
app holds real facts about GTA VI, written in our own words (research/parody.md
lists the sources). Fonts: Inter, Anton, Bebas Neue, Pacifico (SIL OFL) and Font
Awesome Free 5 icons (CC BY 4.0), see parody/fonts/.

Coordinates are device pixels (unit_width 240).

  python tools/make_parody_pack.py [--out sd/packs]
"""
from __future__ import annotations

import argparse
import math
import random
import shutil
import subprocess
from pathlib import Path

import numpy as np
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from common import ROOT, SD, write_json
import convert
import video

PACK = "2026-11-26_gatorphone"
W, H = 240, 320
SB = 20          # status bar height
HDR = 56         # status bar + app header
FONT_DIR = ROOT / "parody/fonts"
FA = ROOT / "firmware/.pio/libdeps/ili9341/lvgl/scripts/built_in_font/FontAwesome5-Solid+Brands+Regular.woff"

# ------------------------------------------------------------------ fonts
INTER5 = FONT_DIR / "inter-latin-500-normal.woff"
INTER7 = FONT_DIR / "inter-latin-700-normal.woff"
INTER8 = FONT_DIR / "inter-latin-800-normal.woff"
ANTON = FONT_DIR / "Anton-Regular.ttf"
BEBAS = FONT_DIR / "BebasNeue-Regular.ttf"
PACIFICO = FONT_DIR / "Pacifico-Regular.ttf"

# key: (file, size, bpp)
FONTS = {
    "t11": (INTER5, 11, 4),
    "t12": (INTER5, 12, 4),
    "t14": (INTER5, 14, 4),
    "b12": (INTER7, 12, 4),
    "b14": (INTER7, 14, 4),
    "b17": (INTER8, 17, 4),
    "d22": (ANTON, 22, 4),
    "n40": (BEBAS, 40, 4),
    "clock": (BEBAS, 76, 2),
    "s26": (PACIFICO, 26, 4),
    "ico22": (None, 22, 4),   # icons only (Font Awesome)
}
USED: dict[str, set[str]] = {k: set() for k in FONTS}
_pil: dict[str, ImageFont.FreeTypeFont] = {}


def pil(key: str) -> ImageFont.FreeTypeFont:
    if key not in _pil:
        f, s, _ = FONTS[key]
        _pil[key] = ImageFont.truetype(str(f), s)
    return _pil[key]


def line_h(key: str) -> int:
    a, d = pil(key).getmetrics()
    return a + d


def wrap(key: str, text: str, width: int) -> list[str]:
    """Greedy word wrap with the same font; a few px of slack for LVGL."""
    f = pil(key)
    lines = []
    for para in text.split("\n"):
        cur = ""
        for word in para.split(" "):
            t = word if not cur else cur + " " + word
            if f.getlength(t) <= width - 9 or not cur:
                cur = t
            else:
                lines.append(cur)
                cur = word
        lines.append(cur)
    return lines


def text_h(key: str, text: str, width: int, ls: int = 0) -> int:
    n = len(wrap(key, text, width))
    return n * line_h(key) + (n - 1) * ls + 2


# Font Awesome 5 glyphs
G = {
    "phone": "", "comment": "", "fire": "", "news": "", "bulb": "",
    "cloudsun": "", "car": "", "burger": "", "piggy": "", "house": "",
    "heart": "", "run": "", "radio": "", "map": "", "star": "",
    "cog": "", "images": "", "lock": "", "signal": "", "wifi": "",
    "battery": "", "back": "", "chev": "", "pin": "", "sun": "",
    "cloud": "", "rain": "", "bolt": "", "check": "", "user": "",
    "mic": "", "phoneoff": "", "play": "", "music": "", "shield": "",
    "dollar": "", "bell": "", "search": "", "water": "", "skull": "",
    "ghost": "", "crown": "", "drop": "", "smile": "", "camera": "",
    "pause": "", "next": "", "prev": "", "plane": "", "moon": "",
    "info": "", "clock": "", "send": "", "plus": "", "dots": "",
}

C = {
    "bg": "#0E0B16", "surface": "#1A1426", "surface2": "#251C36", "line": "#2E2440",
    "fg": "#FFF4EC", "muted": "#A99BB8", "dim": "#6E6280",
    "pink": "#FF3D8B", "orange": "#FF8A3D", "yellow": "#FFD23F", "teal": "#19D3C5",
    "purple": "#7B2FF7", "green": "#2BD67B", "red": "#FF4D4D", "blue": "#3DA5FF",
}

# ------------------------------------------------------------------ element helpers


def T(x, y, w, h, text, font="t14", color="$color.fg", align=None, valign=None, mode=None, ls=None, **kw):
    USED[font].update(text)
    if mode in ("dots", "clip") and valign == "center" and h > line_h(font):
        lh = line_h(font)
        y, h, valign = y + (h - lh) // 2, lh, None
    e = {"type": "text", "x": x, "y": y, "w": w, "h": h, "font": font, "color": color, "text": text}
    if align:
        e["align"] = align
    if valign:
        e["valign"] = valign
    if mode:
        e["mode"] = mode
    if ls is not None:
        e["line_space"] = ls
    e.update(kw)
    return e


def CLK(x, y, w, h, fmt, font, color="$color.fg", align="center", sample="00:00"):
    USED[font].update("0123456789:" + sample)
    return {"type": "text", "x": x, "y": y, "w": w, "h": h, "font": font, "color": color, "text": sample,
            "clock_format": fmt, "align": align}


def R(x, y, w, h, bg=None, radius=None, grad=None, children=None, action=None, pressed=None, **kw):
    e = {"type": "button" if action else "rect", "x": x, "y": y, "w": w, "h": h}
    if bg:
        e["bg"] = bg
    if grad:
        e["bg_grad"] = {"dir": grad[2] if len(grad) > 2 else "ver", "colors": [grad[0], grad[1]]}
    if radius is not None:
        e["radius"] = radius
    if children:
        e["children"] = children
    if action:
        e["action"] = action
    if pressed:
        e["pressed"] = pressed
    e.update(kw)
    return e


def IMG(x, y, w, h, src, **kw):
    e = {"type": "image", "x": x, "y": y, "w": w, "h": h, "src": src}
    e.update(kw)
    return e


def go(target, transition=None):
    a = {"type": "open_screen", "target": target}
    if transition:
        a["transition"] = transition
    return a


BACK = {"type": "back"}


def seq(steps, end="back"):
    return {"type": "run_sequence", "steps": [{"screen": s, "ms": ms} for s, ms in steps], "end": end}


def screen(sid, elements, height=H, top_h=HDR, bottom_h=0, bg="$color.bg", status_bar=True):
    s = {"schema": 1, "id": sid, "height": max(H, height), "status_bar": status_bar, "top_h": top_h,
         "bg": bg, "elements": elements}
    if bottom_h:
        s["bottom_h"] = bottom_h
    return s


def header(title, font="d22", color="$color.fg", bg="$color.bg", back=True, accent="$color.pink", right=None):
    els = [R(0, 0, W, HDR, bg=bg),
           T(44, SB, 152, HDR - SB, title, font, color, align="center", valign="center", mode="dots")]
    if back:
        els.append(R(0, SB, 44, HDR - SB, action=BACK, pressed={"opa": 150},
                     children=[T(6, SB, 32, HDR - SB, G["back"], "t14", accent, align="center", valign="center")]))
    if right:
        els.append(right)
    els.append(R(0, HDR - 1, W, 1, bg="$color.line"))
    return els


def avatar(x, y, size, initials, c1, c2, font="b14"):
    return R(x, y, size, size, radius=9999, grad=(c1, c2),
             children=[T(x, y, size, size, initials, font, "#FFFFFF", align="center", valign="center")])


def chip(x, y, label, color):
    w = int(pil("b12").getlength(label.upper())) + 12
    return R(x, y, w, 16, bg=color, radius=8,
             children=[T(x, y, w, 16, label.upper(), "b12", "#0E0B16", align="center", valign="center")]), w


def stars(x, y, n_on, total=5, font="t14", on="$color.yellow", off="#FFFFFF33", step=16):
    return [T(x + i * step, y, step, 18, G["star"], font, on if i < n_on else off) for i in range(total)]


# ------------------------------------------------------------------ pictures (procedural, original)
SS = 3  # supersampling


def lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def hexrgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def vgrad(d, box, c1, c2):
    x0, y0, x1, y1 = box
    for y in range(y0, y1):
        t = (y - y0) / max(1, (y1 - y0 - 1))
        d.line((x0, y, x1, y), fill=lerp(c1, c2, t))


def palm(d, x, y, height, lean, color, sway=0.0, s=1.0):
    """Palm silhouette with its base at (x, y)."""
    pts = []
    for i in range(21):
        t = i / 20
        px = x + lean * t * t * height
        py = y - t * height
        pts.append((px, py))
    for i in range(len(pts) - 1):
        wdt = (7 - 4 * i / 20) * s
        d.line((pts[i], pts[i + 1]), fill=color, width=max(1, int(wdt)))
    tx, ty = pts[-1]
    for k in range(8):
        ang = -math.pi + k * (math.pi / 7) + sway
        length = height * (0.55 + 0.12 * math.sin(k * 1.7))
        poly = []
        for i in range(12):
            t = i / 11
            lx = tx + math.cos(ang) * length * t
            ly = ty + math.sin(ang) * length * t * 0.55 + (t * t) * length * 0.55
            poly.append((lx, ly))
        upper = [(px, py - (1 - abs(0.5 - i / 11) * 2) * 6 * s) for i, (px, py) in enumerate(poly)]
        lower = [(px, py + (1 - abs(0.5 - i / 11) * 2) * 3 * s) for i, (px, py) in enumerate(poly)]
        d.polygon(upper + lower[::-1], fill=color)
    d.ellipse((tx - 5 * s, ty - 4 * s, tx + 5 * s, ty + 5 * s), fill=color)


def finish(img, size):
    return img.resize(size, Image.LANCZOS)


def scene_sunset(w, h, seed=0, phase=0.0, palms=True, hz_frac=0.62, r_frac=0.30):
    rnd = random.Random(seed)
    W2, H2 = w * SS, h * SS
    img = Image.new("RGB", (W2, H2))
    d = ImageDraw.Draw(img)
    hz = int(H2 * hz_frac)
    vgrad(d, (0, 0, W2, hz), (32, 10, 70), (255, 92, 122))
    # sun with stripes
    r = int(min(W2, H2) * r_frac)
    cx, cy = W2 // 2, hz - int(r * 0.25)
    sun = Image.new("RGB", (2 * r, 2 * r))
    vgrad(ImageDraw.Draw(sun), (0, 0, 2 * r, 2 * r), (255, 214, 70), (255, 61, 139))
    mask = Image.new("L", (2 * r, 2 * r), 0)
    md = ImageDraw.Draw(mask)
    md.ellipse((0, 0, 2 * r - 1, 2 * r - 1), fill=255)
    for k in range(6):
        yy = int(r * (1.05 + k * 0.17 + (phase * 0.17) % 0.17))
        md.rectangle((0, yy, 2 * r, yy + int(2 + k * 1.6) * SS // 2), fill=0)
    img.paste(sun, (cx - r, cy - r), mask)
    # sea
    vgrad(d, (0, hz, W2, H2), (58, 28, 113), (10, 6, 22))
    for k in range(14):
        yy = hz + 4 * SS + k * (H2 - hz) // 14
        half = int(r * (1.0 - k / 16) * (0.7 + 0.3 * math.sin(phase * 2 * math.pi + k)))
        d.rectangle((cx - half, yy, cx + half, yy + SS * 2), fill=(255, 110, 140))
    if palms:
        sil = (20, 8, 38)
        palm(d, int(W2 * 0.12), H2 + 10, H2 * 0.75, 0.18, sil, sway=0.05 * math.sin(phase * 2 * math.pi), s=SS)
        palm(d, int(W2 * 0.92), H2 + 10, H2 * 0.62, -0.22, sil, sway=0.05 * math.cos(phase * 2 * math.pi), s=SS)
    return finish(img, (w, h))


def scene_skyline(w, h, seed=1):
    rnd = random.Random(seed)
    W2, H2 = w * SS, h * SS
    img = Image.new("RGB", (W2, H2))
    d = ImageDraw.Draw(img)
    vgrad(d, (0, 0, W2, H2), (25, 12, 60), (233, 84, 120))
    x = 0
    while x < W2:
        bw = rnd.randint(14, 34) * SS
        bh = rnd.randint(int(H2 * 0.25), int(H2 * 0.8))
        col = (rnd.randint(18, 30), rnd.randint(10, 20), rnd.randint(40, 60))
        d.rectangle((x, H2 - bh, x + bw, H2), fill=col)
        for wy in range(H2 - bh + 6 * SS, H2 - 4 * SS, 7 * SS):
            for wx in range(x + 3 * SS, x + bw - 3 * SS, 6 * SS):
                if rnd.random() < 0.35:
                    d.rectangle((wx, wy, wx + 2 * SS, wy + 3 * SS), fill=rnd.choice([(255, 210, 90), (255, 140, 200), (120, 230, 255)]))
        if rnd.random() < 0.3:
            d.rectangle((x + 2 * SS, H2 - bh - 3 * SS, x + bw - 2 * SS, H2 - bh - SS), fill=(255, 61, 139))
        x += bw + rnd.randint(0, 3) * SS
    return finish(img, (w, h))


def scene_beach(w, h, seed=2):
    W2, H2 = w * SS, h * SS
    img = Image.new("RGB", (W2, H2))
    d = ImageDraw.Draw(img)
    vgrad(d, (0, 0, W2, int(H2 * 0.5)), (80, 190, 255), (190, 240, 255))
    d.ellipse((W2 * 0.72, H2 * 0.08, W2 * 0.86, H2 * 0.08 + W2 * 0.14), fill=(255, 236, 140))
    vgrad(d, (0, int(H2 * 0.5), W2, int(H2 * 0.72)), (25, 200, 200), (20, 150, 190))
    for k in range(5):
        yy = int(H2 * 0.52) + k * 7 * SS
        d.line((0, yy, W2, yy + 2 * SS), fill=(160, 250, 245), width=SS)
    d.polygon([(0, H2 * 0.75), (W2, H2 * 0.66), (W2, H2), (0, H2)], fill=(245, 214, 160))
    ux, uy = int(W2 * 0.32), int(H2 * 0.62)
    ur = int(W2 * 0.16)
    for k in range(6):
        col = (255, 61, 139) if k % 2 == 0 else (255, 255, 255)
        d.pieslice((ux - ur, uy - ur // 2, ux + ur, uy + ur // 2), 180 + k * 30, 180 + (k + 1) * 30, fill=col)
    d.line((ux, uy, ux + SS * 4, int(H2 * 0.92)), fill=(90, 60, 40), width=SS * 2)
    d.rectangle((int(W2 * 0.55), int(H2 * 0.84), int(W2 * 0.78), int(H2 * 0.88)), fill=(255, 138, 61))
    palm(d, int(W2 * 0.95), H2, H2 * 0.85, -0.25, (40, 90, 60), s=SS)
    return finish(img, (w, h))


def scene_swamp(w, h, seed=3):
    rnd = random.Random(seed)
    W2, H2 = w * SS, h * SS
    img = Image.new("RGB", (W2, H2))
    d = ImageDraw.Draw(img)
    hz = int(H2 * 0.6)
    vgrad(d, (0, 0, W2, hz), (8, 20, 40), (30, 70, 80))
    d.ellipse((W2 * 0.62, H2 * 0.1, W2 * 0.62 + W2 * 0.16, H2 * 0.1 + W2 * 0.16), fill=(235, 240, 210))
    vgrad(d, (0, hz, W2, H2), (20, 50, 55), (5, 12, 18))
    for k in range(7):
        tx = rnd.randint(0, W2)
        th = rnd.randint(int(H2 * 0.3), int(H2 * 0.55))
        d.polygon([(tx - 10 * SS, hz), (tx + 10 * SS, hz), (tx + 2 * SS, hz - th), (tx - 2 * SS, hz - th)], fill=(6, 18, 22))
        for j in range(4):
            yy = hz - th + j * th // 5
            d.ellipse((tx - (16 - j) * SS, yy, tx + (16 - j) * SS, yy + 10 * SS), fill=(10, 28, 30))
    # the gator: two eyes and a snout line
    gx, gy = int(W2 * 0.45), int(H2 * 0.78)
    d.ellipse((gx, gy, gx + 5 * SS, gy + 4 * SS), fill=(255, 210, 60))
    d.ellipse((gx + 12 * SS, gy, gx + 17 * SS, gy + 4 * SS), fill=(255, 210, 60))
    d.line((gx - 10 * SS, gy + 6 * SS, gx + 40 * SS, gy + 6 * SS), fill=(30, 60, 40), width=2 * SS)
    for k in range(10):
        yy = hz + 5 * SS + k * 6 * SS
        x0 = rnd.randint(0, W2 // 2)
        d.line((x0, yy, x0 + rnd.randint(20, 60) * SS, yy), fill=(60, 100, 110), width=SS)
    return finish(img, (w, h))


def scene_condo(w, h, seed=4, body=(255, 170, 190), trim=(255, 255, 255), sky=((120, 210, 255), (255, 200, 220))):
    rnd = random.Random(seed)
    W2, H2 = w * SS, h * SS
    img = Image.new("RGB", (W2, H2))
    d = ImageDraw.Draw(img)
    vgrad(d, (0, 0, W2, H2), sky[0], sky[1])
    bx0, bx1 = int(W2 * 0.18), int(W2 * 0.82)
    top = int(H2 * 0.18)
    d.rectangle((bx0, top, bx1, H2), fill=body)
    d.rectangle((bx0, top, bx1, top + 6 * SS), fill=trim)
    d.rectangle((int(W2 * 0.45), top - 14 * SS, int(W2 * 0.55), top), fill=trim)
    rows = 5
    for r in range(rows):
        yy = top + 14 * SS + r * (H2 - top - 20 * SS) // rows
        for c in range(4):
            xx = bx0 + 10 * SS + c * (bx1 - bx0 - 20 * SS) // 4
            d.rectangle((xx, yy, xx + 18 * SS, yy + 12 * SS), fill=(40, 80, 120))
            d.rectangle((xx - 2 * SS, yy + 12 * SS, xx + 20 * SS, yy + 14 * SS), fill=trim)
    d.rectangle((0, int(H2 * 0.92), W2, H2), fill=(60, 170, 90))
    palm(d, int(W2 * 0.1), H2, H2 * 0.7, 0.15, (30, 110, 60), s=SS)
    return finish(img, (w, h))


def scene_map(w, h, seed=5):
    rnd = random.Random(seed)
    W2, H2 = w * SS, h * SS
    img = Image.new("RGB", (W2, H2), (40, 120, 200))
    d = ImageDraw.Draw(img)
    # coastline: land on the left/top, ragged edge
    pts = [(0, 0), (int(W2 * 0.78), 0)]
    y = 0
    while y < H2:
        y += 12 * SS
        x = int(W2 * (0.62 + 0.12 * math.sin(y / (40 * SS)) + rnd.uniform(-0.03, 0.03)))
        pts.append((x, y))
    pts += [(0, H2)]
    d.polygon(pts, fill=(236, 222, 186))
    # swamp and park blobs
    for k in range(5):
        cx, cy = rnd.randint(0, int(W2 * 0.5)), rnd.randint(0, H2)
        rr = rnd.randint(18, 36) * SS
        d.ellipse((cx - rr, cy - rr // 2, cx + rr, cy + rr // 2), fill=(110, 170, 110))
    # keys (islands)
    for k in range(6):
        cx = int(W2 * (0.82 + 0.03 * k))
        cy = int(H2 * (0.55 + 0.07 * k))
        d.ellipse((cx - 7 * SS, cy - 3 * SS, cx + 7 * SS, cy + 3 * SS), fill=(236, 222, 186))
    # roads
    for k in range(6):
        yy = rnd.randint(10, H2 // SS - 10) * SS
        d.line((0, yy, int(W2 * 0.7), yy + rnd.randint(-20, 20) * SS), fill=(255, 255, 255), width=2 * SS)
    for k in range(4):
        xx = rnd.randint(10, int(w * 0.6)) * SS
        d.line((xx, 0, xx + rnd.randint(-30, 30) * SS, H2), fill=(255, 255, 255), width=2 * SS)
    d.line((int(W2 * 0.3), 0, int(W2 * 0.45), H2), fill=(255, 200, 60), width=4 * SS)
    d.line((int(W2 * 0.78), int(H2 * 0.5), int(W2 * 0.98), int(H2 * 0.92)), fill=(255, 200, 60), width=3 * SS)
    return finish(img, (w, h))


def scene_flamingo(w, h, seed=6):
    W2, H2 = w * SS, h * SS
    img = Image.new("RGB", (W2, H2))
    d = ImageDraw.Draw(img)
    vgrad(d, (0, 0, W2, H2), (255, 200, 160), (255, 120, 170))
    d.rectangle((0, int(H2 * 0.75), W2, H2), fill=(80, 160, 200))
    cx, cy = int(W2 * 0.5), int(H2 * 0.45)
    pink = (255, 80, 150)
    d.ellipse((cx - 26 * SS, cy - 12 * SS, cx + 22 * SS, cy + 14 * SS), fill=pink)
    d.line((cx + 14 * SS, cy - 4 * SS, cx + 18 * SS, cy - 30 * SS), fill=pink, width=5 * SS)
    d.line((cx + 18 * SS, cy - 30 * SS, cx + 10 * SS, cy - 40 * SS), fill=pink, width=5 * SS)
    d.ellipse((cx + 4 * SS, cy - 46 * SS, cx + 16 * SS, cy - 36 * SS), fill=pink)
    d.polygon([(cx + 4 * SS, cy - 40 * SS), (cx - 6 * SS, cy - 34 * SS), (cx + 4 * SS, cy - 36 * SS)], fill=(30, 20, 30))
    d.line((cx - 2 * SS, cy + 12 * SS, cx - 2 * SS, int(H2 * 0.85)), fill=pink, width=2 * SS)
    d.line((cx + 4 * SS, cy + 12 * SS, cx + 12 * SS, cy + 26 * SS), fill=pink, width=2 * SS)
    d.line((cx + 12 * SS, cy + 26 * SS, cx + 4 * SS, cy + 32 * SS), fill=pink, width=2 * SS)
    # sunglasses, obviously
    d.rectangle((cx + 6 * SS, cy - 44 * SS, cx + 18 * SS, cy - 40 * SS), fill=(20, 20, 20))
    return finish(img, (w, h))


def palm_sprite(w, h, lean, sway=0.0):
    W2, H2 = w * SS, h * SS
    img = Image.new("RGBA", (W2, H2), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    palm(d, int(W2 * (0.25 if lean > 0 else 0.75)), H2 + 4, H2 * 0.8, lean, (20, 8, 38, 255), sway=sway, s=SS)
    return img.resize((w, h), Image.LANCZOS)


# ------------------------------------------------------------------ status bar and wallpaper


def sb_elements(carrier=False):
    left = T(10, 3, 80, 15, "SwampTel", "b12", "$color.fg") if carrier else CLK(10, 3, 60, 15, "%H:%M", "b12", align="left")
    return [left,
            T(130, 3, 102, 15, f"5G  {G['signal']}  {G['wifi']}  {G['battery']}", "t12", "$color.fg", align="right")]


def status_bar():
    return {"schema": 1, "id": "status_bar", "height": SB, "elements": sb_elements()}


def wallpaper(dim=False, palms=True):
    """Retro sunset built from LVGL shapes (no image reads, fast to redraw)."""
    hz = 200
    sky = [(20, 10, 46), (91, 31, 114), (240, 89, 122)]

    def sky_at(y):
        if y < 120:
            return lerp(sky[0], sky[1], y / 120)
        return lerp(sky[1], sky[2], (y - 120) / 80)

    def hx(c):
        return "#%02X%02X%02X" % c
    els = [R(0, 0, W, 120, grad=(hx(sky[0]), hx(sky[1]))),
           R(0, 120, W, 80, grad=(hx(sky[1]), hx(sky[2]))),
           R(70, 116, 100, 100, radius=9999, grad=("#FFD23F", "#FF3D8B"))]
    for k, (yy, hh) in enumerate([(168, 2), (177, 3), (186, 4), (195, 5)]):
        els.append(R(60, yy, 120, hh, bg=hx(sky_at(yy))))
    els.append(R(0, hz, W, H - hz, grad=("#3A1C71", "#0B0716")))
    for k in range(9):
        half = int(46 * (1 - k / 11))
        els.append(R(120 - half, hz + 6 + k * 12, 2 * half, 2, bg="#FF6E8C", opa=200 - k * 18))
    if palms:  # images with alpha are read line by line from the card: keep them off busy screens
        els.append(IMG(-8, 92, 96, 228, "assets/palm_l.bin"))
        els.append(IMG(160, 120, 88, 200, "assets/palm_r.bin"))
    if dim:
        els.append(R(0, 0, W, H, bg="#0E0B1680"))
    return els


# ------------------------------------------------------------------ apps on the home screen

APPS = [
    # id, label, glyph, c1, c2
    ("phone", "Phone", "phone", "#2BD67B", "#13A15B"),
    ("txtz", "Txtz", "comment", "#3DA5FF", "#2357D9"),
    ("clout", "Clout", "fire", "#FF3D8B", "#FF8A3D"),
    ("pics", "Pics", "images", "#FFD23F", "#FF8A3D"),
    ("news", "News", "news", "#FF4D4D", "#B3123A"),
    ("facts", "VI Facts", "bulb", "#7B2FF7", "#FF3D8B"),
    ("humid", "Humid", "cloudsun", "#19D3C5", "#3DA5FF"),
    ("hailr", "Hailr", "car", "#FFD23F", "#F59E0B"),
    ("grub", "Grub", "burger", "#FF8A3D", "#E5484D"),
    ("moola", "Moola", "piggy", "#2BD67B", "#19D3C5"),
    ("condos", "Condos", "house", "#FFB3C7", "#FF3D8B"),
    ("sweat", "Sweat", "run", "#FF3D8B", "#7B2FF7"),
    ("radio", "Radio", "radio", "#7B2FF7", "#3DA5FF"),
    ("maps", "Maps", "map", "#2BD67B", "#3DA5FF"),
    ("wanted", "Wanted", "star", "#FFD23F", "#FF4D4D"),
    ("settings", "Settings", "cog", "#8A8FA3", "#4B4F63"),
]
APP = {a[0]: a for a in APPS}
OPEN = {"type": "cover_up", "ms": 260, "bezier": [0.2, 0.8, 0.2, 1.0]}


def icon(app, x, y, label=True, size=44):
    _, lab, g, c1, c2 = APP[app]
    kids = [R(x, y, size, size, radius=12, grad=(c1, c2)),
            T(x, y, size, size, G[g], "ico22", "#FFFFFF", align="center", valign="center")]
    if label:
        kids.append(T(x - 8, y + size + 3, size + 16, 14, lab, "t11", "$color.fg", align="center", mode="clip"))
    return R(x - 6, y - 2, size + 12, size + (20 if label else 4), action=go(f"{app}/main", OPEN),
             pressed={"opa": 140}, children=kids)


def lock():
    # One opaque picture (sky, sun, sea, palms): read sequentially from the card,
    # unlike shapes plus alpha palms, which made redraws slow.
    els = sb_elements(carrier=True)
    els.append(T(0, 22, W, 16, G["lock"], "t14", "#FFFFFFCC", align="center"))
    els.append(CLK(0, 34, W, 80, "%H:%M", "clock", sample="18:30"))
    els.append(CLK(0, 112, W, 20, "%A, %B %e", "b14", sample="Thursday, November 19"))
    els.append(T(0, 132, W, 16, "Port Sunburn  " + G["sun"] + "  94°", "t12", "#FFFFFFCC", align="center"))

    def notif(y, app, title, body, target):
        _, lab, g, c1, c2 = APP[app]
        return R(10, y, 220, 46, bg="#140E22D9", radius=12, action=go(target), pressed={"bg": "#2A2040E6"}, children=[
            R(18, y + 8, 20, 20, radius=6, grad=(c1, c2),
              children=[T(18, y + 8, 20, 20, G[g], "t11", "#FFFFFF", align="center", valign="center")]),
            T(44, y + 6, 120, 14, title, "b12", "$color.fg"),
            T(170, y + 6, 52, 14, "now" if app == "txtz" else "2m ago", "t11", "$color.muted", align="right"),
            T(44, y + 22, 180, 16, body, "t12", "#FFF4ECDD", mode="dots"),
        ])
    els.append(notif(170, "txtz", "Mom", "The alligator is back in the pool.", "txtz/mom"))
    els.append(notif(222, "clout", "Clout", "@FloridaManDaily: pelicans have lawyers now", "clout/main"))
    els.append(R(64, 284, 112, 26, bg="#FFFFFF2E", radius=13, action=go("_system/home", {"type": "none", "ms": 0}),
                 pressed={"bg": "#FFFFFF55"},
                 children=[T(64, 284, 112, 26, "Tap to unlock", "b12", "$color.fg", align="center", valign="center")]))
    return {"schema": 1, "id": "lock", "height": H, "status_bar": False, "top_h": 0, "bg": "$color.bg",
            "bg_image": "assets/lock_wall.bin", "elements": els}


def home():
    els = wallpaper(dim=True, palms=False) + sb_elements()
    grid = ["news", "facts", "humid", "hailr", "grub", "moola", "condos", "sweat", "radio", "maps", "wanted", "settings"]
    page1 = []
    for i, a in enumerate(grid):
        col, row = i % 4, i // 4
        page1.append(icon(a, 13 + col * 58, 34 + row * 72))
    p2 = []
    x0 = W
    p2.append(R(x0 + 8, 30, 224, 96, bg="#1A1426E0", radius=16, action=go("facts/main", OPEN), pressed={"opa": 160}, children=[
        T(x0 + 20, 40, 150, 14, G["bulb"] + "  VI FACT OF THE DAY", "b12", "$color.teal"),
        T(x0 + 20, 60, 200, 58, "GTA V came out in 2013. GTA VI arrived in 2026. That's 13 years of “any day now”.",
          "t12", "$color.fg", ls=1),
    ]))
    p2.append(R(x0 + 8, 134, 108, 104, bg="#1A1426E0", radius=16, action=go("humid/main", OPEN), pressed={"opa": 160}, children=[
        T(x0 + 18, 142, 90, 14, "Port Sunburn", "b12", "$color.fg"),
        T(x0 + 18, 156, 90, 44, "94°", "n40", "$color.yellow"),
        T(x0 + 18, 200, 90, 30, "Feels like soup.\nH: 97°  L: 91°", "t11", "$color.muted"),
    ]))
    p2.append(R(x0 + 124, 134, 108, 104, bg="#1A1426E0", radius=16, action=go("wanted/main", OPEN), pressed={"opa": 160}, children=[
        T(x0 + 134, 142, 90, 14, "WANTED LEVEL", "b12", "$color.red"),
        *stars(x0 + 134, 166, 0, step=17),
        T(x0 + 134, 194, 90, 36, "Zero. For now.\nKeep it that way.", "t11", "$color.muted"),
    ]))
    els.append({"type": "scroll", "id": "pages", "dir": "x", "snap": "page", "x": 0, "y": 24, "w": W, "h": 220,
                "children": page1 + p2})
    els.append(R(108, 246, 6, 6, radius=9999, bg="#FFFFFFDD"))
    els.append(R(126, 246, 6, 6, radius=9999, bg="#FFFFFF66"))
    els.append(R(8, 258, 224, 58, bg="#FFFFFF24", radius=20))
    for i, a in enumerate(["phone", "txtz", "clout", "pics"]):
        els.append(icon(a, 22 + i * 54, 265, label=False))
    return {"schema": 1, "id": "home", "height": H, "status_bar": False, "top_h": 0, "bg": "$color.bg", "elements": els}


# ------------------------------------------------------------------ Phone

CONTACTS = [
    ("mom", "Mom", "MO", "#FF3D8B", "#FF8A3D", "Calls 6 times a day. Answer.", "(305) 555-0112",
     "Hi sweetie, it's Mom. You didn't answer, so I assume you're in a ditch. Call me back. Also bring sunscreen."),
    ("dwayne", "Cousin Dwayne", "CD", "#FFD23F", "#FF8A3D", "Owes you $40 since 2013", "(305) 555-0140",
     "Yo it's Dwayne. Leave a message, unless it's about the forty bucks. Then leave the country."),
    ("gator", "Gator Removal Guy", "GR", "#2BD67B", "#13A15B", "24/7. Mostly 7.", "(305) 555-0177",
     "You've reached Gator Removal. If there's a gator in your pool, congratulations, it's now his pool."),
    ("lawyer", "Lawyer (Budget)", "LB", "#3DA5FF", "#7B2FF7", "Billable by the yell", "(305) 555-0199",
     "Law office. If you've been arrested, press 1. If you're about to be arrested, run, then press 1."),
    ("boat", "Boat Guy", "BG", "#19D3C5", "#3DA5FF", "Has a boat. Is the boat.", "(305) 555-0123",
     "This is Boat Guy. I'm on the boat. If you can hear this, so is the boat. Beep."),
    ("pizza", "Swamp Pizza", "SP", "#FF4D4D", "#FF8A3D", "Delivers to swamps", "(305) 555-0155",
     "Swamp Pizza! We deliver anywhere a canoe can reach. Toppings include: regret."),
    ("unknown", "Unknown Number", "?", "#6E6280", "#2E2440", "About your car's warranty", "(000) 000-0000",
     "We've been trying to reach you about your car's extended warranty. And your boat's. And your soul's."),
    ("ex", "The Ex", "EX", "#7B2FF7", "#FF3D8B", "Do NOT call. (You will.)", "(305) 555-0666",
     "The number you have dialed has blocked you. Spiritually."),
]


def phone_main():
    els = header("CONTACTS", accent="$color.green")
    y = HDR + 6
    els.append(R(10, y, 220, 26, bg="$color.surface", radius=13, children=[
        T(20, y, 200, 26, G["search"] + "  Search 8 questionable people", "t12", "$color.dim", valign="center")]))
    y += 34
    for cid, name, ini, c1, c2, sub, num, vm in CONTACTS:
        els.append(R(0, y, W, 50, action=go(f"phone/{cid}"), pressed={"bg": "$color.surface2"}, children=[
            avatar(12, y + 7, 36, ini, c1, c2),
            T(58, y + 8, 160, 18, name, "b14", "$color.fg", mode="dots"),
            T(58, y + 27, 170, 16, sub, "t12", "$color.muted", mode="dots"),
            T(216, y, 16, 50, G["chev"], "t12", "$color.dim", valign="center"),
            R(58, y + 49, 182, 1, bg="$color.line"),
        ]))
        y += 50
    return screen("main", els, y + 10)


def phone_contact(c):
    cid, name, ini, c1, c2, sub, num, vm = c
    els = header("", back=True, accent="$color.green")
    els += [avatar(80, 70, 80, ini, c1, c2, font="d22"),
            T(10, 158, 220, 24, name, "b17", "$color.fg", align="center"),
            T(10, 182, 220, 16, num, "t14", "$color.muted", align="center"),
            T(20, 202, 200, 34, sub, "t12", "$color.dim", align="center")]

    def act(x, glyph, label, color, action=None):
        return R(x, 242, 64, 64, action=action, pressed={"opa": 140}, children=[
            R(x + 12, 242, 40, 40, radius=9999, bg=color,
              children=[T(x + 12, 242, 40, 40, G[glyph], "t14", "#FFFFFF", align="center", valign="center")]),
            T(x, 286, 64, 16, label, "t11", "$color.fg", align="center")])
    els.append(act(16, "phone", "Call", "$color.green", seq([(f"phone/call_{cid}", 2200), (f"phone/vm_{cid}", 4200)])))
    els.append(act(88, "comment", "Text", "$color.blue", go("txtz/main")))
    els.append(act(160, "skull", "Block", "$color.surface2", go(f"phone/block_{cid}")))
    return screen(cid, els)


def phone_call(c, stage):
    cid, name, ini, c1, c2, sub, num, vm = c
    els = [R(0, 0, W, H, grad=("#13102A", "#05040A"), region="body")]
    els += [avatar(80, 54, 80, ini, c1, c2, font="d22"),
            T(10, 144, 220, 24, name, "b17", "$color.fg", align="center")]
    if stage == "call":
        els += [T(10, 170, 220, 18, "calling...", "t14", "$color.muted", align="center"),
                T(20, 196, 200, 34, "Ringing. It's ringing. Still ringing.", "t12", "$color.dim", align="center")]
    else:
        els += [T(10, 170, 220, 18, "Voicemail  0:0" + str(len(vm) % 9 + 1), "t14", "$color.orange", align="center"),
                T(16, 194, 208, text_h("t12", "“" + vm + "”", 208, 2), "“" + vm + "”", "t12", "$color.fg",
                  align="center", ls=2)]
    els.append(R(96, 262, 48, 48, radius=9999, bg="$color.red",
                 children=[T(96, 262, 48, 48, G["phoneoff"], "t14", "#FFFFFF", align="center", valign="center")]))
    return {"schema": 1, "id": f"{stage}_{cid}", "height": H, "status_bar": True, "top_h": SB, "bg": "#05040A",
            "elements": els}


def phone_block(c):
    cid, name, *_ = c
    msg = {"mom": "You can't block Mom. Mom blocks you. Nice try.",
           "ex": "Blocked. Again. Third time this week.",
           "dwayne": "Dwayne has been blocked. Dwayne has already found your other number."}.get(
        cid, f"{name} has been blocked. They will now text you from a cousin's phone.")
    els = header("BLOCKED", accent="$color.green")
    els += [T(0, 96, W, 40, G["skull"], "ico22", "$color.red", align="center"),
            T(20, 140, 200, text_h("b14", msg, 200, 2), msg, "b14", "$color.fg", align="center", ls=2)]
    return screen(f"block_{cid}", els)


# ------------------------------------------------------------------ Txtz (messages)

THREADS = [
    ("mom", "Mom", "MO", "#FF3D8B", "#FF8A3D", [
        ("in", "Did you eat?"), ("out", "Yes"), ("in", "What did you eat"), ("out", "Food"),
        ("in", "The alligator is back in the pool. Your father is “negotiating” with it."),
        ("in", "Also everyone at church says that game you waited for finally came out."),
        ("in", "Are you going outside ever again?"), ("out", "Define outside"),
        ("in", "I am calling you"), ("in", "Pick up"), ("in", "I can see you typing"),
    ]),
    ("dwayne", "Cousin Dwayne", "CD", "#FFD23F", "#FF8A3D", [
        ("in", "bro u up"), ("in", "got a business opportunity"), ("out", "Is it the boat again"),
        ("in", "its a DIFFERENT boat"), ("in", "this one floats"),
        ("in", "also can i borrow $40. ill pay u back like i did in 2013"),
        ("out", "You never paid me back in 2013"), ("in", "exactly. consistency"),
    ]),
    ("support", "Clout Support", "CS", "#FF3D8B", "#7B2FF7", [
        ("in", "Your account has been flagged for: posting a sunset without a filter."),
        ("in", "Please add at least 3 filters to restore your Clout Score."),
        ("out", "It was a real sunset"), ("in", "We don't do that here."),
    ]),
    ("boat", "Boat Guy", "BG", "#19D3C5", "#3DA5FF", [
        ("in", "Boat's ready."), ("out", "What boat"), ("in", "THE boat."),
        ("in", "Bring snacks and a signed waiver."), ("out", "Why do I need a waiver"), ("in", "Boat."),
    ]),
    ("unknown", "Unknown Number", "?", "#6E6280", "#2E2440", [
        ("in", "We've been trying to reach you about your boat's extended warranty."),
        ("out", "I don't have a boat"), ("in", "Dwayne said you do."), ("out", "DWAYNE"),
    ]),
]


def txtz_main():
    els = header("TXTZ", accent="$color.blue")
    y = HDR + 4
    times = ["now", "9:41 PM", "Tue", "Mon", "2013"]
    for (tid, name, ini, c1, c2, msgs), tm in zip(THREADS, times):
        last = msgs[-1][1]
        els.append(R(0, y, W, 56, action=go(f"txtz/{tid}"), pressed={"bg": "$color.surface2"}, children=[
            avatar(12, y + 9, 38, ini, c1, c2),
            T(60, y + 9, 120, 18, name, "b14", "$color.fg", mode="dots"),
            T(176, y + 10, 54, 16, tm, "t11", "$color.muted", align="right"),
            T(60, y + 29, 170, 16, last, "t12", "$color.muted", mode="dots"),
            R(60, y + 55, 180, 1, bg="$color.line"),
        ]))
        if tid in ("mom", "dwayne"):
            els.append(R(226, y + 32, 8, 8, radius=9999, bg="$color.blue"))
        y += 56
    return screen("main", els, y + 10)


def txtz_thread(t):
    tid, name, ini, c1, c2, msgs = t
    els = [R(0, 0, W, HDR, bg="$color.surface"),
           R(0, SB, 44, HDR - SB, action=BACK, pressed={"opa": 150},
             children=[T(6, SB, 32, HDR - SB, G["back"], "t14", "$color.blue", align="center", valign="center")]),
           avatar(44, SB + 6, 24, ini, c1, c2, font="b12"),
           T(74, SB, 150, HDR - SB, name, "b14", "$color.fg", valign="center", mode="dots"),
           R(0, HDR - 1, W, 1, bg="$color.line")]
    y = HDR + 10
    els.append(T(0, y, W, 14, "Today 9:41 PM", "t11", "$color.dim", align="center"))
    y += 20
    maxw = 168
    for side, text in msgs:
        lines = wrap("t14", text, maxw - 20)
        tw = max(int(pil("t14").getlength(l)) for l in lines) + 6
        bw = min(maxw, tw + 20)
        bh = len(lines) * line_h("t14") + 12
        x = 10 if side == "in" else W - 10 - bw
        bg = "$color.surface2" if side == "in" else "$color.blue"
        els.append(R(x, y, bw, bh, bg=bg, radius=14, children=[
            T(x + 10, y + 5, bw - 16, bh - 8, text, "t14", "$color.fg")]))
        y += bh + 6
    if msgs[-1][0] == "in":
        els.append(R(10, y, 46, 24, bg="$color.surface2", radius=12, children=[
            T(10, y, 46, 24, G["dots"], "t14", "$color.muted", align="center", valign="center")]))
        y += 30
    y += 40
    els.append(R(0, y - 34, W, 34, bg="$color.bg", children=[
        R(10, y - 30, 190, 26, bg="$color.surface", radius=13,
          children=[T(22, y - 30, 170, 26, "Type something you'll regret", "t12", "$color.dim", valign="center")]),
        R(206, y - 30, 26, 26, bg="$color.blue", radius=9999,
          children=[T(206, y - 30, 26, 26, G["send"], "t12", "#FFFFFF", align="center", valign="center")])]))
    return screen(tid, els, y + 4)


# ------------------------------------------------------------------ Clout (social)

POSTS = [
    ("FloridaManDaily", "FM", "#FF8A3D", "#FF3D8B", "3m", "flamingo",
     "Man arrested for teaching pelicans to shoplift. Pelicans released on their own recognizance.", "48.2K"),
    ("VictoriaInfluences", "VI", "#FF3D8B", "#7B2FF7", "12m", "video",
     "Golden hour hits different when you've been waiting since 2013. #blessed #finally #humid", "1.2M"),
    ("GymBroGreg", "GG", "#2BD67B", "#19D3C5", "41m", None,
     "Day 412 of skipping leg day. My legs filed a missing persons report. Police can't find them either.", "903"),
    ("SwampTours4U", "ST", "#19D3C5", "#3DA5FF", "1h", "swamp",
     "Tonight's tour is cancelled. The gator unionized. We support him.", "12.7K"),
    ("RealEstateRandy", "RR", "#FFD23F", "#FF8A3D", "2h", "condo",
     "JUST LISTED: 1 bed, 0 bath, partial roof, ocean view (if you stand on the partial roof). $1.9M. Won't last!", "77"),
    ("NewsBot3000", "NB", "#FF4D4D", "#B3123A", "3h", None,
     "BREAKING: Humidity hits 104%. Scientists: “that's not how percentages work.” Air: “watch me.”", "220K"),
    ("SunsetSnobs", "SS", "#FF8A3D", "#FFD23F", "5h", "sunset",
     "Rate this sunset. Wrong answers only. (It's a 10. It's always a 10. We live here.)", "5.5K"),
]


def clout_main():
    els = [R(0, 0, W, HDR, bg="$color.bg"),
           R(0, SB, 44, HDR - SB, action=BACK, pressed={"opa": 150},
             children=[T(6, SB, 32, HDR - SB, G["back"], "t14", "$color.pink", align="center", valign="center")]),
           T(44, SB - 4, 152, HDR - SB + 4, "Clout", "s26", "$color.pink", align="center", valign="center"),
           T(196, SB, 36, HDR - SB, G["bell"], "t14", "$color.fg", align="center", valign="center"),
           R(0, HDR - 1, W, 1, bg="$color.line")]
    y = HDR + 8
    # stories row
    for i, (n, ini, c1, c2) in enumerate([("You", "+", "#2E2440", "#2E2440"), ("Mom", "MO", "#FF3D8B", "#FF8A3D"),
                                          ("Dwayne", "CD", "#FFD23F", "#FF8A3D"), ("Gator", "GR", "#2BD67B", "#13A15B"),
                                          ("Randy", "RR", "#FFD23F", "#FF8A3D")]):
        x = 8 + i * 46
        els.append(R(x, y, 40, 40, radius=9999, bg="$color.pink" if i else "$color.line"))
        els.append(avatar(x + 3, y + 3, 34, ini, c1, c2, font="b12"))
        els.append(T(x - 4, y + 42, 48, 14, n, "t11", "$color.muted", align="center", mode="clip"))
    y += 64
    els.append(R(0, y - 4, W, 1, bg="$color.line"))
    for i, (h, ini, c1, c2, tm, media, cap, likes) in enumerate(POSTS):
        els.append(avatar(10, y + 4, 30, ini, c1, c2, font="b12"))
        els.append(T(48, y + 4, 150, 16, "@" + h, "b12", "$color.fg", mode="dots"))
        els.append(T(48, y + 20, 150, 14, tm + "  ·  Port Sunburn", "t11", "$color.muted"))
        els.append(T(204, y + 4, 28, 20, G["dots"], "t14", "$color.muted", align="right"))
        y += 40
        if media == "video":
            els.append({"type": "video", "id": "golden", "x": 0, "y": y, "w": 240, "h": 135, "src": "video/golden.mjpeg",
                        "autoplay": True, "loop": True})
            y += 141
        elif media:
            els.append(IMG(0, y, 240, 135, f"assets/post_{media}.bin"))
            y += 141
        ch = text_h("t12", cap, 220, 1)
        els.append(T(10, y, 220, ch, cap, "t12", "$color.fg", ls=1))
        y += ch + 6
        els.append(T(10, y, 220, 16, f"{G['heart']}  {likes}      {G['comment']}  {len(cap)}      {G['send']}", "t12", "$color.pink"))
        y += 24
        els.append(R(0, y, W, 1, bg="$color.line"))
        y += 8
    els.append(T(0, y + 4, W, 30, "You're all caught up.\nGo touch grass. (Watch for gators.)", "t11", "$color.dim", align="center"))
    return screen("main", els, y + 44)


# ------------------------------------------------------------------ Sunburn News

ARTICLES = [
    ("waited", "LOCAL", "$color.orange", "Area Man Finally Plays Game He Waited 13 Years For, Calls Humidity “Very Realistic”",
     "skyline",
     "PORT SUNBURN — After waiting since 2013, local man Derek, 34, confirmed on Thursday that the game is, in fact, out. "
     "“I've been looking at a palm tree for six hours,” he said. “It's a really good palm tree.”\n\n"
     "Derek's family reports he has not left the couch since launch, but has “done more crimes than ever, all of them fake.” "
     "His mother has started leaving sandwiches by the door like it's a zoo exhibit."),
    ("weather", "WEATHER", "$color.teal", "Forecast Calls for Hot, Then Hotter, Then a Brief Moment of Regret", None,
     "Meteorologists expect temperatures to climb all week before peaking on Friday at “why.”\n\n"
     "Residents are advised to stay hydrated, stay indoors, and stop asking the meteorologist if it's “humid enough for you.” "
     "He has asked us to tell you that it is, in fact, humid enough for him."),
    ("jetski", "CRIME", "$color.red", "Suspect Flees Police on Jet Ski, Then Lawnmower, Then “Sort Of Just Walked”", "beach",
     "A chase through three neighborhoods ended peacefully Tuesday when the suspect ran out of vehicles.\n\n"
     "“He went jet ski, ride-on mower, golf cart, then he just walked,” said one officer. “We also walked. "
     "It was honestly a nice afternoon.” The suspect has been charged with grand theft lawnmower and “vibes.”"),
    ("gator5g", "BUSINESS", "$color.green", "Startup Raises $40M to Bring Wi-Fi to the Swamp; Gators Now Expect 5G", "swamp",
     "A local startup has closed its first funding round to install Wi-Fi hotspots across the swamp.\n\n"
     "Early results are mixed: tourists can now post from the airboat, but a 12-foot gator has reportedly started "
     "leaving one-star reviews. “He types with his tail,” the CEO said. “It's actually very fast.”"),
    ("phone", "TECH", "$color.blue", "New GatorPhone VI Is Waterproof, Gator-Proof, Not Mom-Proof", None,
     "Swamp Inc. unveiled its new flagship on Monday, promising a battery that lasts “all day” (day not specified).\n\n"
     "The phone survived drops, floods and a 30-minute test inside a gator. It did not survive Mom, who answered "
     "a text from the reviewer's ex “just to be polite.”"),
    ("flamingo", "SPORTS", "$color.pink", "Pickleball League Suspended After “Incident” Involving a Flamingo", "flamingo",
     "The Port Sunburn Senior Pickleball League has paused its season after a flamingo wandered onto court 3 and refused to leave.\n\n"
     "“He stood on one leg the entire match,” said a player. “Honestly, better footwork than Gary.” "
     "Gary has declined to comment."),
]


def news_main():
    els = header("SUNBURN NEWS", color="$color.fg", accent="$color.red")
    y = HDR + 8
    els.append(CLK(10, y, 220, 14, "%A, %B %e  ·  94° and rising", "t11", "$color.muted", align="left",
                   sample="Thursday, November 19  ·  94° and rising"))
    y += 22
    lead = ARTICLES[0]
    els.append(R(0, y, W, 0 + 135 + 8 + text_h("b17", lead[3], 220, 1) + 24, action=go(f"news/{lead[0]}"),
                 pressed={"opa": 170}, children=[
        IMG(0, y, 240, 135, "assets/news_skyline.bin"),
        chip(10, y + 143, lead[1], lead[2])[0],
        T(10, y + 163, 220, text_h("b17", lead[3], 220, 1), lead[3], "b17", "$color.fg", ls=1)]))
    y += 135 + 8 + text_h("b17", lead[3], 220, 1) + 32
    for aid, cat, col, title, img, body in ARTICLES[1:]:
        th = text_h("b14", title, 206, 1)
        hh = max(56, th + 30)
        els.append(R(0, y, W, hh, action=go(f"news/{aid}"), pressed={"bg": "$color.surface2"}, children=[
            chip(10, y + 6, cat, col)[0],
            T(10, y + 25, 206, th, title, "b14", "$color.fg", ls=1),
            T(222, y, 12, hh, G["chev"], "t12", "$color.dim", valign="center"),
            R(10, y + hh - 1, 220, 1, bg="$color.line")]))
        y += hh + 6
    return screen("main", els, y + 10)


def news_article(a):
    aid, cat, col, title, img, body = a
    els = header("SUNBURN NEWS", accent="$color.red")
    y = HDR + 10
    els.append(chip(10, y, cat, col)[0])
    y += 22
    th = text_h("b17", title, 220, 1)
    els.append(T(10, y, 220, th, title, "b17", "$color.fg", ls=1))
    y += th + 4
    els.append(T(10, y, 220, 14, "By Staff Writer (Sweaty)  ·  4 min read", "t11", "$color.muted"))
    y += 22
    if img:
        els.append(IMG(0, y, 240, 135, f"assets/news_{img}.bin"))
        y += 143
    for para in body.split("\n\n"):
        ph = text_h("t14", para, 220, 3)
        els.append(T(10, y, 220, ph, para, "t14", "#FFF4ECE6", ls=3))
        y += ph + 10
    els.append(T(10, y, 220, 30, "Satire. Any resemblance to real Florida men is a coincidence, probably.", "t11", "$color.dim"))
    return screen(aid, els, y + 40)


# ------------------------------------------------------------------ VI Facts (real facts, our own words)

FACTS = [
    ("gap", "13 years in the making",
     "GTA V came out on September 17, 2013. GTA VI arrived on November 19, 2026. That 13-year wait is the longest gap "
     "between two main games in the series.", "Rockstar Games"),
    ("leonida", "Welcome to Leonida",
     "GTA VI is set in the state of Leonida, Rockstar's satirical take on Florida. Its biggest city is Vice City, "
     "the series' version of Miami.", "Rockstar Games"),
    ("vicecity", "Vice City is back",
     "Vice City first starred in GTA: Vice City (2002) and returned in Vice City Stories (2006). GTA VI brings it back, "
     "this time in the present day.", "Rockstar Games"),
    ("regions", "More than one city",
     "Besides Vice City, Leonida includes the Leonida Keys, Grassrivers, Port Gellhorn, Ambrosia and Mount Kalaga "
     "National Park.", "Rockstar Games (official GTA VI site)"),
    ("leads", "Two leads",
     "You play as Lucia Caminos and Jason Duval, a criminal couple often compared to Bonnie and Clyde.", "Rockstar Games"),
    ("lucia", "Lucia makes history",
     "Lucia is the first woman to headline a main GTA game since the series went 3D with GTA III in 2001.", "Rockstar Games"),
    ("record", "A record-breaking trailer",
     "Trailer 1 (December 2023) passed 90 million YouTube views in its first 24 hours, a Guinness World Record "
     "for a video game trailer.", "Guinness World Records"),
    ("early", "Leaked, so released early",
     "Trailer 1 leaked online the night before its planned debut, so Rockstar posted it about 15 hours early.",
     "Rockstar Games"),
    ("trailer2", "Half a billion views",
     "Trailer 2 (May 6, 2025) drew about 475 million views across platforms in 24 hours, which Rockstar called the "
     "biggest video launch of all time.", "Rockstar Games, via TechRadar and VGC"),
    ("songs", "Trailer soundtrack",
     "Trailer 1 used Tom Petty's “Love Is a Long Road”. Trailer 2 used “Hot Together” by The Pointer Sisters.",
     "Rockstar Games"),
    ("delays", "Delayed twice",
     "First planned for Fall 2025, GTA VI moved to May 26, 2026 and then to November 19, 2026, so Rockstar could "
     "finish it with the polish players expect.", "Rockstar Games"),
    ("consoles", "Consoles first",
     "GTA VI launched on PlayStation 5 and Xbox Series X|S. A PC version had not been announced at launch.",
     "Rockstar Games support"),
    ("leak", "The 2022 leak",
     "In September 2022 a hacker posted about 90 clips of early GTA VI development footage, one of the biggest "
     "leaks in gaming history.", "Rockstar Games statement, Sept 2022"),
    ("sales", "GTA V is still selling",
     "GTA V has sold more than 200 million copies, making it one of the best-selling games ever made.",
     "Take-Two Interactive"),
    ("time", "Game time",
     "In GTA V one in-game minute lasts two real seconds, so a full day takes 48 minutes. This phone's clock "
     "runs at the same speed.", "GTA V (Rockstar Games)"),
]


def facts_main():
    els = header("VI FACTS", accent="$color.purple")
    y = HDR + 8
    els.append(R(10, y, 220, 52, radius=14, grad=("#7B2FF7", "#FF3D8B", "hor"), children=[
        T(20, y + 6, 200, 18, "Real facts. No parody.", "b14", "#FFFFFF"),
        T(20, y + 26, 200, 18, "Promise. (We checked twice.)", "t12", "#FFFFFFDD")]))
    y += 62
    for i, (fid, title, body, src) in enumerate(FACTS):
        els.append(R(10, y, 220, 44, bg="$color.surface", radius=12, action=go(f"facts/{fid}"),
                     pressed={"bg": "$color.surface2"}, children=[
            R(18, y + 9, 26, 26, radius=9999, bg="$color.purple",
              children=[T(18, y + 9, 26, 26, str(i + 1), "b12", "#FFFFFF", align="center", valign="center")]),
            T(52, y, 160, 44, title, "b14", "$color.fg", valign="center", mode="dots"),
            T(212, y, 12, 44, G["chev"], "t12", "$color.dim", valign="center")]))
        y += 50
    return screen("main", els, y + 10)


def facts_detail(i):
    fid, title, body, src = FACTS[i]
    els = header(f"FACT {i + 1} / {len(FACTS)}", accent="$color.purple")
    y = HDR + 14
    els.append(R(10, y, 220, 6, radius=3, grad=("#7B2FF7", "#FF3D8B", "hor")))
    y += 16
    th = text_h("b17", title, 220, 1)
    els.append(T(10, y, 220, th, title, "b17", "$color.fg", ls=1))
    y += th + 10
    bh = text_h("t14", body, 220, 3)
    els.append(T(10, y, 220, bh, body, "t14", "#FFF4ECE6", ls=3))
    y += bh + 12
    sh = text_h("t11", "Source: " + src, 220, 1)
    els.append(T(10, y, 220, sh, "Source: " + src, "t11", "$color.muted", ls=1))
    y += sh + 14
    if i + 1 < len(FACTS):
        els.append(R(10, y, 220, 34, bg="$color.surface", radius=12, action=go(f"facts/{FACTS[i + 1][0]}"),
                     pressed={"bg": "$color.surface2"}, children=[
            T(10, y, 220, 34, "Next fact  " + G["chev"], "b12", "$color.pink", align="center", valign="center")]))
        y += 40
    return screen(fid, els, y + 10)


# ------------------------------------------------------------------ Humid (weather)


def humid_main():
    els = header("HUMID", bg="#123A5A", accent="$color.teal")
    y = HDR + 6
    els.append(R(0, HDR, W, 150, grad=("#123A5A", "#0E0B16")))
    els.append(T(0, y, W, 16, "Port Sunburn", "b14", "$color.fg", align="center"))
    els.append(T(0, y + 16, W, 46, "94°", "n40", "$color.yellow", align="center"))
    els.append(T(0, y + 62, W, 16, "Feels like: soup", "b14", "$color.fg", align="center"))
    els.append(T(0, y + 80, W, 14, "H: 97°   L: 91°   Humidity: yes", "t11", "$color.muted", align="center"))
    y += 104
    hours = [("9AM", "sun", "91°"), ("11AM", "sun", "94°"), ("1PM", "fire", "97°"),
             ("3PM", "bolt", "LOL"), ("5PM", "rain", "95°"), ("7PM", "sun", "93°")]
    els.append(R(10, y, 220, 70, bg="#FFFFFF14", radius=14))
    for i, (hh, g, t) in enumerate(hours):
        x = 14 + i * 36
        els.append(T(x, y + 6, 36, 14, hh, "t11", "$color.muted", align="center"))
        els.append(T(x, y + 22, 36, 20, G[g], "t14", "$color.yellow" if g in ("sun", "fire") else "$color.teal", align="center"))
        els.append(T(x, y + 46, 36, 16, t, "b12", "$color.fg", align="center"))
    y += 80
    days = [("Fri", "sun", "Hot"), ("Sat", "fire", "Hotter"), ("Sun", "bolt", "Hurricane-ish"),
            ("Mon", "cloud", "Pleasant (for 10 min)"), ("Tue", "rain", "Raining, still hot"), ("Wed", "sun", "Florida")]
    for d, g, txt in days:
        els.append(T(14, y, 40, 26, d, "b14", "$color.fg", valign="center"))
        els.append(T(56, y, 24, 26, G[g], "t14", "$color.yellow" if g in ("sun", "fire") else "$color.teal", valign="center"))
        els.append(T(86, y, 144, 26, txt, "t12", "$color.muted", valign="center", mode="dots"))
        els.append(R(14, y + 26, 212, 1, bg="$color.line"))
        y += 28
    y += 8
    grid = [("UV INDEX", "Yes"), ("WIND", "Leaf blower"), ("AIR", "Mostly steam"), ("SUNSET", "Every day, 10/10")]
    for i, (k, v) in enumerate(grid):
        x = 10 + (i % 2) * 112
        yy = y + (i // 2) * 52
        els.append(R(x, yy, 108, 46, bg="#FFFFFF14", radius=12, children=[
            T(x + 10, yy + 6, 90, 14, k, "b12", "$color.teal"),
            T(x + 10, yy + 22, 94, 18, v, "t12", "$color.fg", mode="dots")]))
    y += 110
    return screen("main", els, y)


# ------------------------------------------------------------------ Hailr (rides)

DESTS = [("beach", "The Beach (all of it)", "12 min"), ("dwayne", "Dwayne's “Office”", "18 min"),
         ("ac", "Anywhere with A/C", "4 min"), ("away", "Far away from Mom", "forever")]


def hailr_main():
    els = header("HAILR", accent="$color.yellow")
    els.append(IMG(0, HDR, 240, 120, "assets/map_small.bin"))
    els.append(R(112, HDR + 44, 16, 16, radius=9999, bg="$color.blue", border_w=3, border_color="#FFFFFF"))
    y = HDR + 128
    els.append(R(10, y, 220, 30, bg="$color.surface", radius=15, children=[
        T(22, y, 196, 30, G["search"] + "  Where to? (be honest)", "t12", "$color.muted", valign="center")]))
    y += 38
    for did, name, eta in DESTS:
        els.append(R(0, y, W, 40, action=go("hailr/quote"), pressed={"bg": "$color.surface2"}, children=[
            R(12, y + 8, 24, 24, radius=9999, bg="$color.surface2",
              children=[T(12, y + 8, 24, 24, G["pin"], "t12", "$color.yellow", align="center", valign="center")]),
            T(46, y, 140, 40, name, "b12", "$color.fg", valign="center", mode="dots"),
            T(184, y, 46, 40, eta, "t11", "$color.muted", align="right", valign="center"),
            R(46, y + 39, 194, 1, bg="$color.line")]))
        y += 40
    return screen("main", els, y + 10)


def hailr_quote():
    els = header("CHOOSE A RIDE", accent="$color.yellow")
    y = HDR + 10
    opts = [("Hailr Basic", "$14", "Car has 3 doors. Pick one.", "car", "$color.yellow"),
            ("Hailr Boat", "$40", "It's Dwayne. It's always Dwayne.", "water", "$color.teal"),
            ("Hailr Gator", "$9", "No questions asked. No seatbelts.", "skull", "$color.green"),
            ("Hailr Luxe", "$212", "Leather seats, sweaty leather seats.", "crown", "$color.pink")]
    for name, price, sub, g, col in opts:
        els.append(R(10, y, 220, 48, bg="$color.surface", radius=12, children=[
            R(18, y + 8, 32, 32, radius=10, bg="$color.surface2",
              children=[T(18, y + 8, 32, 32, G[g], "t14", col, align="center", valign="center")]),
            T(58, y + 7, 120, 18, name, "b14", "$color.fg"),
            T(58, y + 26, 160, 16, sub, "t11", "$color.muted", mode="dots"),
            T(180, y + 7, 42, 18, price, "b14", "$color.fg", align="right")]))
        y += 54
    els.append(R(10, y + 4, 220, 40, bg="$color.yellow", radius=20, pressed={"bg": "#E5B800"},
                 action=seq([("hailr/finding", 1800), ("hailr/found", 2600), ("hailr/arriving", 2600), ("hailr/done", 3800)]),
                 children=[T(10, y + 4, 220, 40, "Request Hailr Basic", "b14", "#0E0B16", align="center", valign="center")]))
    return screen("quote", els, y + 54)


def hailr_step(sid, title, lines, glyph, col):
    els = header(title, back=False, accent="$color.yellow")
    els.append(IMG(0, HDR, 240, 120, "assets/map_small.bin"))
    els.append(R(0, HDR + 120, W, H - HDR - 120, bg="$color.bg"))
    els.append(T(0, HDR + 130, W, 30, G[glyph], "ico22", col, align="center"))
    y = HDR + 166
    for i, l in enumerate(lines):
        f = "b14" if i == 0 else "t12"
        hh = text_h(f, l, 210, 1)
        els.append(T(15, y, 210, hh, l, f, "$color.fg" if i == 0 else "$color.muted", align="center", ls=1))
        y += hh + 4
    return {"schema": 1, "id": sid, "height": H, "status_bar": True, "top_h": HDR, "bg": "$color.bg", "elements": els}


# ------------------------------------------------------------------ Grub (food)

PLACES = [
    ("fried", "Fried Everything Shack", "If it exists, we fried it.", "4.6", "25 min", [
        ("Fried Pickles", "$6"), ("Fried Ice Cream", "$7"), ("Fried Salad (healthy)", "$9"),
        ("Fried Fried Chicken", "$12"), ("Fried Water (don't ask)", "$3")]),
    ("gas", "The Gas Station (Surprisingly Good)", "Sushi next to the motor oil.", "4.9", "15 min", [
        ("Gas Station Sushi", "$8"), ("Hot Dog (Roller Day 3)", "$2"), ("Mystery Burrito", "$5"),
        ("Energy Drink, 2 L", "$4"), ("Scratch Ticket (a dream)", "$1")]),
    ("pie", "Key Lime Pie Emergency", "24/7 pie hotline.", "5.0", "9 min", [
        ("Key Lime Pie", "$5"), ("Key Lime Pie (Large)", "$9"), ("Key Lime Pie (Personal Crisis)", "$14"),
        ("Just the Crust", "$2")]),
    ("sushi", "Sushi? In This Heat?", "Bold choice. We respect it.", "3.1", "45 min", [
        ("Spicy Tuna Roll", "$11"), ("Room Temp Roll", "$9"), ("Gator Nigiri", "$15"), ("Water (warm)", "$2")]),
]


def grub_main():
    els = header("GRUB", accent="$color.orange")
    y = HDR + 8
    els.append(R(10, y, 220, 50, radius=14, grad=("#FF8A3D", "#E5484D", "hor"), children=[
        T(20, y + 6, 200, 18, "Free delivery*", "b14", "#FFFFFF"),
        T(20, y + 26, 200, 16, "*Driver may eat one fry. It's policy.", "t11", "#FFFFFFDD")]))
    y += 60
    for pid, name, sub, rate, eta, menu in PLACES:
        els.append(R(10, y, 220, 58, bg="$color.surface", radius=12, action=go(f"grub/{pid}"),
                     pressed={"bg": "$color.surface2"}, children=[
            R(18, y + 9, 40, 40, radius=10, grad=("#FF8A3D", "#E5484D"),
              children=[T(18, y + 9, 40, 40, G["burger"], "t14", "#FFFFFF", align="center", valign="center")]),
            T(66, y + 7, 156, 18, name, "b12", "$color.fg", mode="dots"),
            T(66, y + 24, 156, 14, sub, "t11", "$color.muted", mode="dots"),
            T(66, y + 39, 156, 14, f"{G['star']} {rate}   {G['clock']} {eta}", "t11", "$color.yellow")]))
        y += 64
    return screen("main", els, y + 6)


def grub_menu(p):
    pid, name, sub, rate, eta, menu = p
    els = header("MENU", accent="$color.orange")
    y = HDR + 8
    th = text_h("b17", name, 220, 1)
    els.append(T(10, y, 220, th, name, "b17", "$color.fg", ls=1))
    y += th + 2
    els.append(T(10, y, 220, 14, f"{G['star']} {rate}  ·  {eta}  ·  {sub}", "t11", "$color.muted", mode="dots"))
    y += 22
    for item, price in menu:
        els.append(T(14, y, 150, 30, item, "t12", "$color.fg", valign="center", mode="dots"))
        els.append(T(150, y, 80, 30, price, "b12", "$color.orange", align="right", valign="center", mode="dots"))
        els.append(R(14, y + 30, 212, 1, bg="$color.line"))
        y += 32
    y += 8
    els.append(R(10, y, 220, 40, bg="$color.orange", radius=20, pressed={"bg": "#D96A20"},
                 action=seq([("grub/placed", 1800), ("grub/cooking", 2400), ("grub/driving", 2600), ("grub/delivered", 3800)]),
                 children=[T(10, y, 220, 40, "Order everything", "b14", "#0E0B16", align="center", valign="center")]))
    return screen(pid, els, y + 50)


def simple_step(app, sid, title, lines, glyph, col, accent):
    els = header(title, back=False, accent=accent)
    els.append(T(0, HDR + 40, W, 40, G[glyph], "ico22", col, align="center"))
    y = HDR + 90
    for i, l in enumerate(lines):
        f = "b17" if i == 0 else "t12"
        hh = text_h(f, l, 200, 2)
        els.append(T(20, y, 200, hh, l, f, "$color.fg" if i == 0 else "$color.muted", align="center", ls=2))
        y += hh + 8
    return {"schema": 1, "id": sid, "height": H, "status_bar": True, "top_h": HDR, "bg": "$color.bg", "elements": els}


# ------------------------------------------------------------------ Moola (bank)


def moola_main():
    els = header("MOOLA", accent="$color.green")
    y = HDR + 10
    els.append(R(10, y, 220, 118, radius=16, grad=("#2BD67B", "#19D3C5", "hor"), children=[
        T(22, y + 10, 150, 14, "MOOLA DEBIT", "b12", "#0E0B16"),
        T(160, y + 8, 60, 20, G["piggy"], "t14", "#0E0B16", align="right"),
        T(22, y + 32, 196, 44, "-$4.12", "n40", "#0E0B16"),
        T(22, y + 78, 196, 14, "Available balance (allegedly)", "t11", "#0E0B16CC"),
        T(22, y + 96, 196, 14, "••••  1337", "b12", "#0E0B16")]))
    y += 128
    for i, (lab, g) in enumerate([("Send", "send"), ("Request", "dollar"), ("Panic", "bolt")]):
        x = 10 + i * 76
        els.append(R(x, y, 68, 34, bg="$color.surface", radius=12, children=[
            T(x, y, 68, 34, G[g] + " " + lab, "b12", "$color.green", align="center", valign="center")]))
    y += 44
    els.append(T(10, y, 220, 16, "RECENT", "b12", "$color.muted"))
    y += 20
    tx = [("Paycheck", "+$612.00", "$color.green"), ("GatorGrub (Fried Water)", "-$38.50", "$color.fg"),
          ("Hailr Boat (Dwayne)", "-$40.00", "$color.fg"), ("Loan to Cousin Dwayne", "-$40.00", "$color.fg"),
          ("Overdraft fee", "-$35.00", "$color.red"), ("Fee for the overdraft fee", "-$35.00", "$color.red"),
          ("Refund: dignity", "+$0.00", "$color.green"), ("Mom: “buy food”", "+$20.00", "$color.green"),
          ("Sunscreen (SPF 100)", "-$29.99", "$color.fg"), ("Pickleball damages", "-$400.00", "$color.red")]
    for name, amt, col in tx:
        els.append(T(14, y, 150, 30, name, "t12", "$color.fg", valign="center", mode="dots"))
        els.append(T(160, y, 70, 30, amt, "b12", col, align="right", valign="center"))
        els.append(R(14, y + 30, 212, 1, bg="$color.line"))
        y += 32
    return screen("main", els, y + 10)


# ------------------------------------------------------------------ Condos (real estate)

LISTINGS = [
    ("studio", "Cozy Studio", "$1.2M", "Cozy means you can touch all four walls at once. Great for minimalists and hermits.",
     ((255, 179, 199), (255, 255, 255)), "1 bd  ·  0.5 ba  ·  190 sq ft"),
    ("water", "Waterfront Home", "$3.4M", "Water in front. Water behind. Water inside, seasonally. Bring a mop and a dream.",
     ((140, 220, 230), (255, 255, 255)), "3 bd  ·  2 ba  ·  flood zone: yes"),
    ("pent", "Penthouse", "$9.9M", "Breathtaking views. Elevator sold separately. Stairs: 41 floors, character-building.",
     ((255, 214, 120), (255, 255, 255)), "4 bd  ·  4 ba  ·  2 helipads, 0 elevators"),
    ("fixer", "Fixer-Upper", "$640K", "Needs a little work: roof, floors, walls, plumbing, exorcism. Priced to move (please).",
     ((190, 170, 150), (230, 220, 200)), "2 bd  ·  1 ba  ·  1 ghost (friendly)"),
]


def condos_main():
    els = header("CONDO KING", accent="$color.pink")
    y = HDR + 8
    els.append(T(10, y, 220, 30, "Homes in Port Sunburn under $10M. (So, four.)", "t12", "$color.muted"))
    y += 34
    for lid, name, price, desc, cols, spec in LISTINGS:
        els.append(R(10, y, 220, 160, bg="$color.surface", radius=14, clip=True, action=go(f"condos/{lid}"),
                     pressed={"opa": 170}, children=[
            IMG(10, y, 220, 104, f"assets/condo_{lid}_t.bin"),
            T(20, y + 110, 130, 20, name, "b14", "$color.fg", mode="dots"),
            T(150, y + 110, 70, 20, price, "b14", "$color.pink", align="right"),
            T(20, y + 132, 200, 16, spec, "t11", "$color.muted", mode="dots")]))
        y += 168
    return screen("main", els, y + 6)


def condos_detail(l):
    lid, name, price, desc, cols, spec = l
    els = header("LISTING", accent="$color.pink")
    els.append(IMG(0, HDR, 240, 150, f"assets/condo_{lid}.bin"))
    y = HDR + 158
    els.append(T(10, y, 150, 22, name, "b17", "$color.fg", mode="dots"))
    els.append(T(150, y, 80, 22, price, "b17", "$color.pink", align="right"))
    y += 24
    els.append(T(10, y, 220, 14, spec, "t11", "$color.muted"))
    y += 20
    dh = text_h("t14", desc, 220, 2)
    els.append(T(10, y, 220, dh, desc, "t14", "#FFF4ECE6", ls=2))
    y += dh + 10
    els.append(R(10, y, 220, 38, bg="$color.pink", radius=19, action=go("condos/offer"), pressed={"bg": "#D92A70"},
                 children=[T(10, y, 220, 38, "Make an offer", "b14", "#FFFFFF", align="center", valign="center")]))
    return screen(lid, els, y + 48)


def condos_offer():
    return simple_step("condos", "offer", "OFFER SENT", [
        "Offer received!", "Randy will get back to you after he finishes laughing.",
        "Your Moola balance: -$4.12. Randy has seen it."], "crown", "$color.yellow", "$color.pink")


# ------------------------------------------------------------------ Sweat (fitness)


def bar(x, y, w, label, val, frac, col):
    return [T(x, y, w, 16, label, "b12", "$color.fg"),
            T(x, y, w, 16, val, "t11", "$color.muted", align="right"),
            R(x, y + 19, w, 8, bg="$color.surface2", radius=4),
            R(x, y + 19, max(8, int(w * frac)), 8, bg=col, radius=4)]


def sweat_main():
    els = header("SWEAT", accent="$color.pink")
    y = HDR + 10
    els.append(R(10, y, 220, 84, bg="$color.surface", radius=14, children=[
        T(22, y + 10, 120, 14, "STEPS TODAY", "b12", "$color.pink"),
        T(22, y + 26, 120, 44, "312", "n40", "$color.fg"),
        T(110, y + 34, 112, 40, "Mostly to the fridge and back.", "t11", "$color.muted")]))
    y += 96
    for label, val, frac, col in [("Vibes", "immaculate", 0.97, "$color.pink"),
                                  ("Hydration", "iced coffee counts", 0.62, "$color.teal"),
                                  ("Sunburn", "lobster", 0.88, "$color.orange"),
                                  ("Leg day", "skipped (412)", 0.03, "$color.purple"),
                                  ("Patience", "used up in 2013-2026", 0.08, "$color.yellow")]:
        els += bar(14, y, 212, label, val, frac, col)
        y += 38
    y += 4
    els.append(R(10, y, 220, 58, bg="$color.surface", radius=14, children=[
        T(22, y + 8, 196, 16, G["run"] + "  Personal best", "b12", "$color.green"),
        T(22, y + 26, 196, 30, "Ran 0.4 km from a goose. New record!", "t12", "$color.fg")]))
    y += 68
    return screen("main", els, y)


# ------------------------------------------------------------------ Radio

STATIONS = [("104.3", "SMOOTH HUMIDITY", "Slow jams for slow traffic", "$color.pink"),
            ("88.1", "TALK BACK", "Callers yelling about lawns", "$color.orange"),
            ("99.9", "SYNTH SUNSET", "Neon, palm trees, more neon", "$color.purple"),
            ("101.1", "COUNTRY-ISH", "Songs about trucks and boats", "$color.yellow"),
            ("107.7", "NEWS: IT'S HOT", "Updates every 4 minutes. It's hot.", "$color.red"),
            ("92.5", "GATOR FM", "Mostly hissing. Big in the swamp.", "$color.green")]


def radio_main():
    els = header("RADIO", accent="$color.purple")
    y = HDR + 8
    els.append(R(10, y, 220, 96, radius=16, grad=("#7B2FF7", "#3DA5FF"), children=[
        T(22, y + 10, 196, 14, "NOW PLAYING  ·  99.9 FM", "b12", "#FFFFFFDD"),
        T(22, y + 28, 196, 20, "“Palm Trees at 4 AM”", "b14", "#FFFFFF"),
        T(22, y + 48, 196, 14, "The Humid Boys", "t12", "#FFFFFFCC"),
        R(22, y + 70, 196, 4, bg="#FFFFFF44", radius=2),
        R(22, y + 70, 120, 4, bg="#FFFFFF", radius=2),
        T(22, y + 76, 196, 14, "Audio not included. Please hum.", "t11", "#FFFFFFCC")]))
    y += 106
    for i, (f, name, sub, col) in enumerate(STATIONS):
        els.append(R(0, y, W, 44, pressed={"bg": "$color.surface2"}, action=go("radio/hum"), children=[
            T(12, y, 48, 44, f, "b14", col, valign="center"),
            T(64, y + 6, 160, 16, name, "b12", "$color.fg", mode="dots"),
            T(64, y + 23, 160, 14, sub, "t11", "$color.muted", mode="dots"),
            R(12, y + 43, 216, 1, bg="$color.line")]))
        y += 44
    return screen("main", els, y + 10)


def radio_hum():
    return simple_step("radio", "hum", "RADIO", [
        "Hum along!", "This gadget has no speaker plugged in, so you're the radio now.",
        "Tip: “doo doo doo” works for most stations."], "music", "$color.purple", "$color.purple")


# ------------------------------------------------------------------ Maps


def maps_main():
    els = header("SWAMP MAPS", accent="$color.green")
    els.append(IMG(0, HDR, 240, 264, "assets/map.bin"))

    def pin(x, y, label, col):
        w = int(pil("b12").getlength(label)) + 14
        lx = x + 8 if x + 8 + w <= W - 4 else x - 8 - w
        return [R(x - 5, y - 5, 10, 10, radius=9999, bg=col, border_w=2, border_color="#FFFFFF"),
                R(lx, y - 9, w, 18, bg="#0E0B16D9", radius=9,
                  children=[T(lx, y - 9, w, 18, label, "b12", "$color.fg", align="center", valign="center")])]
    els += pin(70, HDR + 40, "Swamp", "$color.green")
    els += pin(40, HDR + 100, "More swamp", "$color.green")
    els += pin(110, HDR + 150, "You (sadly)", "$color.blue")
    els += pin(200, HDR + 200, "Dwayne's boat", "$color.yellow")
    els += pin(24, HDR + 238, "Fried Everything", "$color.orange")
    return screen("main", els)


# ------------------------------------------------------------------ Wanted


def wanted_main():
    els = header("WANTED", accent="$color.red")
    y = HDR + 20
    els.append(T(0, y, W, 16, "YOUR CURRENT WANTED LEVEL", "b12", "$color.muted", align="center"))
    y += 24
    els += stars(40, y, 0, font="ico22", step=33)
    y += 36
    els.append(T(20, y, 200, 36, "Law-abiding citizen.\n(Allegedly.)", "b14", "$color.fg", align="center"))
    y += 44
    tips = "Tips: Don't. Just don't. If you must, at least use your turn signal."
    th = text_h("t12", tips, 200, 2)
    els.append(T(20, y, 200, th, tips, "t12", "$color.muted", align="center", ls=2))
    y += th + 14
    els.append(R(30, y, 180, 38, bg="$color.red", radius=19, action=go("wanted/report"), pressed={"bg": "#CC3030"},
                 children=[T(30, y, 180, 38, "Report a crime", "b14", "#FFFFFF", align="center", valign="center")]))
    return screen("main", els, y + 48)


def wanted_report():
    return simple_step("wanted", "report", "REPORT", [
        "Thanks, citizen!", "Your report has been filed under “Florida”.",
        "Estimated response time: after lunch."], "shield", "$color.blue", "$color.red")


# ------------------------------------------------------------------ Pics (gallery)

PICS = [("sunset", "Sunset #4,812. Still not over it."), ("beach", "Beach day. Sand everywhere. Forever."),
        ("swamp", "Pretty sure that's a log. Pretty sure."), ("flamingo", "Met a flamingo. He was cooler than me."),
        ("skyline", "Port Sunburn at night. 97° at night."), ("condo", "Our future home (in 400 years).")]


def pics_main():
    els = header("PICS", accent="$color.yellow")
    y = HDR + 8
    els.append(T(10, y, 220, 14, "Recents  ·  6 photos, 4,000 sunsets", "t11", "$color.muted"))
    y += 20
    for i, (pid, cap) in enumerate(PICS):
        x = 4 + (i % 3) * 78
        yy = y + (i // 3) * 78
        els.append(R(x, yy, 76, 76, action=go(f"pics/{pid}"), pressed={"opa": 150},
                     children=[IMG(x, yy, 76, 76, f"assets/thumb_{pid}.bin")]))
    y += 2 * 78 + 10
    els.append(R(10, y, 220, 50, bg="$color.surface", radius=12, children=[
        T(22, y + 6, 196, 16, G["camera"] + "  Storage", "b12", "$color.yellow"),
        T(22, y + 24, 196, 18, "98% memes, 2% receipts", "t12", "$color.fg")]))
    return screen("main", els, y + 60)


def pics_view(i):
    pid, cap = PICS[i]
    els = header("", accent="$color.yellow")
    els.append(IMG(0, HDR + 20, 240, 160, f"assets/full_{pid}.bin"))
    ch = text_h("t14", cap, 220, 2)
    els.append(T(10, HDR + 190, 220, ch, cap, "t14", "$color.fg", align="center", ls=2))
    els.append(T(10, HDR + 196 + ch, 220, 14, f"{G['heart']}  {G['send']}  {G['dots']}", "t14", "$color.muted", align="center"))
    if i + 1 < len(PICS):
        els.append(R(170, HDR + 236, 60, 26, bg="$color.surface", radius=13, action=go(f"pics/{PICS[i + 1][0]}"),
                     pressed={"bg": "$color.surface2"},
                     children=[T(170, HDR + 236, 60, 26, "Next " + G["chev"], "b12", "$color.yellow", align="center",
                                 valign="center")]))
    return screen(pid, els, bg="#000000")


# ------------------------------------------------------------------ Settings


def toggle(x, y, on):
    return [R(x, y, 36, 20, radius=10, bg="$color.green" if on else "$color.surface2"),
            R(x + (18 if on else 2), y + 2, 16, 16, radius=9999, bg="#FFFFFF")]


def settings_main():
    els = header("SETTINGS", accent="$color.muted")
    y = HDR + 8
    els.append(R(10, y, 220, 56, bg="$color.surface", radius=14, action=go("settings/about"), pressed={"bg": "$color.surface2"},
                 children=[avatar(20, y + 10, 36, "ME", "#FF3D8B", "#7B2FF7"),
                           T(64, y + 10, 150, 18, "Your Name Here", "b14", "$color.fg"),
                           T(64, y + 29, 150, 16, "GatorPhone VI  ·  About", "t11", "$color.muted"),
                           T(212, y, 12, 56, G["chev"], "t12", "$color.dim", valign="center")]))
    y += 66
    rows = [("plane", "Airplane mode", "Off (afraid of flying)", False),
            ("bell", "Wanted level alerts", "On, obviously", True),
            ("drop", "Humidity filter", "Not available in your region", False),
            ("moon", "Dark mode", "Always. It's 2 AM somewhere.", True),
            ("ghost", "Ghost your ex", "Enabled", True),
            ("smile", "Positive vibes only", "Battery-intensive", True),
            ("shield", "Share data with Dwayne", "He'll find it anyway", False)]
    for g, name, sub, on in rows:
        els.append(R(10, y, 220, 44, bg="$color.surface", radius=12, children=[
            T(18, y, 22, 44, G[g], "t14", "$color.muted", align="center", valign="center"),
            T(46, y + 6, 136, 16, name, "b12", "$color.fg", mode="dots"),
            T(46, y + 23, 136, 14, sub, "t11", "$color.muted", mode="dots"),
            *toggle(186, y + 12, on)]))
        y += 50
    return screen("main", els, y + 6)


def settings_about():
    els = header("ABOUT", accent="$color.muted")
    y = HDR + 10
    els.append(T(0, y, W, 34, "GatorPhone", "s26", "$color.pink", align="center"))
    y += 36
    els.append(T(0, y, W, 16, "VI Pro Max Humid Edition", "b14", "$color.fg", align="center"))
    y += 26
    specs = [("Software", "SwampOS 6.0 (“Finally”)"), ("Storage", "98% memes"),
             ("Water resistance", "Ocean? Probably not."), ("Battery", "“All day” (day not specified)"),
             ("Gator resistance", "Tested. Once."), ("Made in", "A garage in Port Sunburn")]
    for k, v in specs:
        els.append(T(14, y + 3, 212, 14, k.upper(), "t11", "$color.muted"))
        els.append(T(14, y + 17, 212, 16, v, "b12", "$color.fg", mode="dots"))
        els.append(R(14, y + 36, 212, 1, bg="$color.line"))
        y += 38
    y += 8
    legal = ("A fan-made parody gadget. Not affiliated with, endorsed by or connected to Rockstar Games or Take-Two "
             "Interactive. All jokes, names and pictures are original. Fonts: Inter, Anton, Bebas Neue, Pacifico "
             "(SIL OFL 1.1). Icons: Font Awesome Free (CC BY 4.0).")
    lh = text_h("t11", legal, 220, 1)
    els.append(T(10, y, 220, lh, legal, "t11", "$color.dim", ls=1))
    return screen("about", els, y + lh + 14)


# ------------------------------------------------------------------ manifest + build


def manifest():
    return {
        "schema": 1, "id": PACK, "unit_width": W,
        "label": "GatorPhone VI (parody)",
        "notes": "Original parody pack generated by tools/make_parody_pack.py. No game assets.",
        "apps": [{"id": a[0], "entry": "main"} for a in APPS],
        "system": {"boot": "_system/lock", "home": "_system/home", "status_bar": "_system/status_bar"},
        "theme": {"color": C},
        "fonts": {k: {"file": f"fonts/{k}.bin", "source": f"{(v[0].name if v[0] else 'FontAwesome5')}@{v[1]}"}
                  for k, v in FONTS.items()},
        # Starts on launch evening and runs at GTA V speed: 1 game minute per 2 real seconds.
        "clock": {"start": "2026-11-19T18:30:00", "rate": 30.0},
        "transitions": {
            "open_app": {"type": "cover_up", "ms": 260, "bezier": [0.2, 0.8, 0.2, 1.0]},
            "push": {"type": "slide_left", "ms": 240, "bezier": [0.3, 0.7, 0.2, 1.0]},
            "pop": {"type": "slide_right", "ms": 220, "bezier": [0.3, 0.7, 0.2, 1.0]},
            "close_app": {"type": "fade_out", "ms": 200, "bezier": [0.25, 0.1, 0.25, 1.0]},
        },
    }


def build_fonts(out: Path):
    out.mkdir(parents=True, exist_ok=True)
    npx = shutil.which("npx") or "npx"
    days = "MondayTuesdayWednesdayThursdayFridaySaturdaySunday"
    months = "JanuaryFebruaryMarchAprilMayJuneJulyAugustSeptemberOctoberNovemberDecember"
    sizes = {}
    for key, (path, size, bpp) in FONTS.items():
        chars = set(USED[key]) | {" "}
        if key in ("b14", "t11", "b12"):
            chars |= set(days + months + "0123456789,:")
        if key == "clock":
            chars = set("0123456789:")
        text = sorted(c for c in chars if ord(c) < 0xE000 and c not in "\n")
        icons = sorted(c for c in chars if 0xE000 <= ord(c) <= 0xF8FF)
        if path is not None:
            have = TTFont(str(path)).getBestCmap()
            lost = [c for c in text if ord(c) not in have]
            if lost:
                print(f"  {key}: no glyph for {lost!r}")
            text = [c for c in text if ord(c) in have]
        cmd = [npx, "-y", "lv_font_conv@1.5.3", "--size", str(size), "--bpp", str(bpp), "--format", "bin",
               "--no-compress", "-o", str(out / f"{key}.bin")]
        if path is not None:
            cmd += ["--font", str(path), "--symbols", "".join(text)]
        if icons:
            cmd += ["--font", str(FA), "--symbols", "".join(icons)]
        if path is None and not icons:
            continue
        subprocess.run(cmd, check=True, capture_output=True)
        sizes[key] = (out / f"{key}.bin").stat().st_size
    return sizes


def save_img(path: Path, img: Image.Image):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(convert.encode(img))


def thumb(img, size):
    w, h = img.size
    s = min(w, h)
    return img.crop(((w - s) // 2, (h - s) // 2, (w - s) // 2 + s, (h - s) // 2 + s)).resize(size, Image.LANCZOS)


SCENES = {"sunset": lambda w, h: scene_sunset(w, h, 7), "beach": scene_beach, "swamp": scene_swamp,
          "flamingo": scene_flamingo, "skyline": scene_skyline,
          "condo": lambda w, h: scene_condo(w, h, 9, body=(255, 200, 120))}


def build_assets(p: Path):
    sysa = p / "apps/_system/assets"
    save_img(sysa / "lock_wall.bin", scene_sunset(240, 320, 3, hz_frac=0.74, r_frac=0.24))
    for k in ("flamingo", "swamp", "condo", "sunset"):
        save_img(p / f"apps/clout/assets/post_{k}.bin", SCENES[k](240, 135))
    frames = [scene_sunset(240, 135, 11, phase=i / 24) for i in range(24)]
    video.write_container(p / "apps/clout/video/golden.mjpeg", frames, 12.0, quality=82)
    for k in ("skyline", "beach", "swamp", "flamingo"):
        save_img(p / f"apps/news/assets/news_{k}.bin", SCENES[k](240, 135))
    save_img(p / "apps/hailr/assets/map_small.bin", scene_map(240, 120, 21))
    save_img(p / "apps/maps/assets/map.bin", scene_map(240, 264, 5))
    for lid, name, price, desc, cols, spec in LISTINGS:
        big = scene_condo(240, 150, 40 + len(lid), body=cols[0], trim=cols[1])
        save_img(p / f"apps/condos/assets/condo_{lid}.bin", big)
        save_img(p / f"apps/condos/assets/condo_{lid}_t.bin", big.crop((10, 0, 230, 104)))
    for pid, cap in PICS:
        full = SCENES[pid](240, 160)
        save_img(p / f"apps/pics/assets/full_{pid}.bin", full)
        save_img(p / f"apps/pics/assets/thumb_{pid}.bin", thumb(full, (76, 76)))


def build(out: Path) -> Path:
    p = out / PACK
    if p.exists():
        shutil.rmtree(p)
    S = lambda app, name, doc: write_json(p / f"apps/{app}/screens/{name}.json", doc, compact=True)
    S("_system", "status_bar", status_bar())
    S("_system", "lock", lock())
    S("_system", "home", home())
    S("phone", "main", phone_main())
    for c in CONTACTS:
        S("phone", c[0], phone_contact(c))
        S("phone", f"call_{c[0]}", phone_call(c, "call"))
        S("phone", f"vm_{c[0]}", phone_call(c, "vm"))
        S("phone", f"block_{c[0]}", phone_block(c))
    S("txtz", "main", txtz_main())
    for t in THREADS:
        S("txtz", t[0], txtz_thread(t))
    S("clout", "main", clout_main())
    S("news", "main", news_main())
    for a in ARTICLES:
        S("news", a[0], news_article(a))
    S("facts", "main", facts_main())
    for i in range(len(FACTS)):
        S("facts", FACTS[i][0], facts_detail(i))
    S("humid", "main", humid_main())
    S("hailr", "main", hailr_main())
    S("hailr", "quote", hailr_quote())
    S("hailr", "finding", hailr_step("finding", "HAILR", ["Finding you a driver...", "Checking who's awake. And sober-ish."], "search", "$color.yellow"))
    S("hailr", "found", hailr_step("found", "DRIVER FOUND", ["Kevin  ·  4.2 " + G["star"], "Silver sedan (mostly silver). Plate: SWMP 007.", "Kevin's bio: “I talk.”"], "car", "$color.yellow"))
    S("hailr", "arriving", hailr_step("arriving", "ON THE WAY", ["Kevin is 2 min away.", "Kevin is now 5 min away.", "Kevin stopped for a smoothie."], "clock", "$color.orange"))
    S("hailr", "done", hailr_step("done", "YOU ARRIVED", ["You made it!", "Trip: $14 + $6 smoothie fee.", "Rate Kevin: " + G["star"] * 5 + " (he cried twice)"], "check", "$color.green"))
    S("grub", "main", grub_main())
    for pl in PLACES:
        S("grub", pl[0], grub_menu(pl))
    S("grub", "placed", simple_step("grub", "placed", "ORDER", ["Order placed!", "The kitchen has been notified. The kitchen sighed."], "check", "$color.green", "$color.orange"))
    S("grub", "cooking", simple_step("grub", "cooking", "ORDER", ["Cooking...", "Frying it. Frying it again. Just to be safe."], "fire", "$color.orange", "$color.orange"))
    S("grub", "driving", simple_step("grub", "driving", "ORDER", ["On the way!", "Your driver ate one fry. It's policy.", "Your driver ate two fries. That's not policy."], "car", "$color.yellow", "$color.orange"))
    S("grub", "delivered", simple_step("grub", "delivered", "ORDER", ["Delivered!", "To your neighbor. He says thanks.", "Tip suggestion: 40%, 50%, your car."], "burger", "$color.orange", "$color.orange"))
    S("moola", "main", moola_main())
    S("condos", "main", condos_main())
    for l in LISTINGS:
        S("condos", l[0], condos_detail(l))
    S("condos", "offer", condos_offer())
    S("sweat", "main", sweat_main())
    S("radio", "main", radio_main())
    S("radio", "hum", radio_hum())
    S("maps", "main", maps_main())
    S("wanted", "main", wanted_main())
    S("wanted", "report", wanted_report())
    S("pics", "main", pics_main())
    for i in range(len(PICS)):
        S("pics", PICS[i][0], pics_view(i))
    S("settings", "main", settings_main())
    S("settings", "about", settings_about())
    write_json(p / "manifest.json", manifest())
    write_json(p / "timeline.json", {"schema": 1, "events": []})
    build_assets(p)
    sizes = build_fonts(p / "fonts")
    print("fonts:", ", ".join(f"{k} {v // 1024}K" for k, v in sizes.items()), f"total {sum(sizes.values()) // 1024}K")
    return p


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=SD / "packs")
    a = ap.parse_args(argv)
    print(build(a.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
