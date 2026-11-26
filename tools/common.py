"""Shared paths and helpers for the ingest tools (PLAN.md §5)."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REFERENCE = ROOT / "reference"
CONTENT = ROOT / "content"
SD = ROOT / "sd"
SCHEMA = ROOT / "schema"
SIM = ROOT / "simulator" / "build" / "sim"

TARGET_W = 240
TARGET_H = 320
CANONICAL_W = TARGET_W * 4  # 960, PLAN.md §5 step 1

SNAPSHOT_RE = re.compile(r"^\d{4}-\d{2}-\d{2}_[A-Za-z0-9._-]+$")


def is_snapshot_id(s: str) -> bool:
    return bool(SNAPSHOT_RE.match(s))


def content_dir(snapshot: str) -> Path:
    return CONTENT / snapshot


def read_json(p: Path):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def write_json(p: Path, data, compact: bool = False) -> None:
    """compact=True writes minified JSON (screens: less to read and parse on the device)."""
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, separators=(",", ":"), ensure_ascii=False) if compact else json.dumps(data, indent=2, ensure_ascii=False)
    p.write_text(text + "\n", encoding="utf-8")


def scale_for(unit_width: float) -> float:
    """The one scale factor (PLAN.md §7.1)."""
    return TARGET_W / float(unit_width)


def to_px(unit: float, unit_width: float) -> int:
    return int(round(unit * scale_for(unit_width)))
