import numpy as np
from PIL import Image

import convert


def test_roundtrip_opaque():
    img = Image.fromarray(np.random.default_rng(1).integers(0, 256, (7, 9, 3), dtype=np.uint8))
    data = convert.encode(img)
    assert data[0] == convert.MAGIC and data[1] == convert.CF_RGB565
    assert len(data) == 12 + 7 * 9 * 2
    back = np.asarray(convert.decode(data)).astype(int)
    assert np.abs(back - np.asarray(img).astype(int)).max() <= 8  # RGB565 quantisation


def test_alpha_kept_only_when_used():
    rgba = Image.new("RGBA", (4, 3), (10, 20, 30, 255))
    assert convert.encode(rgba)[1] == convert.CF_RGB565
    rgba.putpixel((0, 0), (10, 20, 30, 0))
    data = convert.encode(rgba)
    assert data[1] == convert.CF_RGB565A8 and len(data) == 12 + 4 * 3 * 3
    assert convert.decode(data).getpixel((0, 0))[3] == 0


def test_header_fields(tmp_path):
    p = tmp_path / "a.bin"
    p.write_bytes(convert.encode(Image.new("RGB", (240, 2))))
    h = convert.read_header(p)
    assert (h["w"], h["h"], h["stride"]) == (240, 2, 480)
