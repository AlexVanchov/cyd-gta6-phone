import numpy as np
from PIL import Image, ImageDraw

import measure
import slice as slicer


def scene():
    img = Image.new("RGB", (400, 300), (16, 20, 24))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((100, 80, 260, 240), radius=40, fill=(229, 72, 77))
    return img


def test_sample_and_palette():
    a = np.asarray(scene())
    assert measure.sample(a, 180, 160) == "#E5484D"
    pal = measure.palette(a, 2)
    assert {p[0] for p in pal} == {"#E5484D", "#101418"}


def test_box_and_radius():
    a = np.asarray(scene())
    x, y, w, h = measure.flat_box(a, 180, 160)
    assert (x, y, w, h) == (100, 80, 161, 161)
    r = measure.corner_radius(a, (100, 80, 261, 241))
    assert 30 <= r <= 45


def test_slice_device_size_and_alpha():
    out = slicer.slice_image(scene(), (100, 80, 160, 160), 960, "rounded:40")
    assert out.size == (40, 40)
    assert out.getpixel((0, 0))[3] < 40 and out.getpixel((20, 20))[3] == 255


def test_device_box_edges():
    # edges are rounded, so adjacent boxes stay adjacent
    assert slicer.device_box(0, 0, 150, 150) == (38, 38)
    assert slicer.device_box(150, 150, 150, 150) == (37, 37)
