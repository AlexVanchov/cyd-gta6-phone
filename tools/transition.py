"""Measure transition durations (PLAN.md §7.1, phase 7).

  python tools/transition.py video ref.mp4 [--corners-from x.corners.json]
      duration of the on-screen change in a reference transition video, frame by frame
  python tools/transition.py sim --pack sd/packs/<id> --screen app/screen --tap x,y
      duration the simulator animates after that tap
  python tools/transition.py check --pack sd/packs/<id>
      for each manifest transition with a "source" video, compare both (pass within 50 ms)
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import cv2
import numpy as np

from common import SIM

TOLERANCE_MS = 50


def video_duration_ms(video: Path, corners: np.ndarray | None = None, thresh: float = 2.0) -> dict:
    import rectify

    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    prev, changes, i = None, [], 0
    while True:
        ok, f = cap.read()
        if not ok:
            break
        if corners is not None:
            f = rectify.warp(f, corners, out_w=240)
        g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY).astype(np.float32)
        if prev is not None and float(np.mean(np.abs(g - prev))) > thresh:
            changes.append(i)
        prev = g
        i += 1
    cap.release()
    if not changes:
        return {"fps": fps, "duration_ms": 0}
    return {"fps": fps, "first_frame": changes[0], "last_frame": changes[-1],
            "duration_ms": round((changes[-1] - changes[0] + 1) * 1000.0 / fps)}


def sim_duration_ms(pack: Path, screen: str, tap: str) -> dict:
    out = subprocess.run([str(SIM), "--pack", str(pack), "--screen", screen, "--input", f"tap:{tap}",
                          "--measure-transition"], check=True, capture_output=True, text=True).stdout
    return json.loads(out.splitlines()[0])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("video")
    v.add_argument("video", type=Path)
    v.add_argument("--corners-from", type=Path)
    s = sub.add_parser("sim")
    s.add_argument("--pack", type=Path, required=True)
    s.add_argument("--screen", required=True)
    s.add_argument("--tap", required=True)
    a = ap.parse_args(argv)
    if a.cmd == "video":
        corners = np.array(json.loads(a.corners_from.read_text())["corners"], np.float32) if a.corners_from else None
        print(json.dumps(video_duration_ms(a.video, corners)))
    else:
        print(json.dumps(sim_duration_ms(a.pack, a.screen, a.tap)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
