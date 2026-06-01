"""Tests for X posting analytics helpers."""

from app.services.x_posting_analytics import (
    _circular_mean_hour,
    _format_hour_local,
    _handle_from_url,
)


def test_handle_from_url():
    assert _handle_from_url("https://x.com/TKCkhyber/status/123") == "tkckhyber"


def test_circular_mean_hour_noon_cluster():
    mean = _circular_mean_hour([11.5, 12.0, 12.5, 13.0])
    assert mean is not None
    assert 11 <= mean <= 14


def test_circular_mean_wraps_midnight():
    mean = _circular_mean_hour([23.0, 0.5, 1.0])
    assert mean is not None
    assert mean < 3 or mean > 22


def test_format_hour_local():
    label = _format_hour_local(14.5)
    assert "14:30" in label
