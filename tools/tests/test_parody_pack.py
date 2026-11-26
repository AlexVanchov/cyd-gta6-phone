"""The GatorPhone parody pack builds, validates, and every screen is reachable."""
import json
import shutil

import pytest

import make_parody_pack as mp
import pack


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    if shutil.which("npx") is None:
        pytest.skip("npx (Node.js) needed for lv_font_conv")
    out = tmp_path_factory.mktemp("packs")
    return mp.build(out)


def _actions(elements):
    for e in elements or []:
        a = e.get("action")
        if a:
            yield a
        yield from _actions(e.get("children"))
        yield from _actions(e.get("items"))


def test_validates(built):
    r = pack.validate(built)
    assert r.errors == []


def test_every_screen_reachable_from_lock(built):
    screens = {f"{f.parent.parent.name}/{f.stem}": json.loads(f.read_text())
               for f in (built / "apps").glob("*/screens/*.json")}
    seen, todo = set(), ["_system/lock"]
    while todo:
        s = todo.pop()
        if s in seen:
            continue
        seen.add(s)
        for a in _actions(screens[s]["elements"]):
            if a["type"] == "open_screen":
                todo.append(a["target"])
            elif a["type"] == "run_sequence":
                todo += [st["screen"] for st in a["steps"]]
    unreachable = set(screens) - seen - {"_system/status_bar"}
    assert unreachable == set()


def test_fonts_stay_small(built):
    # Every font is loaded into RAM whole (no PSRAM); keep the set small.
    total = sum(f.stat().st_size for f in (built / "fonts").glob("*.bin"))
    assert total < 80 * 1024
