"""Independent reference renderer for SYNTHETIC packs (phase 1 verification).

Draws a screen JSON with Pillow at canonical size (unit coordinates, e.g. 960
px wide), the way a capture would look. tools/diff.py can then scale it down
and compare it with the simulator, which checks the whole chain (layout, scale,
rounding, fonts, images) against a second implementation.

This is never used for game screens: those are compared with the owner's
captures. It needs each font's "source" (file@device_px) in the manifest.

  python tools/refrender.py --pack sd/packs/<id> --screen app/screen --out ref.png
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from common import ROOT, TARGET_H, TARGET_W
import convert
import pack as packlib
import video

FONT_DIRS = [ROOT / "firmware/.pio/libdeps/ili9341/lvgl/scripts/built_in_font", ROOT / "tools/fonts"]


def _color(v, tokens):
    if not isinstance(v, str):
        return None
    while v.startswith("$"):
        cur = tokens
        for p in v[1:].split("."):
            cur = cur[p]
        v = cur
    v = v.lstrip("#")
    rgb = tuple(int(v[i:i + 2], 16) for i in (0, 2, 4))
    a = int(v[6:8], 16) if len(v) == 8 else 255
    return rgb + (a,)


class Renderer:
    def __init__(self, pack_dir: Path):
        self.chain = packlib.chain_of(Path(pack_dir))
        self.m = packlib.merged_manifest(self.chain)
        self.tokens = self.m.get("theme", {})
        self.unit_w = float(self.m.get("unit_width", TARGET_W))
        self.k = self.unit_w / TARGET_W  # canonical px per device px
        self._fonts = {}

    def font(self, fid):
        if fid not in self._fonts:
            src = self.m["fonts"][fid]["source"]
            name, _, size = src.partition("@")
            path = next((d / name for d in FONT_DIRS if (d / name).is_file()), None)
            if path is None:
                raise FileNotFoundError(name)
            self._fonts[fid] = ImageFont.truetype(str(path), int(round(int(size) * self.k)))
        return self._fonts[fid]

    # ---- primitives
    def rect(self, img, e, box):
        x0, y0, x1, y1 = box
        if x1 <= x0 or y1 <= y0:
            return
        r = e.get("radius", 0)
        if r >= 9999:
            r = min(x1 - x0, y1 - y0) / 2
        r = min(r, (x1 - x0) / 2, (y1 - y0) / 2)
        layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        mask = Image.new("L", img.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle((x0, y0, x1 - 1, y1 - 1), radius=r, fill=255)
        grad = e.get("bg_grad")
        if grad:
            c0, c1 = (_color(c, self.tokens) for c in grad["colors"])
            g = Image.new("RGBA", (int(x1 - x0), int(y1 - y0)))
            gd = ImageDraw.Draw(g)
            n = g.height if grad.get("dir", "ver") == "ver" else g.width
            for i in range(n):
                t = i / max(n - 1, 1)
                c = tuple(int(round(c0[j] + (c1[j] - c0[j]) * t)) for j in range(4))
                if grad.get("dir", "ver") == "ver":
                    gd.line((0, i, g.width, i), fill=c)
                else:
                    gd.line((i, 0, i, g.height), fill=c)
            layer.paste(g, (int(x0), int(y0)))
        elif e.get("bg"):
            ImageDraw.Draw(layer).rectangle((x0, y0, x1, y1), fill=_color(e["bg"], self.tokens))
        bw = e.get("border_w", 0)
        if bw and e.get("border_color"):
            inner = Image.new("L", img.size, 0)
            ImageDraw.Draw(inner).rounded_rectangle((x0 + bw, y0 + bw, x1 - 1 - bw, y1 - 1 - bw),
                                                    radius=max(r - bw, 0), fill=255)
            ring = Image.eval(Image.composite(Image.new("L", img.size, 0), mask, inner), lambda v: v)
            border = Image.new("RGBA", img.size, _color(e["border_color"], self.tokens))
            layer = Image.composite(border, layer, ring)
        img.alpha_composite(Image.composite(layer, Image.new("RGBA", img.size, (0, 0, 0, 0)), mask))

    def text(self, img, e, box):
        x0, y0, x1, y1 = box
        f = self.font(e["font"])
        asc, desc = f.getmetrics()
        lh = asc + desc + e.get("line_space", 0)
        w = x1 - x0
        words = e.get("text", "").split(" ")
        lines, cur = [], ""
        for wd in words:
            cand = wd if not cur else cur + " " + wd
            if f.getlength(cand) <= w or not cur:
                cur = cand
            else:
                lines.append(cur)
                cur = wd
        lines.append(cur)
        total = lh * len(lines)
        va = e.get("valign", "top")
        y = y0 if va == "top" else (y0 + (y1 - y0 - total) / 2 if va == "center" else y1 - total)
        d = ImageDraw.Draw(img)
        col = _color(e.get("color", "#000000"), self.tokens)
        for ln in lines:
            tw = f.getlength(ln)
            al = e.get("align", "left")
            x = x0 if al == "left" else (x0 + (w - tw) / 2 if al == "center" else x1 - tw)
            d.text((x, y + asc), ln, font=f, fill=col, anchor="ls")
            y += lh

    def image(self, img, e, box, app_dir):
        f = packlib.resolve_asset(self.chain, app_dir, e["src"])
        if f.suffix == ".mjpeg":
            import io
            _, frames = video.read_container(f)
            src = Image.open(io.BytesIO(frames[0])).convert("RGBA")
        else:
            src = convert.decode(f.read_bytes()).convert("RGBA")
        src = src.resize((int(round(src.width * self.k)), int(round(src.height * self.k))), Image.LANCZOS)
        img.alpha_composite(src, (int(box[0]), int(box[1])))

    def element(self, img, e, app_dir, clip=None):
        x, y = e.get("x", 0), e.get("y", 0)
        box = (x, y, x + e.get("w", 0), y + e.get("h", 0))
        t = e.get("type")
        target = img
        if clip is not None:
            target = Image.new("RGBA", img.size, (0, 0, 0, 0))
        if t in ("rect", "button", "station", "scroll", "list"):
            self.rect(target, e, box)
            for c in e.get("children", []) or []:
                self.element(target, c, app_dir, clip=box if t == "scroll" else None)
            for it in e.get("items", []) or []:
                ib = (it.get("x", 0), it.get("y", 0), it.get("x", 0) + it.get("w", 0), it.get("y", 0) + it.get("h", 0))
                self.rect(target, it, ib)
                for c in it.get("children", []) or []:
                    self.element(target, c, app_dir, clip=ib)
        elif t == "text":
            self.text(target, e, box)
        elif t in ("image", "video"):
            self.image(target, e, box, app_dir)
        if clip is not None:
            mask = Image.new("L", img.size, 0)
            ImageDraw.Draw(mask).rectangle((clip[0], clip[1], clip[2] - 1, clip[3] - 1), fill=255)
            img.alpha_composite(Image.composite(target, Image.new("RGBA", img.size, (0, 0, 0, 0)), mask))

    def screen(self, ref: str) -> Image.Image:
        sf = packlib.resolve_screen(self.chain, ref)
        s = json.loads(sf.read_text())
        app_dir = sf.parent.parent
        unit_w = s.get("unit_width", self.unit_w)
        h = s.get("height", unit_w * TARGET_H / TARGET_W)
        img = Image.new("RGBA", (int(unit_w), int(h)), (0, 0, 0, 255))
        if s.get("bg"):
            img.paste(_color(s["bg"], self.tokens), (0, 0, img.width, img.height))
        for e in s.get("elements", []):
            self.element(img, e, app_dir)
        if s.get("status_bar") and self.m.get("system", {}).get("status_bar"):
            sbf = packlib.resolve_screen(self.chain, self.m["system"]["status_bar"])
            for e in json.loads(sbf.read_text()).get("elements", []):
                self.element(img, e, sbf.parent.parent)
        return img.convert("RGB")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pack", required=True, type=Path)
    ap.add_argument("--screen", required=True)
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args(argv)
    Renderer(a.pack).screen(a.screen).save(a.out)
    print(a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
