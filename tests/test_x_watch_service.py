"""Tests for X watch list handle normalization."""

from app.services.x_watch_service import normalize_x_handle


def test_normalize_at_handle():
    assert normalize_x_handle("@TKCkhyber") == "tkckhyber"


def test_normalize_profile_url():
    assert normalize_x_handle("https://x.com/TKCkhyber") == "tkckhyber"


def test_normalize_invalid():
    assert normalize_x_handle("") is None
    assert normalize_x_handle("not a valid handle!!!") is None
