"""Measure the in-game clock rate from the 2-minute clock video (PLAN.md §3, §6).

Read the phone clock at two or more moments of the video (video time in
seconds, displayed in-game time) and pass them as pairs. The rate is the
least-squares slope: game seconds per real second. Minute-resolution clocks
need moments right at minute changes for a precise result.

  python tools/clockrate.py 3.2=14:05 61.7=14:35 119.9=15:04
"""
from __future__ import annotations

import argparse


def parse_pair(s: str) -> tuple[float, float]:
    t, _, clock = s.partition("=")
    parts = [int(p) for p in clock.split(":")]
    secs = parts[0] * 3600 + parts[1] * 60 + (parts[2] if len(parts) > 2 else 0)
    return float(t), float(secs)


def rate(pairs: list[tuple[float, float]]) -> float:
    if len(pairs) < 2:
        raise ValueError("need at least two readings")
    # Unwrap midnight.
    fixed, day = [], 0.0
    for i, (t, g) in enumerate(pairs):
        if i and g + day < fixed[-1][1]:
            day += 86400
        fixed.append((t, g + day))
    n = len(fixed)
    mt = sum(t for t, _ in fixed) / n
    mg = sum(g for _, g in fixed) / n
    num = sum((t - mt) * (g - mg) for t, g in fixed)
    den = sum((t - mt) ** 2 for t, _ in fixed)
    if den == 0:
        raise ValueError("readings must be at different video times")
    return num / den


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pairs", nargs="+")
    a = ap.parse_args(argv)
    r = rate([parse_pair(p) for p in a.pairs])
    print(f"rate {r:.3f} game s per real s (one game minute = {60 / r:.2f} real s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
