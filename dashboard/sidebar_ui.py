"""Streamlit sidebar — app status and ingestion pipeline controls."""

from __future__ import annotations

from types import ModuleType
from typing import Any

import streamlit as st

from dashboard.collection_ui import (
    handle_run_collection_click,
    is_monitoring_collection,
    render_sidebar_ingestion_progress,
)


def render_app_sidebar(
    backend: ModuleType,
    base_url: str,
    *,
    embedded: bool,
    health: dict[str, Any],
    on_render: bool,
) -> bool:
    """Status, re-run ingestion pipeline, and live progress (no API URL / auto-refresh)."""
    st.markdown("### App status")

    connected = bool(health.get("ok"))
    degraded = bool(health.get("degraded"))
    data = health.get("data") or {}

    st.markdown('<div class="sidebar-status-box">', unsafe_allow_html=True)
    if connected:
        label = "Embedded backend" if embedded else ("API connected (REST reads)" if degraded else "API connected")
        st.markdown(
            f'<span class="status-pill status-connected">{label}</span>',
            unsafe_allow_html=True,
        )
        if degraded:
            st.caption(
                "Postgres is offline on Render (IPv6). Dashboard reads via Supabase REST. "
                "Set SUPABASE_DB_POOLER_URL on the API service for ingestion writes."
            )
    else:
        st.markdown(
            '<span class="status-pill status-disconnected">Not connected</span>',
            unsafe_allow_html=True,
        )
        err = health.get("error") or health.get("detail")
        if err and err != "not_found":
            st.caption(str(err)[:200])
    st.markdown("</div>", unsafe_allow_html=True)

    db_meta = data.get("database") or {}
    if embedded and hasattr(backend, "get_database_status"):
        db_info = backend.get_database_status()
        db_meta = {
            "using_supabase": db_info.get("using_supabase"),
            "backend": db_info.get("backend"),
            "connected": db_info.get("ok"),
        }
        if not db_info.get("ok"):
            st.caption(f"DB: {db_info.get('error', 'offline')[:120]}")
    elif db_meta:
        if db_meta.get("using_supabase"):
            db_line = f"Database: Supabase ({db_meta.get('backend', 'postgres')})"
            if degraded and not db_meta.get("connected"):
                db_line += " · REST fallback"
            st.caption(db_line)
        else:
            st.caption(f"Database: {db_meta.get('backend', 'local')} (set SUPABASE_DB_URL)")

    scweet = data.get("scweet") or {}
    if scweet.get("enabled"):
        if scweet.get("has_auth_token") and scweet.get("client_ok"):
            st.caption("X / Scweet: ready")
        elif scweet.get("has_auth_token"):
            st.caption("X / Scweet: token set, client idle")
        else:
            st.caption("X / Scweet: token missing")

    if on_render and embedded and not connected:
        if st.button("Retry API connection", use_container_width=True, key="sidebar_retry_api"):
            st.rerun()

    st.divider()
    st.markdown("### Ingestion pipeline")

    if st.button(
        "Re-run full ingestion pipeline",
        type="primary",
        use_container_width=True,
        key="sidebar_rerun_ingestion",
        disabled=not connected,
        help="GDELT, ReliefWeb, ACLED, RSS, X search, watch-list profiles → Supabase → incidents → drafts",
    ):
        if handle_run_collection_click(backend, base_url):
            st.rerun()

    should_rerun = render_sidebar_ingestion_progress(backend, base_url)

    st.caption(
        "Configure sources under **Data Ingestion**. "
        "Human review only · no auto-posting by default."
    )
    return should_rerun
