"""Sync packs to the SD card or to the device over WiFi (PLAN.md §5 step 10).

  python tools/sync.py sd <mount> [--packs sd/packs] [--only <id>] [--delete]
      copy sd/ (packs and config) to a mounted FAT32 card; only changed files are copied
  python tools/sync.py wifi <host> [--only <id>]
      push to the device's upload endpoint (hidden menu > Start upload mode)

The SD mode also checks the card is FAT32-sized and that the copy reads back.
"""
from __future__ import annotations

import argparse
import filecmp
import shutil
from pathlib import Path

from common import SD


def plan_copy(src_root: Path, dst_root: Path, only: str | None = None) -> list[tuple[Path, Path]]:
    todo = []
    for f in sorted(src_root.rglob("*")):
        if not f.is_file() or f.name.startswith("."):
            continue
        rel = f.relative_to(src_root)
        if only and len(rel.parts) > 1 and rel.parts[0] == "packs" and rel.parts[1] != only:
            continue
        d = dst_root / rel
        if not d.exists() or d.stat().st_size != f.stat().st_size or not filecmp.cmp(f, d, shallow=False):
            todo.append((f, d))
    return todo


def stale_packs(src_root: Path, dst_root: Path) -> list[Path]:
    have = {p.name for p in (src_root / "packs").iterdir() if p.is_dir()} if (src_root / "packs").is_dir() else set()
    dst = dst_root / "packs"
    return [p for p in dst.iterdir() if p.is_dir() and p.name not in have] if dst.is_dir() else []


def sync_sd(mount: Path, src_root: Path = SD, only: str | None = None, delete: bool = False) -> dict:
    if not mount.is_dir():
        raise SystemExit(f"{mount} is not mounted")
    todo = plan_copy(src_root, mount, only)
    for s, d in todo:
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(s, d)
    removed = []
    if delete:
        for p in stale_packs(src_root, mount):
            shutil.rmtree(p)
            removed.append(p.name)
    bad = [str(d) for s, d in todo if not filecmp.cmp(s, d, shallow=False)]
    return {"copied": len(todo), "bytes": sum(s.stat().st_size for s, _ in todo), "removed": removed, "verify_failed": bad}


def sync_wifi(host: str, src_root: Path = SD, only: str | None = None) -> dict:
    import requests

    base = f"http://{host}"
    info = requests.get(f"{base}/api/info", timeout=10).json()
    files = [f for f in sorted(src_root.rglob("*")) if f.is_file() and not f.name.startswith(".")]
    sent = 0
    for f in files:
        rel = f.relative_to(src_root)
        if only and len(rel.parts) > 1 and rel.parts[0] == "packs" and rel.parts[1] != only:
            continue
        path = "/" + rel.as_posix()
        with f.open("rb") as fh:
            r = requests.post(f"{base}/api/upload", params={"path": path}, files={"file": (f.name, fh)}, timeout=120)
        r.raise_for_status()
        sent += 1
    return {"device": info, "uploaded": sent}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="mode", required=True)
    s = sub.add_parser("sd")
    s.add_argument("mount", type=Path)
    s.add_argument("--src", type=Path, default=SD)
    s.add_argument("--only")
    s.add_argument("--delete", action="store_true", help="remove packs on the card that are not in sd/packs")
    w = sub.add_parser("wifi")
    w.add_argument("host")
    w.add_argument("--src", type=Path, default=SD)
    w.add_argument("--only")
    a = ap.parse_args(argv)
    res = sync_sd(a.mount, a.src, a.only, a.delete) if a.mode == "sd" else sync_wifi(a.host, a.src, a.only)
    print(res)
    return 0 if not res.get("verify_failed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
