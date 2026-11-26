import io

import pytest
from PIL import Image

import video


def test_container_roundtrip(tmp_path):
    frames = [Image.new("RGB", (240, 135), (i * 20, 0, 0)) for i in range(5)]
    info = video.write_container(tmp_path / "c.mjpeg", frames, 12.0)
    assert info["frames"] == 5
    hdr, data = video.read_container(tmp_path / "c.mjpeg")
    assert (hdr["w"], hdr["h"], hdr["fps"], hdr["frames"]) == (240, 135, 12.0, 5)
    first = Image.open(io.BytesIO(data[0]))
    assert first.format == "JPEG" and first.size == (240, 135)
    assert data[0][:4] == b"\xff\xd8\xff\xe0"  # JFIF APP0, what TJpgDec expects


def test_rejects_too_large(tmp_path):
    with pytest.raises(ValueError):
        video.write_container(tmp_path / "x.mjpeg", [Image.new("RGB", (240, 320))], 12)
