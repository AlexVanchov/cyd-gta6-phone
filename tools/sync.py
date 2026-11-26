"""Sync packs to the SD card or to the device over WiFi (PLAN.md §5 step 10).

  python tools/sync.py sd <mount> [--packs sd/packs] [--only <id>] [--delete]
      copy sd/ (packs and config) to a mounted FAT32 card; only changed files are copied
  python tools/sync.py wifi <host> [--only <id>]
      push to the device's upload endpoint (hidden menu > Start upload mode)
  python tools/sync.py serial [--port /dev/cu.usbserial-X] [--only <id>] [--rm <path>...] [--baud 460800]
      write files to the card in the device over the USB cable (PUT/CRC/RMTREE serial
      commands); unchanged files are skipped by CRC; the device reboots at the end

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


def _files(src_root: Path, only: str | None):
    for f in sorted(src_root.rglob("*")):
        if not f.is_file() or f.name.startswith(".") or f.name.endswith(".example"):
            continue
        rel = f.relative_to(src_root)
        if only and len(rel.parts) > 1 and rel.parts[0] == "packs" and rel.parts[1] != only:
            continue
        if rel.parts[0] == "config" and rel.name == "wifi.json":
            continue  # credentials are copied by hand, never synced
        yield f, "/" + rel.as_posix()


def sync_serial(port: str | None, src_root: Path = SD, only: str | None = None, rm: list[str] | None = None,
                baud: int = 460800, verbose: bool = True) -> dict:
    import time
    import zlib

    from devserial import default_port, open_port

    s = open_port(port or default_port(), reset=True)
    s.timeout = 10
    time.sleep(4)  # let it boot
    s.reset_input_buffer()

    def expect(*prefixes: str) -> str:
        while True:
            line = s.readline().decode(errors="replace").strip()
            if not line:
                raise SystemExit(f"device did not answer (waiting for {prefixes})")
            if line.startswith("ERR"):
                raise SystemExit(f"device: {line}")
            if line.startswith(prefixes):
                return line
            if verbose:
                print("   device:", line)

    def cmd(c: str, *prefixes: str) -> str:
        s.write((c + "\n").encode())
        return expect(*prefixes)

    if baud != 115200:
        cmd(f"BAUD {baud}", "OK")
        s.baudrate = baud
        time.sleep(0.2)
        s.reset_input_buffer()
    for path in rm or []:
        s.write(f"RMTREE {path}\n".encode())
        line = s.readline().decode(errors="replace").strip()
        print(f"rm {path}: {line}")
    sent = skipped = nbytes = 0
    t0 = time.time()
    for f, dst in _files(src_root, only):
        data = f.read_bytes()
        crc = zlib.crc32(data) & 0xFFFFFFFF
        size, dcrc = cmd(f"CRC {dst}", "CRC ").split()[1:3]
        if int(size) == len(data) and int(dcrc, 16) == crc:
            skipped += 1
            continue
        cmd(f"PUT {dst} {len(data)} {crc:08x}", "READY")
        chunk = 2048
        for i in range(0, len(data), chunk):
            s.write(data[i:i + chunk])
            expect("A ")
        expect("DONE")
        sent += 1
        nbytes += len(data)
        print(f"  {dst}  {len(data)} B")
    s.write(b"REBOOT\n")
    s.close()
    return {"sent": sent, "skipped": skipped, "bytes": nbytes, "seconds": round(time.time() - t0, 1)}


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
    se = sub.add_parser("serial")
    se.add_argument("--port")
    se.add_argument("--src", type=Path, default=SD)
    se.add_argument("--only")
    se.add_argument("--rm", nargs="*", help="paths on the card to delete first (e.g. /packs/<id>)")
    se.add_argument("--baud", type=int, default=460800)
    a = ap.parse_args(argv)
    if a.mode == "serial":
        res = sync_serial(a.port, a.src, a.only, a.rm, a.baud)
    else:
        res = sync_sd(a.mount, a.src, a.only, a.delete) if a.mode == "sd" else sync_wifi(a.host, a.src, a.only)
    print(res)
    return 0 if not res.get("verify_failed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
