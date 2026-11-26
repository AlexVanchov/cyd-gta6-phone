"""Rectify captures: find the phone screen's four corners, correct perspective,
and save a flat canonical image 960 px wide (PLAN.md §5 step 1).

The screen is found as the largest convex quadrilateral whose contents differ
from the surrounding game scene (edges + contour approximation). If detection
is unreliable for a capture, pass --corners "x1,y1;x2,y2;x3,y3;x4,y4"
(top-left, top-right, bottom-right, bottom-left). The detected corners are
saved next to the output (.corners.json) so videos can reuse them.

  python tools/rectify.py <snapshot-id> [--app <app>]          # every PNG in reference/<id>
  python tools/rectify.py --image in.png --out out.png [--corners ...]

Writes content/<id>/canonical/<app>/<name>.png and content/<id>/measurements.json
(measured aspect ratio, needed for DEVIATIONS.md).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np

from common import CANONICAL_W, CONTENT, REFERENCE, write_json


def order_corners(pts: np.ndarray) -> np.ndarray:
    """Return corners as TL, TR, BR, BL."""
    pts = np.asarray(pts, dtype=np.float32).reshape(4, 2)
    s = pts.sum(axis=1)
    d = np.diff(pts, axis=1).ravel()
    return np.array([pts[np.argmin(s)], pts[np.argmin(d)], pts[np.argmax(s)], pts[np.argmax(d)]], dtype=np.float32)


def find_screen(img: np.ndarray, min_area_frac: float = 0.03) -> np.ndarray | None:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    h, w = gray.shape
    best, best_area = None, 0.0
    for lo, hi in ((30, 100), (50, 150), (10, 60)):
        edges = cv2.Canny(gray, lo, hi)
        edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=1)
        contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        for c in contours:
            area = cv2.contourArea(c)
            if area < min_area_frac * w * h or area <= best_area:
                continue
            peri = cv2.arcLength(c, True)
            approx = cv2.approxPolyDP(c, 0.02 * peri, True)
            if len(approx) == 4 and cv2.isContourConvex(approx):
                best, best_area = approx.reshape(4, 2), area
    return None if best is None else order_corners(best)


def measured_aspect(corners: np.ndarray) -> float:
    tl, tr, br, bl = corners
    width = (np.linalg.norm(tr - tl) + np.linalg.norm(br - bl)) / 2
    height = (np.linalg.norm(bl - tl) + np.linalg.norm(br - tr)) / 2
    return float(height / width)


def warp(img: np.ndarray, corners: np.ndarray, out_w: int = CANONICAL_W, aspect: float | None = None) -> np.ndarray:
    aspect = aspect or measured_aspect(corners)
    out_h = int(round(out_w * aspect))
    dst = np.array([[0, 0], [out_w - 1, 0], [out_w - 1, out_h - 1], [0, out_h - 1]], dtype=np.float32)
    m = cv2.getPerspectiveTransform(corners.astype(np.float32), dst)
    return cv2.warpPerspective(img, m, (out_w, out_h), flags=cv2.INTER_LANCZOS4)


def parse_corners(s: str) -> np.ndarray:
    return order_corners(np.array([[float(v) for v in p.split(",")] for p in s.split(";")]))


def rectify_file(src: Path, dst: Path, corners: np.ndarray | None = None, aspect: float | None = None) -> dict:
    img = cv2.imread(str(src), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError(f"cannot read {src}")
    if corners is None:
        corners = find_screen(img)
    if corners is None:
        raise ValueError(f"{src}: phone screen not found; pass --corners")
    out = warp(img, corners, aspect=aspect)
    dst.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(dst), out)
    info = {"source": str(src), "corners": corners.tolist(), "aspect": measured_aspect(corners),
            "size": [out.shape[1], out.shape[0]]}
    dst.with_suffix(".corners.json").write_text(json.dumps(info, indent=2))
    return info


def rectify_snapshot(snapshot: str, app: str | None = None) -> list[dict]:
    ref = REFERENCE / snapshot
    out = CONTENT / snapshot / "canonical"
    results, failures = [], []
    for png in sorted(ref.glob("*/screens/*.png")) + sorted(ref.glob("_system/*.png")):
        a = png.parent.parent.name if png.parent.name == "screens" else png.parent.name
        if app and a != app:
            continue
        try:
            results.append(rectify_file(png, out / a / png.name))
        except ValueError as e:
            failures.append(str(e))
    aspects = [r["aspect"] for r in results]
    meas = {"screens": len(results), "failures": failures,
            "aspect_median": float(np.median(aspects)) if aspects else None,
            "aspect_min": min(aspects) if aspects else None, "aspect_max": max(aspects) if aspects else None}
    write_json(CONTENT / snapshot / "measurements.json", meas)
    return results


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("snapshot", nargs="?")
    ap.add_argument("--app")
    ap.add_argument("--image", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--corners")
    ap.add_argument("--aspect", type=float, help="force the output aspect (height/width)")
    a = ap.parse_args(argv)
    if a.image:
        info = rectify_file(a.image, a.out, parse_corners(a.corners) if a.corners else None, a.aspect)
        print(json.dumps(info))
    elif a.snapshot:
        res = rectify_snapshot(a.snapshot, a.app)
        print(f"rectified {len(res)} images -> {CONTENT / a.snapshot / 'canonical'}")
    else:
        ap.error("snapshot or --image required")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
