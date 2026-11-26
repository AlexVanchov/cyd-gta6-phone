import cv2
import numpy as np

import rectify


def synthetic_capture():
    """A 3:6.5 'phone screen' with a pattern, warped into a cluttered scene."""
    w, h = 300, 650
    screen = np.full((h, w, 3), 230, np.uint8)
    cv2.rectangle(screen, (20, 40), (280, 120), (40, 80, 200), -1)
    cv2.putText(screen, "TEST", (60, 400), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 0), 4)
    scene = np.full((900, 900, 3), 40, np.uint8)
    dst = np.float32([[320, 110], [610, 140], [590, 800], [290, 770]])
    src = np.float32([[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]])
    m = cv2.getPerspectiveTransform(src, dst)
    warped = cv2.warpPerspective(screen, m, (900, 900))
    mask = cv2.warpPerspective(np.full((h, w), 255, np.uint8), m, (900, 900))
    scene[mask > 0] = warped[mask > 0]
    return scene, dst


def test_finds_corners():
    scene, truth = synthetic_capture()
    c = rectify.find_screen(scene)
    assert c is not None
    assert np.abs(c - rectify.order_corners(truth)).max() < 6


def test_warp_size_and_aspect(tmp_path):
    scene, truth = synthetic_capture()
    src = tmp_path / "cap.png"
    cv2.imwrite(str(src), scene)
    info = rectify.rectify_file(src, tmp_path / "out.png")
    out = cv2.imread(str(tmp_path / "out.png"))
    assert out.shape[1] == 960
    assert abs(info["aspect"] - out.shape[0] / 960) < 0.01
    assert 1.9 < info["aspect"] < 2.6
    # The blue header ends up near the top of the canonical image.
    assert out[int(out.shape[0] * 0.12), 480][2] > 150  # BGR: header drawn with R=200


def test_order_corners():
    pts = np.float32([[10, 100], [100, 100], [100, 0], [0, 0]])
    o = rectify.order_corners(pts)
    assert o[0].tolist() == [0, 0] and o[2].tolist() == [100, 100]
