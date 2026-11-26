"""Convert a TTF/OTF/WOFF to LVGL binary fonts (.bin) at measured sizes.

Sizes are device pixels: measured canonical size x scale (PLAN.md §7.1). Uses
lv_font_conv via npx (Node.js required).

  python tools/fonts.py --font Inter.ttf --sizes 14,17 --out content/<snap>/pack/fonts --name body
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

LV_FONT_CONV = "lv_font_conv@1.5.3"
# Printable ASCII, Latin-1, general punctuation (curly quotes, dashes, ellipsis),
# currency symbols.
DEFAULT_RANGES = "0x20-0x7E,0xA0-0xFF,0x2010-0x2027,0x2030-0x205E,0x20A0-0x20BF"


def command(font: Path, size: int, out: Path, ranges: str = DEFAULT_RANGES, bpp: int = 4) -> list[str]:
    npx = shutil.which("npx") or "npx"
    return [npx, "-y", LV_FONT_CONV, "--font", str(font), "-r", ranges, "--size", str(size),
            "--bpp", str(bpp), "--format", "bin", "--no-compress", "-o", str(out)]


def convert(font: Path, sizes: list[int], out_dir: Path, name: str, ranges: str = DEFAULT_RANGES) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    made = []
    for s in sizes:
        dst = out_dir / f"{name}_{s}.bin"
        subprocess.run(command(font, s, dst, ranges), check=True, capture_output=True)
        made.append(dst)
    return made


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--font", required=True, type=Path)
    ap.add_argument("--sizes", required=True, help="comma separated pixel sizes")
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--name", required=True)
    ap.add_argument("--ranges", default=DEFAULT_RANGES)
    a = ap.parse_args(argv)
    for p in convert(a.font, [int(x) for x in a.sizes.split(",")], a.out, a.name, a.ranges):
        print(p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
