import sync


def test_sd_sync_copies_changed_and_deletes_stale(tmp_path):
    src, card = tmp_path / "sd", tmp_path / "card"
    (src / "packs/p1/apps").mkdir(parents=True)
    (src / "packs/p1/manifest.json").write_text("{}")
    (src / "packs/p1/apps/a.bin").write_bytes(b"123")
    (card / "packs/old").mkdir(parents=True)
    r = sync.sync_sd(card, src, delete=True)
    assert r["copied"] == 2 and r["removed"] == ["old"] and not r["verify_failed"]
    assert (card / "packs/p1/apps/a.bin").read_bytes() == b"123"
    assert sync.sync_sd(card, src)["copied"] == 0  # idempotent
    (src / "packs/p1/apps/a.bin").write_bytes(b"124")
    assert sync.sync_sd(card, src)["copied"] == 1


def test_only_filter(tmp_path):
    src = tmp_path / "sd"
    for p in ("p1", "p2"):
        (src / "packs" / p).mkdir(parents=True)
        (src / "packs" / p / "manifest.json").write_text("{}")
    todo = sync.plan_copy(src, tmp_path / "card", only="p2")
    assert [d.parent.name for _, d in todo] == ["p2"]
