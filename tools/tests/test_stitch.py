import numpy as np

import stitch


def make_frames(top=40, view=300, total=900, step=37, w=120):
    rng = np.random.default_rng(3)
    content = (rng.integers(0, 255, (total, w, 3))).astype(np.uint8)
    content = np.repeat(np.repeat(content[::6, ::6], 6, 0), 6, 1)[:total, :w]
    bar = np.full((top, w, 3), 200, np.uint8)
    frames, y = [], 0
    while y + view <= total:
        frames.append(np.vstack([bar, content[y:y + view]]))
        frames.append(frames[-1].copy())  # duplicate frame
        y += step
    return frames, content, bar


def test_stitch_recovers_content():
    frames, content, bar = make_frames()
    out, info = stitch.stitch_frames(frames, top=40, bottom=0)
    assert info["dropped"] >= len(frames) // 2 - 1
    body = out[40:]
    assert np.array_equal(out[:40], bar)
    assert np.array_equal(body, content[:body.shape[0]])
    assert body.shape[0] >= 300 + 37 * (len(frames) // 2 - 1) - 1
