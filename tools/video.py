"""Convert a clip to the device's MJPEG container (PLAN.md §5 step 8).

Clips are scaled to the target width (default 240 px), resampled to 12 fps and
written silent (the container has no audio track). Frames are baseline JPEGs.

Container: "MJPG" | u16 version=1 | u16 fps*100 | u16 w | u16 h | u32 frames | (u32 len + JPEG)*

  python tools/video.py in.mp4 out.mjpeg [--width 240] [--fps 12] [--crop x,y,w,h]
"""
from __future__ import annotations

import argparse
import io
import struct
from pathlib import Path
from typing import Iterable

import numpy as np
from PIL import Image

MAGIC = b"MJPG"
MAX_FRAME_BYTES = 240 * 200 * 2  # must match kMaxFrameBytes in firmware/src/ui/video.cpp


def encode_frame(img: Image.Image, quality: int = 80) -> bytes:
    buf = io.BytesIO()
    # Baseline, 4:2:0, with a JFIF header: what TJpgDec on the device decodes.
    img.convert("RGB").save(buf, "JPEG", quality=quality, optimize=False, progressive=False, subsampling=2)
    return buf.getvalue()


def write_container(path: Path, frames: Iterable[Image.Image], fps: float, quality: int = 80) -> dict:
    frames = list(frames)
    if not frames:
        raise ValueError("no frames")
    w, h = frames[0].size
    if w * h * 2 > MAX_FRAME_BYTES:
        raise ValueError(f"{w}x{h} frame needs {w*h*2} bytes; device limit is {MAX_FRAME_BYTES}")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as f:
        f.write(MAGIC + struct.pack("<HHHHI", 1, int(round(fps * 100)), w, h, len(frames)))
        for fr in frames:
            if fr.size != (w, h):
                fr = fr.resize((w, h), Image.LANCZOS)
            data = encode_frame(fr, quality)
            f.write(struct.pack("<I", len(data)) + data)
    return {"w": w, "h": h, "frames": len(frames), "fps": fps, "bytes": path.stat().st_size}


def read_container(path: Path) -> tuple[dict, list[bytes]]:
    data = Path(path).read_bytes()
    if data[:4] != MAGIC:
        raise ValueError("not an MJPG container")
    version, fps100, w, h, n = struct.unpack("<HHHHI", data[4:16])
    frames, off = [], 16
    for _ in range(n):
        (ln,) = struct.unpack("<I", data[off:off + 4])
        frames.append(data[off + 4:off + 4 + ln])
        off += 4 + ln
    return {"version": version, "fps": fps100 / 100, "w": w, "h": h, "frames": n}, frames


def read_clip(src: Path, fps: float, width: int, crop: tuple[int, int, int, int] | None = None) -> list[Image.Image]:
    import cv2  # opencv-python-headless bundles ffmpeg decoding

    cap = cv2.VideoCapture(str(src))
    if not cap.isOpened():
        raise ValueError(f"cannot open {src}")
    src_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    out, t_next, i = [], 0.0, 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        t = i / src_fps
        i += 1
        if t + 1e-9 < t_next:
            continue
        t_next += 1.0 / fps
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        if crop:
            x, y, w, h = crop
            rgb = rgb[y:y + h, x:x + w]
        img = Image.fromarray(rgb)
        hh = int(round(img.height * width / img.width))
        out.append(img.resize((width, hh), Image.LANCZOS))
    cap.release()
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src", type=Path)
    ap.add_argument("dst", type=Path)
    ap.add_argument("--width", type=int, default=240)
    ap.add_argument("--fps", type=float, default=12.0)
    ap.add_argument("--quality", type=int, default=80)
    ap.add_argument("--crop", help="x,y,w,h in source pixels (after rectify)")
    a = ap.parse_args(argv)
    crop = tuple(int(v) for v in a.crop.split(",")) if a.crop else None
    info = write_container(a.dst, read_clip(a.src, a.fps, a.width, crop), a.fps, a.quality)
    print(info)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
