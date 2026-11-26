"""End-to-end: synthetic packs, schema validation, simulator, diff, inheritance."""
import json
import shutil
import subprocess

import pytest
from PIL import Image

import diff
import make_test_pack
import pack
import refrender
from common import SIM

needs_sim = pytest.mark.skipif(not SIM.exists(), reason="simulator not built (make -C simulator)")


@pytest.fixture(scope="module")
def packs(tmp_path_factory):
    out = tmp_path_factory.mktemp("sd") / "packs"
    make_test_pack.build(out)
    return out


def test_validate_ok(packs):
    for p in (make_test_pack.A, make_test_pack.B):
        r = pack.validate(packs / p)
        assert r.ok, r.errors


def test_validate_catches_errors(packs, tmp_path):
    bad = tmp_path / "packs" / make_test_pack.A
    shutil.copytree(packs / make_test_pack.A, bad)
    s = json.loads((bad / "apps/alpha/screens/main.json").read_text())
    s["elements"].append({"type": "image", "src": "assets/missing.bin", "x": 0, "y": 0})
    s["elements"].append({"type": "text", "text": "x", "font": "nofont"})
    s["elements"].append({"type": "rect", "action": {"type": "open_screen", "target": "nope/main"}})
    (bad / "apps/alpha/screens/main.json").write_text(json.dumps(s))
    errs = "\n".join(pack.validate(bad).errors)
    assert "missing.bin" in errs and "nofont" in errs and "nope/main" in errs


def test_inheritance_chain(packs):
    chain = pack.chain_of(packs / make_test_pack.B)
    assert [c.name for c in chain] == [make_test_pack.B, make_test_pack.A]
    assert pack.app_dir(chain, "alpha").parent.parent.name == make_test_pack.A
    assert pack.app_dir(chain, "beta").parent.parent.name == make_test_pack.B
    m = pack.merged_manifest(chain)
    assert m["theme"]["color"]["accent"] == "#E5484D" and m["theme"]["color"]["bg"] == "#101418"


def sim(*args):
    return subprocess.run([str(SIM), *map(str, args)], check=True, capture_output=True, text=True).stdout


@needs_sim
def test_sim_renders_and_navigates(packs, tmp_path):
    a = packs / make_test_pack.A
    out = sim("--pack", a, "--input", "tap:120,285;wait:500;tap:45,60;wait:500;tap:120,90;wait:600",
              "--out", tmp_path / "x.png")
    assert "screen=alpha/detail depth=4" in out
    out = sim("--pack", a, "--screen", "alpha/main", "--input", "swipe:3,150,150,150,150;wait:600",
              "--out", tmp_path / "y.png")
    assert "screen=_system/lock" in out or "screen=_system/home" in out
    out = sim("--pack", a, "--screen", "gamma/main", "--input", "tap:120,140;wait:2000", "--out", tmp_path / "z.png")
    assert "screen=gamma/main depth=2" in out  # run_sequence returned


@needs_sim
def test_sim_snapshot_switch_and_inheritance(packs, tmp_path):
    out = sim("--pack", packs / make_test_pack.A, "--switch", make_test_pack.B, "--screen", "alpha/main",
              "--out", tmp_path / "b.png")
    assert f"snapshot={make_test_pack.B}" in out and "screen=alpha/main" in out
    # accent token overridden in B: the back arrow turns red
    img = Image.open(tmp_path / "b.png").convert("RGB")
    reds = sum(1 for x in range(8, 30) for y in range(30, 55) if img.getpixel((x, y))[0] > 180 and img.getpixel((x, y))[2] < 120)
    assert reds > 5


@needs_sim
def test_sim_video_advances(packs, tmp_path):
    a = packs / make_test_pack.A
    sim("--pack", a, "--screen", "beta/main", "--out", tmp_path / "v0.png")
    sim("--pack", a, "--screen", "beta/main", "--advance", "170", "--out", tmp_path / "v1.png")
    assert Image.open(tmp_path / "v0.png").tobytes() != Image.open(tmp_path / "v1.png").tobytes()


@needs_sim
def test_transition_duration_matches_manifest(packs):
    out = sim("--pack", packs / make_test_pack.A, "--screen", "alpha/main", "--input", "tap:120,90",
              "--measure-transition", "--out", "/dev/null")
    dur = json.loads(out.splitlines()[0])["duration_ms"]
    assert abs(dur - 300) <= 50  # push = slide_left 300 ms


@needs_sim
def test_diff_against_independent_renderer(packs, tmp_path):
    a = packs / make_test_pack.A
    for screen, floor in (("delta/main", 0.95), ("gamma/main", 0.95), ("_system/home", 0.95)):
        ref = tmp_path / "ref.png"
        refrender.Renderer(a).screen(screen).save(ref)
        res = diff.run(a, screen, ref, tmp_path / "report")
        assert res["ssim"] >= floor, (screen, res["ssim"])


def test_diff_identical_is_one():
    img = Image.new("RGB", (240, 320), (30, 40, 50))
    res = diff.compare(img, img, [{"x": 0, "y": 0, "w": 50, "h": 20, "text": "a"}])
    assert res["ssim"] == 1.0 and res["result"] == "pass"
