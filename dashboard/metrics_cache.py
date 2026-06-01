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


METRICS_CACHE_KEY = "dashboard_metrics_cache"
SESSION_BOOT_KEY = "dashboard_session_boot"


def reset_metrics_on_new_session() -> None:
    """Clear cached KPIs when the browser opens a new Streamlit session."""
    if st.session_state.get(SESSION_BOOT_KEY):
        return
    st.session_state[SESSION_BOOT_KEY] = True
    st.session_state.pop(METRICS_CACHE_KEY, None)


def _metrics_from_database_health(payload: dict[str, Any]) -> dict[str, Any] | None:
    storage = payload.get("supabase_storage") or {}
    counts = storage.get("counts") or {}
    if not storage.get("ok") or not counts:
        return None
    return {
        "total_raw": int(counts.get("raw_news") or 0),
        "total_incidents": int(counts.get("incidents") or 0),
        "total_drafts": int(counts.get("draft_posts") or 0),
        "sources_active": 0,
        "ready_for_review": 0,
        "needs_review": 0,
        "save_only": 0,
        "last_collection": "—",
    }


def load_metrics(backend: ModuleType, base_url: str, *, health_ok: bool) -> dict[str, Any]:
    """Fetch stats from backend and merge with session cache."""
    reset_metrics_on_new_session()

    if not health_ok:
        return get_cached_metrics()

    if not hasattr(backend, "get_stats"):
        return get_cached_metrics()

    response = backend.get_stats(base_url)
    if response.get("ok") and response.get("data"):
        data = dict(response["data"])
        data.pop("_via", None)
        return store_metrics(data)

    if hasattr(backend, "get_database_health"):
        db_health = backend.get_database_health(base_url)
        if db_health.get("ok") and db_health.get("data"):
            partial = _metrics_from_database_health(db_health["data"])
            if partial:
                return store_metrics(partial)

    return get_cached_metrics()
