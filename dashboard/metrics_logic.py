"""Pure metrics merge helpers (no Streamlit dependency)."""

from __future__ import annotations

from typing import Any

DEFAULT_METRICS: dict[str, Any] = {
    "total_raw": 0,
    "total_incidents": 0,
    "total_drafts": 0,
    "sources_active": 0,
    "ready_for_review": 0,
    "needs_review": 0,
    "save_only": 0,
    "last_collection": "—",
}

_NUMERIC_KEYS = (
    "total_raw",
    "total_incidents",
    "total_drafts",
    "sources_active",
    "ready_for_review",
    "needs_review",
    "save_only",
)


def merge_dashboard_metrics(
    cached: dict[str, Any],
    fresh: dict[str, Any],
) -> dict[str, Any]:
    """Prefer fresh DB totals; never drop KPIs to zero after a successful prior load."""
    merged = dict(DEFAULT_METRICS)
    merged.update(fresh)

    for key in _NUMERIC_KEYS:
        fresh_val = int(fresh.get(key) or 0)
        cached_val = int(cached.get(key) or 0)
        if fresh_val == 0 and cached_val > 0:
            merged[key] = cached_val
        else:
            merged[key] = max(fresh_val, cached_val)

    fresh_last = fresh.get("last_collection") or "—"
    cached_last = cached.get("last_collection") or "—"
    if fresh_last != "—":
        merged["last_collection"] = fresh_last
    elif cached_last != "—":
        merged["last_collection"] = cached_last

    return merged
