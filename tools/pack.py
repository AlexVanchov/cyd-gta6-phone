"""Build and validate content packs (PLAN.md §5 step 9).

  python tools/pack.py validate sd/packs/<id>            # schema + references + sizes
  python tools/pack.py build <snapshot-id>               # content/<id>/pack -> sd/packs/<id>, then validate

Validation checks every JSON file against schema/, that every referenced
screen, font, image and clip exists (through the parent chain), that image
assets match the device-pixel size of the element that shows them, and that
clips fit the device's frame-buffer limit. It ends with a size report.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

import jsonschema
from referencing import Registry, Resource

from common import CONTENT, SCHEMA, SD, TARGET_W
import convert
import video

PACKS = SD / "packs"


def _registry() -> Registry:
    reg = Registry()
    for name in ("manifest.schema.json", "screen.schema.json", "timeline.schema.json"):
        reg = reg.with_resource(name, Resource.from_contents(json.loads((SCHEMA / name).read_text())))
    return reg


def _validator(name: str):
    schema = json.loads((SCHEMA / name).read_text())
    return jsonschema.Draft202012Validator(schema, registry=_registry())


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    sizes: dict[str, int] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.errors


def chain_of(pack_dir: Path) -> list[Path]:
    """This pack and its ancestors, child first."""
    out, cur = [], pack_dir
    seen = set()
    while cur is not None:
        if cur.name in seen:
            raise ValueError(f"parent cycle at {cur.name}")
        seen.add(cur.name)
        out.append(cur)
        m = json.loads((cur / "manifest.json").read_text())
        parent = m.get("parent")
        cur = (pack_dir.parent / parent) if parent else None
    return out


def merged_manifest(chain: list[Path]) -> dict:
    def merge(dst, src):
        for k, v in src.items():
            if isinstance(v, dict) and isinstance(dst.get(k), dict):
                merge(dst[k], v)
            else:
                dst[k] = v
    m: dict = {}
    for p in reversed(chain):
        merge(m, json.loads((p / "manifest.json").read_text()))
    return m


def app_dir(chain: list[Path], app: str) -> Path | None:
    for p in chain:
        d = p / "apps" / app
        if d.is_dir():
            return d
    return None


def resolve_screen(chain: list[Path], ref: str) -> Path | None:
    app, _, screen = ref.partition("/")
    d = app_dir(chain, app)
    if d is None:
        return None
    f = d / "screens" / f"{screen}.json"
    return f if f.is_file() else None


def resolve_asset(chain: list[Path], cur_app_dir: Path, src: str) -> Path | None:
    if ":" in src.split("/")[0]:
        app, _, rel = src.partition(":")
        d = app_dir(chain, app)
        return (d / rel) if d and (d / rel).is_file() else None
    f = cur_app_dir / src
    return f if f.is_file() else None


def _walk(elements):
    for e in elements or []:
        yield e
        yield from _walk(e.get("children"))
        for item in e.get("items", []) or []:
            yield item
            yield from _walk(item.get("children"))


def _px(unit: float, scale: float) -> int:
    return int(round(unit * scale))


def validate(pack_dir: Path) -> Report:
    r = Report()
    pack_dir = Path(pack_dir)
    if not (pack_dir / "manifest.json").is_file():
        r.errors.append(f"{pack_dir}: no manifest.json")
        return r
    mv, sv, tv = _validator("manifest.schema.json"), _validator("screen.schema.json"), _validator("timeline.schema.json")

    try:
        chain = chain_of(pack_dir)
    except (ValueError, FileNotFoundError) as e:
        r.errors.append(f"parent chain: {e}")
        return r
    own = json.loads((pack_dir / "manifest.json").read_text())
    for err in mv.iter_errors(own):
        r.errors.append(f"manifest.json: {err.json_path}: {err.message}")
    if own.get("id") != pack_dir.name:
        r.errors.append(f"manifest id '{own.get('id')}' does not match folder '{pack_dir.name}'")
    m = merged_manifest(chain)
    unit_w = float(m.get("unit_width", TARGET_W))

    tl = pack_dir / "timeline.json"
    if tl.is_file():
        for err in tv.iter_errors(json.loads(tl.read_text())):
            r.errors.append(f"timeline.json: {err.json_path}: {err.message}")

    for fid, f in (m.get("fonts") or {}).items():
        if not any((p / f["file"]).is_file() for p in chain):
            r.errors.append(f"font '{fid}': {f['file']} missing")
    for key, ref in (m.get("system") or {}).items():
        if resolve_screen(chain, ref) is None:
            r.errors.append(f"system.{key}: screen {ref} missing")
    for a in m.get("apps") or []:
        entry = f"{a['id']}/{a.get('entry', 'main')}"
        if resolve_screen(chain, entry) is None:
            r.errors.append(f"app {a['id']}: entry screen {entry} missing")

    fonts = set((m.get("fonts") or {}).keys())
    tokens = m.get("theme") or {}

    def token_ok(v: str) -> bool:
        cur = tokens
        for part in v[1:].split("."):
            if not isinstance(cur, dict) or part not in cur:
                return False
            cur = cur[part]
        return isinstance(cur, str)

    for sf in sorted((pack_dir / "apps").glob("*/screens/*.json")):
        rel = sf.relative_to(pack_dir)
        try:
            s = json.loads(sf.read_text())
        except json.JSONDecodeError as e:
            r.errors.append(f"{rel}: invalid JSON: {e}")
            continue
        for err in sv.iter_errors(s):
            r.errors.append(f"{rel}: {err.json_path}: {err.message}")
        adir = sf.parent.parent
        scale = TARGET_W / float(s.get("unit_width", unit_w))
        for key in ("bg_image",):
            if key in s and resolve_asset(chain, adir, s[key]) is None:
                r.errors.append(f"{rel}: {key} {s[key]} missing")
        if isinstance(s.get("bg"), str) and s["bg"].startswith("$") and not token_ok(s["bg"]):
            r.errors.append(f"{rel}: unknown token {s['bg']}")
        for e in _walk(s.get("elements")):
            t = e.get("type")
            for ck in ("bg", "color", "border_color"):
                v = e.get(ck)
                if isinstance(v, str) and v.startswith("$") and not token_ok(v):
                    r.errors.append(f"{rel}: unknown token {v}")
            if t == "text" and e.get("font") not in fonts:
                r.errors.append(f"{rel}: font '{e.get('font')}' not in manifest")
            for k in ("src", "pressed_src", "poster"):
                if k in e and t != "station":
                    f = resolve_asset(chain, adir, e[k])
                    if f is None:
                        r.errors.append(f"{rel}: {k} {e[k]} missing")
                    elif f.suffix == ".bin" and "w" in e and "h" in e:
                        hd = convert.read_header(f)
                        want_w = _px(e.get("x", 0) + e["w"], scale) - _px(e.get("x", 0), scale)
                        want_h = _px(e.get("y", 0) + e["h"], scale) - _px(e.get("y", 0), scale)
                        if abs(hd["w"] - want_w) > 1 or abs(hd["h"] - want_h) > 1:
                            r.warnings.append(f"{rel}: {e[k]} is {hd['w']}x{hd['h']} px, element is {want_w}x{want_h} px")
                    elif f.suffix == ".mjpeg":
                        try:
                            info, _ = video.read_container(f)
                            if info["w"] * info["h"] * 2 > video.MAX_FRAME_BYTES:
                                r.errors.append(f"{rel}: clip {e[k]} too large for device memory")
                        except ValueError as ex:
                            r.errors.append(f"{rel}: clip {e[k]}: {ex}")
            act = e.get("action") or {}
            if act.get("type") == "open_screen" and resolve_screen(chain, act.get("target", "")) is None:
                r.errors.append(f"{rel}: action target {act.get('target')} missing")
            for st in act.get("steps", []) if act.get("type") == "run_sequence" else []:
                if resolve_screen(chain, st.get("screen", "")) is None:
                    r.errors.append(f"{rel}: sequence screen {st.get('screen')} missing")

    for f in pack_dir.rglob("*"):
        if f.is_file():
            top = f.relative_to(pack_dir).parts[0]
            if top == "apps":
                top = "apps/" + f.relative_to(pack_dir).parts[1]
            r.sizes[top] = r.sizes.get(top, 0) + f.stat().st_size
    return r


def print_report(pack_dir: Path, r: Report) -> None:
    print(f"== {pack_dir}")
    for e in r.errors:
        print(f"ERROR   {e}")
    for w in r.warnings:
        print(f"warning {w}")
    total = sum(r.sizes.values())
    print("size report:")
    for k in sorted(r.sizes):
        print(f"  {k:<40} {r.sizes[k] / 1024:10.1f} KiB")
    print(f"  {'TOTAL':<40} {total / 1024:10.1f} KiB")
    print("OK" if r.ok else f"FAILED ({len(r.errors)} errors)")


def build(snapshot: str, packs: Path = PACKS) -> Path:
    src = CONTENT / snapshot / "pack"
    if not (src / "manifest.json").is_file():
        raise SystemExit(f"{src} has no manifest.json; run the ingest steps first")
    dst = packs / snapshot
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    return dst


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("validate")
    v.add_argument("packs", nargs="+", type=Path)
    b = sub.add_parser("build")
    b.add_argument("snapshot")
    b.add_argument("--packs", type=Path, default=PACKS)
    a = ap.parse_args(argv)
    dirs = a.packs if a.cmd == "validate" else [build(a.snapshot, a.packs)]
    ok = True
    for d in dirs:
        r = validate(d)
        print_report(d, r)
        ok &= r.ok
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
