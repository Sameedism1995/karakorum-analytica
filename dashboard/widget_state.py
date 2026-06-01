"""Safe Streamlit widget session-state resets (before widget mount)."""

from __future__ import annotations

from typing import Any

import streamlit as st

_RESETS_KEY = "_scheduled_widget_resets"


def schedule_widget_resets(values: dict[str, Any]) -> None:
    """Queue widget key updates for the next run (call from button handlers)."""
    pending = dict(st.session_state.get(_RESETS_KEY) or {})
    pending.update(values)
    st.session_state[_RESETS_KEY] = pending


def schedule_widget_reset(key: str, value: Any) -> None:
    """Queue a single widget key update for the next run."""
    schedule_widget_resets({key: value})


def prepare_widgets(defaults: dict[str, Any]) -> None:
    """Apply queued resets and defaults — call before instantiating widgets."""
    pending = st.session_state.pop(_RESETS_KEY, None)
    if pending:
        for key, value in pending.items():
            st.session_state[key] = value
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
