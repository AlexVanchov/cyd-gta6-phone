"""Visual diff: simulator render vs reference capture (PLAN.md §5, §7.1).

Renders the screen in the headless simulator, composes the reference into the
same fit-width device layout (pinned top, body window at the same scroll
offset, pinned bottom), then scores:

  * whole screen: structural similarity (SSIM, colour), pass >= 0.95
  * every text region (label boxes reported by the simulator): its own SSIM,
    pass >= 0.95, so small text errors cannot hide in a good overall score

Writes a side-by-side image (reference | simulator | difference) and a JSON
result. Scores 0.90-0.95 are "review"; below 0.90 "fail".

  python tools/diff.py --pack sd/packs/<id> --screen app/screen --ref canonical.png \
      [--scroll 0] [--out content/<id>/report]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from skimage.metrics import structural_similarity

from common import SIM, TARGET_H, TARGET_W
import pack as packlib

PASS = 0.95
REVIEW = 0.90
# Captures are rectified from a camera view, so text regions are registered
# within +-1 device pixel before scoring (the shift used is reported).
TEXT_SHIFT = 1


def grade(score: float) -> str:
    return "pass" if score >= PASS else ("review" if score >= REVIEW else "fail")


def ssim(a: np.ndarray, b: np.ndarray) -> float:
    """Colour SSIM tolerant of tiny regions."""
    h, w = a.shape[:2]
    if h < 7 or w < 7:
        pad_h, pad_w = max(0, 7 - h), max(0, 7 - w)
        a = np.pad(a, ((0, pad_h), (0, pad_w), (0, 0)), mode="edge")
        b = np.pad(b, ((0, pad_h), (0, pad_w), (0, 0)), mode="edge")
    if np.array_equal(a, b):
        return 1.0
    return float(structural_similarity(a, b, channel_axis=2, data_range=255))


def quantize_565(img: Image.Image) -> Image.Image:
    """The device shows 16-bit colour (DEVIATIONS.md); compare like with like."""
    a = np.asarray(img.convert("RGB")).astype(np.uint16)
    r, g, b = a[..., 0] >> 3, a[..., 1] >> 2, a[..., 2] >> 3
    out = np.dstack([(r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2)]).astype(np.uint8)
    return Image.fromarray(out)


def region_ssim(a: np.ndarray, b: np.ndarray, x: int, y: int, w: int, h: int, shift: int = TEXT_SHIFT):
    """Best SSIM of b's region against a's region shifted by up to `shift` px."""
    bb = b[y:y + h, x:x + w]
    best = (-1.0, 0, 0)
    for dy in range(-shift, shift + 1):
        for dx in range(-shift, shift + 1):
            ys, xs = y + dy, x + dx
            if ys < 0 or xs < 0 or ys + h > a.shape[0] or xs + w > a.shape[1]:
                continue
            sc = ssim(a[ys:ys + h, xs:xs + w], bb)
            if sc > best[0]:
                best = (sc, dx, dy)
    return best


def screen_layout(pack_dir: Path, screen: str) -> dict:
    chain = packlib.chain_of(Path(pack_dir))
    m = packlib.merged_manifest(chain)
    s = json.loads(packlib.resolve_screen(chain, screen).read_text())
    unit_w = float(s.get("unit_width", m.get("unit_width", TARGET_W)))
    top_h = float(s.get("top_h", 0))
    if s.get("status_bar") and m.get("system", {}).get("status_bar"):
        sb = json.loads(packlib.resolve_screen(chain, m["system"]["status_bar"]).read_text())
        top_h = max(top_h, float(sb.get("height", 0)))
    return {"unit_w": unit_w, "height": float(s.get("height", unit_w * TARGET_H / TARGET_W)),
            "top_h": top_h, "bottom_h": float(s.get("bottom_h", 0))}


def compose_reference(ref: Image.Image, layout: dict, scroll: int = 0) -> Image.Image:
    """Scale a canonical capture to 240 wide and lay it out like the device does."""
    s = TARGET_W / layout["unit_w"]
    px = lambda u: int(round(u * s))  # noqa: E731
    full = ref.convert("RGB").resize((TARGET_W, max(1, px(ref.height * layout["unit_w"] / ref.width))), Image.LANCZOS)
    top, bottom = px(layout["top_h"]), px(layout["bottom_h"])
    out = Image.new("RGB", (TARGET_W, TARGET_H), (0, 0, 0))
    body_h = TARGET_H - top - bottom
    body_src_top = top + scroll
    out.paste(full.crop((0, body_src_top, TARGET_W, body_src_top + body_h)), (0, top))
    if top:
        out.paste(full.crop((0, 0, TARGET_W, top)), (0, 0))
    if bottom:
        out.paste(full.crop((0, full.height - bottom, TARGET_W, full.height)), (0, TARGET_H - bottom))
    return quantize_565(out)


def render(pack_dir: Path, screen: str, out_png: Path, regions_json: Path, scroll: int = 0,
           extra: list[str] | None = None) -> None:
    cmd = [str(SIM), "--pack", str(pack_dir), "--screen", screen, "--out", str(out_png),
           "--regions", str(regions_json)]
    if scroll:
        cmd += ["--scroll", str(scroll)]
    cmd += extra or []
    subprocess.run(cmd, check=True, capture_output=True, text=True)


def side_by_side(ref: Image.Image, sim: Image.Image, regions: list[dict], results: list[dict]) -> Image.Image:
    a, b = np.asarray(ref).astype(int), np.asarray(sim).astype(int)
    d = np.clip(np.abs(a - b).sum(axis=2) * 3, 0, 255).astype(np.uint8)
    heat = Image.fromarray(np.dstack([d, np.zeros_like(d), np.zeros_like(d)]))
    out = Image.new("RGB", (TARGET_W * 3 + 20, TARGET_H), (255, 255, 255))
    out.paste(ref, (0, 0))
    out.paste(sim, (TARGET_W + 10, 0))
    out.paste(heat, (TARGET_W * 2 + 20, 0))
    dr = ImageDraw.Draw(out)
    for r, res in zip(regions, results):
        col = {"pass": (0, 200, 0), "review": (255, 170, 0), "fail": (255, 0, 0)}[res["grade"]]
        x, y = r["x"] + TARGET_W + 10, r["y"]
        dr.rectangle((x, y, x + r["w"] - 1, y + r["h"] - 1), outline=col)
    return out


def compare(ref_img: Image.Image, sim_img: Image.Image, regions: list[dict]) -> dict:
    a, b = np.asarray(ref_img.convert("RGB")), np.asarray(sim_img.convert("RGB"))
    whole = ssim(a, b)
    texts = []
    for r in regions:
        x, y, w, h = r["x"], r["y"], r["w"], r["h"]
        if w <= 0 or h <= 0:
            continue
        sc, dx, dy = region_ssim(a, b, x, y, w, h)
        texts.append({"text": r["text"], "box": [x, y, w, h], "ssim": round(sc, 4), "shift": [dx, dy],
                      "grade": grade(sc)})
    worst = min([whole] + [t["ssim"] for t in texts])
    return {"ssim": round(whole, 4), "grade": grade(whole), "texts": texts,
            "worst": round(worst, 4), "result": grade(worst)}


def run(pack_dir: Path, screen: str, ref_path: Path, out_dir: Path, scroll: int = 0) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    tag = screen.replace("/", "__") + (f"@{scroll}" if scroll else "")
    with tempfile.TemporaryDirectory() as td:
        sim_png, reg = Path(td) / "sim.png", Path(td) / "regions.json"
        render(pack_dir, screen, sim_png, reg, scroll)
        sim_img = Image.open(sim_png).convert("RGB")
        regions = json.loads(reg.read_text())
    ref = compose_reference(Image.open(ref_path), screen_layout(pack_dir, screen), scroll)
    res = compare(ref, sim_img, regions)
    res.update({"screen": screen, "scroll": scroll, "reference": str(ref_path)})
    sbs = out_dir / f"{tag}.png"
    side_by_side(ref, sim_img, [{"x": t["box"][0], "y": t["box"][1], "w": t["box"][2], "h": t["box"][3]}
                                for t in res["texts"]], res["texts"]).save(sbs)
    res["side_by_side"] = str(sbs)
    (out_dir / f"{tag}.json").write_text(json.dumps(res, indent=2, ensure_ascii=False))
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pack", required=True, type=Path)
    ap.add_argument("--screen", required=True)
    ap.add_argument("--ref", required=True, type=Path, help="canonical reference image")
    ap.add_argument("--scroll", type=int, default=0)
    ap.add_argument("--out", type=Path, default=Path("diff-report"))
    a = ap.parse_args(argv)
    res = run(a.pack, a.screen, a.ref, a.out, a.scroll)
    print(f"{a.screen}: ssim {res['ssim']} ({res['grade']}), worst text "
          f"{min([t['ssim'] for t in res['texts']] or [1.0])}, result {res['result']}  -> {res['side_by_side']}")
    for t in res["texts"]:
        if t["grade"] != "pass":
            print(f"   text {t['text']!r} {t['box']}: {t['ssim']} {t['grade']}")
    return 0 if res["result"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
