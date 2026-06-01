"""Metrics merge logic tests."""

from dashboard.metrics_logic import DEFAULT_METRICS, merge_dashboard_metrics


def test_merge_metrics_never_regresses_to_zero():
    cached = {**DEFAULT_METRICS, "total_raw": 42, "total_incidents": 5}
    fresh = {**DEFAULT_METRICS, "total_raw": 0, "total_incidents": 0}
    merged = merge_dashboard_metrics(cached, fresh)
    assert merged["total_raw"] == 42
    assert merged["total_incidents"] == 5


def test_merge_metrics_accepts_higher_fresh_totals():
    cached = {**DEFAULT_METRICS, "total_raw": 10}
    fresh = {**DEFAULT_METRICS, "total_raw": 15}
    merged = merge_dashboard_metrics(cached, fresh)
    assert merged["total_raw"] == 15
