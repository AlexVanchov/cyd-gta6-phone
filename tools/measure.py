"""Measure theme tokens from canonical images (PLAN.md §5 step 4).

  python tools/measure.py palette img.png [--k 8]             dominant colours
  python tools/measure.py sample img.png x,y [x,y ...]        exact colours at points (5x5 median)
  python tools/measure.py box img.png x,y [--tol 12]          bounding box of the flat region at x,y
  python tools/measure.py radius img.png x0,y0,x1,y1          corner radius of a rounded box
  python tools/measure.py textheight img.png x0,y0,x1,y1      cap/x/ink height of text in a box

All values are canonical pixels; multiply by 240/960 for device pixels (the
renderer does this). Colours are written as "#RRGGBB" ready for theme tokens.
"""
from __future__ import annotations

import argparse
import json

import cv2
import numpy as np
from PIL import Image


def load(path) -> np.ndarray:
    return np.asarray(Image.open(path).convert("RGB"))


def hexc(c) -> str:
    return "#{:02X}{:02X}{:02X}".format(*(int(round(v)) for v in c[:3]))


def sample(img: np.ndarray, x: int, y: int, r: int = 2) -> str:
    patch = img[max(0, y - r):y + r + 1, max(0, x - r):x + r + 1].reshape(-1, 3)
    return hexc(np.median(patch, axis=0))


def palette(img: np.ndarray, k: int = 8) -> list[tuple[str, float]]:
    px = img.reshape(-1, 3).astype(np.float32)
    if len(px) > 200000:
        px = px[np.random.default_rng(0).choice(len(px), 200000, replace=False)]
    crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.5)
    _, labels, centers = cv2.kmeans(px, k, None, crit, 3, cv2.KMEANS_PP_CENTERS)
    counts = np.bincount(labels.ravel(), minlength=k) / len(labels)
    order = np.argsort(-counts)
    return [(hexc(centers[i]), float(counts[i])) for i in order]


def flat_box(img: np.ndarray, x: int, y: int, tol: int = 12) -> tuple[int, int, int, int]:
    """Flood-fill the region of similar colour around (x, y); return x, y, w, h."""
    h, w = img.shape[:2]
    mask = np.zeros((h + 2, w + 2), np.uint8)
    flags = 4 | cv2.FLOODFILL_MASK_ONLY | cv2.FLOODFILL_FIXED_RANGE | (255 << 8)
    cv2.floodFill(img.copy(), mask, (x, y), (0, 0, 0), (tol,) * 3, (tol,) * 3, flags)
    ys, xs = np.nonzero(mask[1:-1, 1:-1])
    return int(xs.min()), int(ys.min()), int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1)


def corner_radius(img: np.ndarray, box: tuple[int, int, int, int], tol: int = 24) -> int:
    """Radius of a rounded rectangle: how far the top edge stays background from the left corner."""
    x0, y0, x1, y1 = box
    fill = np.median(img[(y0 + y1) // 2 - 2:(y0 + y1) // 2 + 3, (x0 + x1) // 2 - 2:(x0 + x1) // 2 + 3].reshape(-1, 3), axis=0)
    row = img[y0, x0:x1].astype(int)
    inside = np.abs(row - fill).sum(axis=1) < tol
    if not inside.any():
        return 0
    return int(np.argmax(inside))


def text_height(img: np.ndarray, box: tuple[int, int, int, int], tol: int = 40) -> dict:
    x0, y0, x1, y1 = box
    crop = img[y0:y1, x0:x1].astype(int)
    bg = np.median(np.concatenate([crop[0], crop[-1]]), axis=0)
    ink = (np.abs(crop - bg).sum(axis=2) > tol)
    rows = np.nonzero(ink.any(axis=1))[0]
    cols = np.nonzero(ink.any(axis=0))[0]
    if len(rows) == 0:
        return {"ink_h": 0}
    return {"ink_top": int(y0 + rows[0]), "ink_bottom": int(y0 + rows[-1]), "ink_h": int(rows[-1] - rows[0] + 1),
            "ink_left": int(x0 + cols[0]), "ink_right": int(x0 + cols[-1])}


def _pt(s):
    return tuple(int(v) for v in s.split(","))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["palette", "sample", "box", "radius", "textheight"])
    ap.add_argument("image")
    ap.add_argument("args", nargs="*")
    ap.add_argument("--k", type=int, default=8)
    ap.add_argument("--tol", type=int, default=12)
    a = ap.parse_args(argv)
    img = load(a.image)
    if a.cmd == "palette":
        out = palette(img, a.k)
    elif a.cmd == "sample":
        out = {s: sample(img, *_pt(s)) for s in a.args}
    elif a.cmd == "box":
        out = flat_box(img, *_pt(a.args[0]), tol=a.tol)
    elif a.cmd == "radius":
        out = corner_radius(img, _pt(a.args[0]))
    else:
        out = text_height(img, _pt(a.args[0]))
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
