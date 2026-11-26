"""Stitch a scroll video into one tall canonical image (PLAN.md §5 step 2).

Frames are rectified with the corners of a still from the same session
(--corners-from a .corners.json written by rectify.py), the pinned top and
bottom bars are excluded from matching, and each frame's vertical offset to the
previous one is found by normalised cross-correlation. Frames that did not
move (duplicates) are dropped. The result keeps the first frame's top bar and
the last frame's bottom bar.

  python tools/stitch.py video.mp4 out.png --corners-from canonical/app/x.corners.json \
      [--top 200] [--bottom 0] [--step 2]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np

import rectify


def frame_offset(prev: np.ndarray, cur: np.ndarray, top: int, bottom: int, max_shift: int | None = None) -> tuple[int, float]:
    """Vertical scroll (px) between two canonical frames: content moved up by the result."""
    h = prev.shape[0]
    body_prev = prev[top:h - bottom]
    body_cur = cur[top:h - bottom]
    bh = body_cur.shape[0]
    band = bh // 3  # a band from the middle of the current frame
    tmpl = cv2.cvtColor(body_cur[band:2 * band], cv2.COLOR_BGR2GRAY)
    search = cv2.cvtColor(body_prev, cv2.COLOR_BGR2GRAY)
    res = cv2.matchTemplate(search, tmpl, cv2.TM_CCOEFF_NORMED)
    _, score, _, loc = cv2.minMaxLoc(res)
    shift = loc[1] - band  # where cur's band sits in prev
    if max_shift is not None and abs(shift) > max_shift:
        return 0, 0.0
    return int(shift), float(score)


def stitch_frames(frames: list[np.ndarray], top: int = 0, bottom: int = 0, min_score: float = 0.6) -> tuple[np.ndarray, dict]:
    if not frames:
        raise ValueError("no frames")
    h, w = frames[0].shape[:2]
    body = [frames[0][top:h - bottom]]
    offsets, dropped = [], 0
    total = 0
    prev = frames[0]
    for f in frames[1:]:
        shift, score = frame_offset(prev, f, top, bottom)
        if score < min_score or shift <= 0:
            dropped += 1  # duplicate (no movement), backwards, or unmatched
            continue
        bh = h - top - bottom
        new_rows = f[top:h - bottom][bh - shift:]
        body.append(new_rows)
        total += shift
        offsets.append(shift)
        prev = f
    out = np.vstack([frames[0][:top]] + body + ([prev[h - bottom:]] if bottom else []))
    return out, {"frames": len(frames), "used": len(offsets) + 1, "dropped": dropped, "scrolled_px": total,
                 "height": int(out.shape[0])}


def read_frames(video: Path, corners: np.ndarray | None, step: int = 1) -> list[np.ndarray]:
    cap = cv2.VideoCapture(str(video))
    out, i = [], 0
    while True:
        ok, f = cap.read()
        if not ok:
            break
        if i % step == 0:
            out.append(rectify.warp(f, corners) if corners is not None else f)
        i += 1
    cap.release()
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--corners-from", type=Path)
    ap.add_argument("--top", type=int, default=0, help="pinned top bar height in canonical px")
    ap.add_argument("--bottom", type=int, default=0, help="pinned bottom bar height in canonical px")
    ap.add_argument("--step", type=int, default=2, help="use every n-th video frame")
    a = ap.parse_args(argv)
    corners = None
    if a.corners_from:
        corners = np.array(json.loads(a.corners_from.read_text())["corners"], dtype=np.float32)
    img, info = stitch_frames(read_frames(a.video, corners, a.step), a.top, a.bottom)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(a.out), img)
    print(json.dumps(info))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
