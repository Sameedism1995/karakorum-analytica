"""Persist dashboard KPIs across Streamlit reruns and collection polling."""

from __future__ import annotations

from types import ModuleType
from typing import Any

import streamlit as st

from dashboard.metrics_logic import DEFAULT_METRICS, merge_dashboard_metrics

METRICS_CACHE_KEY = "dashboard_metrics_cache"


def get_cached_metrics() -> dict[str, Any]:
    cached = st.session_state.get(METRICS_CACHE_KEY)
    if not cached:
        return dict(DEFAULT_METRICS)
    return {**DEFAULT_METRICS, **cached}


def store_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    cached = get_cached_metrics()
    merged = merge_dashboard_metrics(cached, metrics)
    st.session_state[METRICS_CACHE_KEY] = merged
    return merged


def load_metrics(backend: ModuleType, base_url: str, *, health_ok: bool) -> dict[str, Any]:
    """Fetch stats from backend and merge with session cache."""
    if not health_ok:
        return get_cached_metrics()

    if not hasattr(backend, "get_stats"):
        return get_cached_metrics()

    response = backend.get_stats(base_url)
    if not response.get("ok") or not response.get("data"):
        return get_cached_metrics()

    return store_metrics(response["data"])
