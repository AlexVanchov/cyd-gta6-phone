import pytest

import clockrate


def test_rate_linear():
    pairs = [clockrate.parse_pair(p) for p in ("0=14:00", "60=14:30", "120=15:00")]
    assert clockrate.rate(pairs) == pytest.approx(30.0)


def test_rate_midnight():
    pairs = [clockrate.parse_pair(p) for p in ("0=23:50", "40=00:10")]
    assert clockrate.rate(pairs) == pytest.approx(30.0)


def test_needs_two():
    with pytest.raises(ValueError):
        clockrate.rate([(0, 0)])
