"""Talk to the device's serial maintenance port (115200).

  python tools/devserial.py log [--reset] [--seconds 8]      print the boot/runtime log
  python tools/devserial.py cmd "INFO" ["TAP 120 285" ...]   send commands, print replies
  python tools/devserial.py shot out.png                     read the panel's pixels back (~15 s)
"""
from __future__ import annotations

import argparse
import glob
import time
from pathlib import Path

import numpy as np
import serial
from PIL import Image


def default_port() -> str:
    ports = sorted(glob.glob("/dev/cu.usbserial-*") + glob.glob("/dev/ttyUSB*"))
    if not ports:
        raise SystemExit("no serial port found")
    return ports[0]


def open_port(port: str, reset: bool = False) -> serial.Serial:
    s = serial.Serial()
    s.port = port
    s.baudrate = 115200
    s.timeout = 0.2
    s.dtr = False
    s.rts = False
    s.open()
    if reset:
        s.rts = True
        time.sleep(0.15)
        s.rts = False
    return s


def read_for(s: serial.Serial, seconds: float) -> bytes:
    end, buf = time.time() + seconds, b""
    while time.time() < end:
        buf += s.read(4096)
    return buf


def shot(s: serial.Serial, out: Path) -> None:
    time.sleep(4)  # opening the port may reset the board; let it boot
    s.reset_input_buffer()
    s.write(b"SHOT\n")
    buf = b""
    end = time.time() + 40
    hdr = b"SHOT 240 320 RGB888\n"
    while hdr not in buf and time.time() < end:
        buf += s.read(256)
    start = buf.index(hdr) + len(hdr)
    data = buf[start:]
    need = 240 * 320 * 3
    while len(data) < need and time.time() < end:
        data += s.read(need - len(data))
    if len(data) < need:
        raise SystemExit(f"short read: {len(data)} of {need} bytes")
    rgb = np.frombuffer(data[:need], dtype=np.uint8).reshape(320, 240, 3)
    Image.fromarray(rgb).save(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", default=None)
    sub = ap.add_subparsers(dest="mode", required=True)
    lg = sub.add_parser("log")
    lg.add_argument("--reset", action="store_true")
    lg.add_argument("--seconds", type=float, default=8)
    c = sub.add_parser("cmd")
    c.add_argument("commands", nargs="+")
    c.add_argument("--wait", type=float, default=1.5)
    c.add_argument("--settle", type=float, default=4.0, help="seconds to wait after opening the port")
    sh = sub.add_parser("shot")
    sh.add_argument("out", type=Path)
    a = ap.parse_args(argv)
    s = open_port(a.port or default_port(), reset=getattr(a, "reset", False))
    if a.mode == "log":
        print(read_for(s, a.seconds).decode(errors="replace"))
    elif a.mode == "cmd":
        time.sleep(a.settle)
        s.reset_input_buffer()
        for cmd in a.commands:
            s.write(cmd.encode() + b"\n")
            print(read_for(s, a.wait).decode(errors="replace"), end="")
    else:
        shot(s, a.out)
        print(a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
