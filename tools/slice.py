"""Slice artwork from canonical images (PLAN.md §5 step 7).

Crops a box (canonical px), downscales with Lanczos by the one scale factor
(240/960) to exact device pixels, and writes an LVGL RGB565 (or RGB565A8 when
--mask is given) .bin asset. --mask rounded:<r> or circle cuts the captured
shape out so rounded icons sit on any background without a halo.

  python tools/slice.py canonical.png x,y,w,h out.bin [--unit-width 960] [--mask rounded:40]
"""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw

from common import CANONICAL_W, TARGET_W
import convert


def device_box(x: float, y: float, w: float, h: float, unit_w: float = CANONICAL_W) -> tuple[int, int]:
    s = TARGET_W / unit_w
    return int(round((x + w) * s)) - int(round(x * s)), int(round((y + h) * s)) - int(round(y * s))


def slice_image(img: Image.Image, box: tuple[float, float, float, float], unit_w: float = CANONICAL_W,
                mask: str | None = None) -> Image.Image:
    x, y, w, h = box
    crop = img.convert("RGBA").crop((int(x), int(y), int(x + w), int(y + h)))
    if mask:
        m = Image.new("L", crop.size, 0)
        d = ImageDraw.Draw(m)
        if mask == "circle":
            d.ellipse((0, 0, crop.width - 1, crop.height - 1), fill=255)
        elif mask.startswith("rounded:"):
            d.rounded_rectangle((0, 0, crop.width - 1, crop.height - 1), radius=float(mask.split(":")[1]), fill=255)
        crop.putalpha(m)
    dw, dh = device_box(x, y, w, h, unit_w)
    return crop.resize((dw, dh), Image.LANCZOS)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("image", type=Path)
    ap.add_argument("box", help="x,y,w,h in canonical px")
    ap.add_argument("out", type=Path)
    ap.add_argument("--unit-width", type=float, default=CANONICAL_W)
    ap.add_argument("--mask")
    ap.add_argument("--png", action="store_true", help="also write a PNG preview")
    a = ap.parse_args(argv)
    box = tuple(float(v) for v in a.box.split(","))
    out = slice_image(Image.open(a.image), box, a.unit_width, a.mask)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_bytes(convert.encode(out))
    if a.png:
        out.save(a.out.with_suffix(".png"))
    print(f"{a.out} {out.width}x{out.height}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
