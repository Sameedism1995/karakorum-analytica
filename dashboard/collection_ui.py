"""Collection progress UI for the Streamlit sidebar."""

from __future__ import annotations

import time
from types import ModuleType
from typing import Any

import streamlit as st

COLLECTION_MONITOR_KEY = "collection_monitoring"
COLLECTION_STATUS_KEY = "collection_last_status"


def start_collection_monitor() -> None:
    st.session_state[COLLECTION_MONITOR_KEY] = True
    st.session_state.pop(COLLECTION_STATUS_KEY, None)


def stop_collection_monitor() -> None:
    st.session_state[COLLECTION_MONITOR_KEY] = False


def is_monitoring_collection() -> bool:
    return bool(st.session_state.get(COLLECTION_MONITOR_KEY))


def _format_events(events: list[dict[str, Any]]) -> str:
    if not events:
        return "_Waiting for updates…_"
    lines = []
    for event in events[-12:]:
        msg = event.get("message", "")
        lines.append(f"- {msg}")
    return "\n".join(lines)


def render_collection_progress(
    backend: ModuleType,
    base_url: str,
) -> bool:
    """
    Render progress bar and live event log. Returns True if collection finished
    and the app should rerun to refresh data.
    """
    if not is_monitoring_collection():
        return False

    st.markdown('<div class="section-title">Collection progress</div>', unsafe_allow_html=True)

    if not hasattr(backend, "get_collection_status"):
        st.warning("Progress tracking is unavailable in this backend mode.")
        stop_collection_monitor()
        return False

    status_resp = backend.get_collection_status(base_url)
    if not status_resp.get("ok"):
        st.error(status_resp.get("error") or "Could not read collection status.")
        stop_collection_monitor()
        return False

    data = status_resp.get("data") or {}
    progress = int(data.get("progress") or 0)
    step_label = data.get("step_label") or data.get("step") or "Running"
    state = data.get("status", "idle")
    events = data.get("events") or []

    st.progress(progress / 100, text=f"{step_label} · {progress}%")
    st.markdown(
        f'<div class="collection-log">{_format_events(events)}</div>',
        unsafe_allow_html=True,
    )

    if state == "running":
        time.sleep(1.5)
        st.rerun()

    stop_collection_monitor()
    st.session_state[COLLECTION_STATUS_KEY] = data

    if state == "completed":
        result = data.get("result") or {}
        collection = result.get("collection") or {}
        incidents = result.get("incidents") or {}
        drafts = result.get("drafts") or {}
        st.success(
            f"Collection complete — saved {collection.get('saved', 0)}, "
            f"incidents created {incidents.get('incidents_created', 0)}, "
            f"drafts created {drafts.get('drafts_created', 0)}."
        )
        return True

    if state == "failed":
        st.error(data.get("error") or "Collection failed.")
        return False

    return False


def handle_run_collection_click(backend: ModuleType, base_url: str) -> bool:
    """Start collection and enable monitoring. Returns True if rerun needed."""
    result = backend.run_collection(base_url)
    if not result["ok"]:
        st.error(result.get("error") or "Collection failed.")
        return False

    data = result.get("data") or {}
    if result.get("async") or data.get("status") in {"started", "running"}:
        start_collection_monitor()
        return True

    collection = data.get("collection", {})
    st.success(
        f"Collection complete — saved {collection.get('saved', 0)}, "
        f"incidents {data.get('incidents', {})}, "
        f"drafts {data.get('drafts', {})}."
    )
    return True
