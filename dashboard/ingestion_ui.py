"""Data Ingestion tab — API collectors and X watch list."""

from __future__ import annotations

from types import ModuleType
from typing import Any

import streamlit as st

from dashboard.collection_ui import (
    handle_run_collection_click,
    is_monitoring_collection,
    render_collection_progress,
)
from dashboard.scweet_ui import render_x_watch_list

API_SOURCES = [
    ("GDELT", "Global security news (keyword search)"),
    ("ReliefWeb", "Humanitarian reports"),
    ("ACLED", "Conflict events (when configured)"),
    ("News RSS", "Open news channel feeds"),
    ("X / Scweet search", "Keyword search from SCWEET_SEARCH_QUERIES"),
    ("X watch list", "Profile timelines for accounts you add below"),
]


def render_ingestion_connection_banners(
    backend: ModuleType,
    base_url: str,
    *,
    embedded: bool,
    health: dict[str, Any],
) -> bool:
    """
    Show Supabase / API / Scweet readiness banners.

    Returns True when the database is connected enough to ingest data.
    """
    ready = True
    health_ok = bool(health.get("ok"))
    data = health.get("data") or {}

    if not health_ok:
        ready = False
        err = health.get("error") or health.get("detail") or "Backend not connected."
        st.error(f"**Backend:** {err}")
        if embedded:
            st.info(
                "On Render, click **Retry API connection** in the sidebar, or set "
                "**SUPABASE_DB_URL** and **SCWEET_AUTH_TOKEN** on this dashboard service."
            )
        return ready

    # Database / Supabase
    if hasattr(backend, "get_database_status"):
        db_info = backend.get_database_status()
        if not db_info.get("ok"):
            ready = False
            st.error(f"**Database:** {db_info.get('error') or 'Not connected.'}")
        elif not (db_info.get("persistent") or db_info.get("using_supabase")):
            st.warning(
                "**Database:** using a temporary local store on this server. "
                "Set **SUPABASE_DB_URL** on Render (dashboard **and** API) so watch list "
                "accounts and tweets persist after restarts."
            )
        else:
            st.success(
                f"**Database:** connected ({db_info.get('backend', 'postgres')}) · data persists in Supabase"
            )
    else:
        db_meta = data.get("database") or {}
        if db_meta.get("using_supabase"):
            st.success(f"**Database:** Supabase via API ({db_meta.get('backend', 'postgres')})")
        elif health_ok:
            st.warning(
                "**Database:** API is up but not using Supabase. Set **SUPABASE_DB_URL** on the API service."
            )

    # Scweet / X token
    scweet = data.get("scweet") or {}
    if not scweet and hasattr(backend, "get_scweet_status"):
        scweet_resp = backend.get_scweet_status(base_url)
        scweet = (scweet_resp.get("data") or {}).get("scweet") or {}

    if scweet.get("enabled"):
        if scweet.get("has_auth_token"):
            client_ok = scweet.get("client_ok")
            if client_ok:
                st.success("**X / Scweet:** auth token set · client ready")
            else:
                st.warning(
                    f"**X / Scweet:** token set but client not ready"
                    f"{': ' + str(scweet.get('error')) if scweet.get('error') else ''}"
                )
        else:
            ready = False
            st.error(
                "**SCWEET_AUTH_TOKEN** is missing on this service. X fetches will fail until you run "
                "locally:\n\n`python scripts/sync_scweet_token_to_render.py --deploy --write-env`"
            )
            if embedded:
                st.caption(
                    "Playwright login is not available on Render/production. "
                    "Use the sync script above (optional cron: `bash scripts/install_scweet_token_cron.sh`)."
                )
    else:
        st.warning("**X / Scweet:** disabled (SCWEET_ENABLED=false).")

    if not embedded and base_url:
        st.caption(f"**Ingestion backend:** API at `{base_url}`")
    elif embedded:
        st.caption("**Ingestion backend:** embedded (in-process on this app)")

    return ready


def render_api_sources_section(
    backend: ModuleType,
    base_url: str,
    *,
    health_ok: bool,
    db_ready: bool,
) -> None:
    """GDELT, ReliefWeb, ACLED, RSS, and pipeline Scweet search."""
    st.markdown("#### API & feed collectors")
    st.caption(
        "Runs all configured sources, filters for Pakistan security keywords, saves to Supabase, "
        "then groups incidents and drafts."
    )

    for name, desc in API_SOURCES[:5]:
        st.markdown(f"- **{name}** — {desc}")

    if not health_ok:
        st.warning("Fix the connection banners above before running collection.")
        return

    col_run, col_status = st.columns([1, 2])
    with col_run:
        if st.button(
            "Run API collection now",
            type="primary",
            use_container_width=True,
            key="ingestion_run_api_collection",
            disabled=not db_ready,
        ):
            if handle_run_collection_click(backend, base_url):
                st.rerun()

    with col_status:
        if not db_ready:
            st.caption("Database must be connected (Supabase recommended).")
        elif is_monitoring_collection():
            st.caption("Collection in progress — see progress below.")

    if is_monitoring_collection():
        if render_collection_progress(backend, base_url):
            st.rerun()

    st.divider()
    st.markdown("**Source configuration**")
    st.caption(
        "Set collector credentials in Render environment or `.env`: "
        "`ACLED_EMAIL`, `ACLED_API_KEY`, `RELIEFWEB_APPNAME`, `SCWEET_SEARCH_QUERIES`, "
        "`NEWS_CHANNEL_FEEDS`, etc."
    )


def render_x_accounts_section(
    backend: ModuleType,
    base_url: str,
    *,
    health_ok: bool,
    db_ready: bool,
) -> None:
    """Watch list — add/remove X profiles and fetch timelines."""
    st.markdown("#### X account watch list")
    st.caption(
        "Add handles to poll on each **Run API collection** (watch-list step) or fetch manually. "
        "All tweets are saved to Supabase (`raw_news`)."
    )

    if not health_ok:
        st.warning("Fix the connection banners above before adding X accounts.")
        return

    if not db_ready:
        st.warning("Connect Supabase before using the watch list.")
        return

    render_x_watch_list(backend, base_url)


def render_ingestion_tab(
    backend: ModuleType,
    base_url: str,
    *,
    embedded: bool,
    health: dict[str, Any],
    raw_df: Any = None,
) -> None:
    """Top-level Data Ingestion tab."""
    del raw_df
    st.markdown('<div class="section-title">Data Ingestion</div>', unsafe_allow_html=True)
    st.caption("Add data from API/feed collectors or from specific X accounts. Everything saves to your database.")

    db_ready = render_ingestion_connection_banners(
        backend,
        base_url,
        embedded=embedded,
        health=health,
    )

    tab_api, tab_x = st.tabs(["API sources", "X accounts"])

    with tab_api:
        render_api_sources_section(
            backend,
            base_url,
            health_ok=bool(health.get("ok")),
            db_ready=db_ready,
        )

    with tab_x:
        render_x_accounts_section(
            backend,
            base_url,
            health_ok=bool(health.get("ok")),
            db_ready=db_ready,
        )
