"""PNG <-> LVGL v9 binary image (.bin) conversion.

Assets are raw RGB565 (opaque) or RGB565A8 (with alpha) behind LVGL's 12-byte
image header, so the device's bin decoder can stream them from SD in strips.

Header (little endian):
  u8 magic 0x19 | u8 colour format | u16 flags | u16 w | u16 h | u16 stride | u16 reserved
"""
from __future__ import annotations

import argparse
import struct
from pathlib import Path

import numpy as np
from PIL import Image

MAGIC = 0x19
CF_RGB565 = 0x12
CF_RGB565A8 = 0x14


def rgb_to_565(rgb: np.ndarray) -> np.ndarray:
    r = rgb[..., 0].astype(np.uint16)
    g = rgb[..., 1].astype(np.uint16)
    b = rgb[..., 2].astype(np.uint16)
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)


def rgb565_to_rgb(v: np.ndarray) -> np.ndarray:
    r = (v >> 11) & 0x1F
    g = (v >> 5) & 0x3F
    b = v & 0x1F
    out = np.stack([(r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2)], axis=-1)
    return out.astype(np.uint8)


def encode(img: Image.Image, force_alpha: bool | None = None) -> bytes:
    """Encode a PIL image. Alpha is kept only when the image actually uses it."""
    rgba = np.asarray(img.convert("RGBA"))
    h, w = rgba.shape[:2]
    has_alpha = bool((rgba[..., 3] < 255).any()) if force_alpha is None else force_alpha
    px = rgb_to_565(rgba[..., :3]).astype("<u2").tobytes()
    if has_alpha:
        cf = CF_RGB565A8
        body = px + rgba[..., 3].astype(np.uint8).tobytes()
    else:
        cf = CF_RGB565
        body = px
    header = struct.pack("<BBHHHHH", MAGIC, cf, 0, w, h, w * 2, 0)
    return header + body


def decode(data: bytes) -> Image.Image:
    magic, cf, _flags, w, h, stride, _r = struct.unpack("<BBHHHHH", data[:12])
    if magic != MAGIC:
        raise ValueError("not an LVGL v9 image")
    if cf not in (CF_RGB565, CF_RGB565A8):
        raise ValueError(f"unsupported colour format 0x{cf:02x}")
    n = w * h
    px = np.frombuffer(data, dtype="<u2", count=n, offset=12).reshape(h, w)
    rgb = rgb565_to_rgb(px)
    if cf == CF_RGB565A8:
        a = np.frombuffer(data, dtype=np.uint8, count=n, offset=12 + n * 2).reshape(h, w)
        return Image.fromarray(np.dstack([rgb, a]), "RGBA")
    return Image.fromarray(rgb, "RGB")


def read_header(path: Path) -> dict:
    data = Path(path).read_bytes()[:12]
    magic, cf, flags, w, h, stride, _ = struct.unpack("<BBHHHHH", data)
    return {"magic": magic, "cf": cf, "flags": flags, "w": w, "h": h, "stride": stride}


def png_to_bin(src: Path, dst: Path) -> None:
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(encode(Image.open(src)))


def bin_to_png(src: Path, dst: Path) -> None:
    decode(Path(src).read_bytes()).save(dst)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src")
    ap.add_argument("dst")
    a = ap.parse_args(argv)
    if a.src.endswith(".bin"):
        bin_to_png(Path(a.src), Path(a.dst))
    else:
        png_to_bin(Path(a.src), Path(a.dst))
    print(f"{a.src} -> {a.dst}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
