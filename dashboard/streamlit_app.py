"""Karakorum Analytica — Streamlit monitoring dashboard."""

from __future__ import annotations

import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard.env_bootstrap import bootstrap_env

bootstrap_env(ROOT)

from dashboard import api_client, embedded_backend
from dashboard.branding import BRAND_NAME, LOGO_PATH, render_sidebar_logo
from dashboard.drafts_ui import render_drafts_tab
from dashboard.incidents_ui import render_incidents_tab
from dashboard.ingestion_ui import render_ingestion_tab
from dashboard.sidebar_ui import render_app_sidebar
from dashboard.metrics_cache import load_metrics
from dashboard.scweet_ui import render_scweet_tab
from dashboard.spiderfoot_ui import render_spiderfoot_tab
from dashboard.styles import CUSTOM_CSS
from dashboard.ui_components import (
    drafts_to_dataframe,
    filter_raw_news_df,
    incidents_to_dataframe,
    inject_styles,
    raw_news_to_dataframe,
    render_header,
    render_overview_charts,
    render_overview_kpis,
    render_raw_news_cards,
    render_system_status,
)

LOCAL_API_URL = api_client.resolve_base_url("http://127.0.0.1:8000")


def _is_streamlit_cloud() -> bool:
    """Detect Streamlit Community Cloud."""
    env = os.environ
    if env.get("STREAMLIT_SERVER_ENV", "").lower() == "cloud":
        return True
    if env.get("STREAMLIT_RUNTIME_ENVIRONMENT", "").lower() == "cloud":
        return True
    if env.get("STREAMLIT_CLOUD", "").lower() in {"1", "true", "yes"}:
        return True
    if ".streamlit.app" in env.get("HOSTNAME", ""):
        return True
    # Streamlit Cloud runs from /mount/src/<repo>
    if str(ROOT).startswith("/mount/src") or "/mount/src/" in os.getcwd():
        return True
    try:
        host = st.context.headers.get("Host", "")
        if ".streamlit.app" in host:
            return True
    except Exception:
        pass
    return False


def _configured_api_url() -> str:
    try:
        secret_url = st.secrets.get("API_BASE_URL", "")
        if secret_url and str(secret_url).strip():
            return str(secret_url).strip().rstrip("/")
    except Exception:
        pass
    return api_client.resolve_base_url()


def _on_render() -> bool:
    return bool(os.environ.get("RENDER"))


def _api_reachable(
    url: str,
    *,
    attempts: int = 1,
    timeout: int = 30,
) -> bool:
    if not url:
        return False
    for attempt in range(attempts):
        if api_client.check_backend(url, timeout=timeout).get("ok"):
            return True
        if attempt < attempts - 1:
            time.sleep(3)
    return False


def _choose_backend() -> tuple[ModuleType, str, bool]:
    """Return backend module, display label, and whether mode is embedded."""
    is_cloud = _is_streamlit_cloud()
    api_url = _configured_api_url()
    is_render = _on_render()

    if api_url:
        attempts = 5 if is_render else 2
        timeout = 90 if is_render else 30
        if _api_reachable(api_url, attempts=attempts, timeout=timeout):
            label = api_url if not is_render else f"API ({api_url})"
            return api_client, api_url, False

    if is_cloud:
        return embedded_backend, "embedded (Streamlit Cloud)", True

    if api_url and api_url != LOCAL_API_URL:
        return embedded_backend, "embedded (remote API unavailable)", True

    if _api_reachable(LOCAL_API_URL):
        return api_client, LOCAL_API_URL, False

    embedded_health = embedded_backend.check_backend("")
    if embedded_health.get("ok"):
        return embedded_backend, "embedded (local API offline)", True

    return embedded_backend, "embedded", True


def _now_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def main() -> None:
    st.set_page_config(
        page_title=BRAND_NAME,
        page_icon=str(LOGO_PATH),
        layout="wide",
        initial_sidebar_state="expanded",
        menu_items={
            "About": f"# {BRAND_NAME}\nPakistan-focused security intelligence dashboard.",
        },
    )

    inject_styles(CUSTOM_CSS)
    render_header()

    backend, _backend_label, embedded = _choose_backend()
    base_url = "" if embedded else (_configured_api_url() or LOCAL_API_URL)

    health = backend.check_backend(base_url)

    with st.sidebar:
        render_sidebar_logo()
        if render_app_sidebar(
            backend,
            base_url,
            embedded=embedded,
            health=health,
            on_render=_on_render(),
        ):
            st.rerun()
    raw_items = backend.get_raw_news(base_url) if health["ok"] else []
    incident_items = backend.get_incidents(base_url) if health["ok"] else []
    draft_items = backend.get_drafts(base_url) if health["ok"] else []

    raw_df = raw_news_to_dataframe(raw_items)
    incidents_df = incidents_to_dataframe(incident_items)
    drafts_df = drafts_to_dataframe(draft_items)

    metrics = load_metrics(backend, base_url, health_ok=health["ok"])
    last_refresh = _now_str()
    x_posting_enabled = bool((health.get("data") or {}).get("x_posting_enabled", False))

    if not health["ok"] and not embedded:
        st.markdown(
            f'<div class="error-box">Cannot reach backend at <strong>{base_url}</strong>. '
            f'Start the API with <code>uvicorn app.main:app --reload</code> or wait for Render to wake up.</div>',
            unsafe_allow_html=True,
        )
    elif health.get("degraded"):
        st.markdown(
            '<div class="warn-box"><strong>Degraded mode:</strong> Postgres is unreachable from Render '
            "(IPv6). Showing data via Supabase REST. Ingestion writes need "
            "<code>SUPABASE_DB_POOLER_URL</code> on the API service.</div>",
            unsafe_allow_html=True,
        )

    tab_overview, tab_raw, tab_incidents, tab_drafts, tab_ingestion, tab_scweet, tab_spiderfoot, tab_system = st.tabs(
        [
            "Overview",
            "Raw News",
            "Incidents",
            "Drafts",
            "Data Ingestion",
            "X explorer",
            "SpiderFoot",
            "System Status",
        ]
    )

    with tab_overview:
        render_overview_kpis(metrics)
        if health["ok"]:
            render_overview_charts(raw_df, incidents_df)
        else:
            st.info("Connect to the backend to view charts.")

    with tab_raw:
        if health["ok"]:
            filtered = filter_raw_news_df(raw_df)
            render_raw_news_cards(filtered)
        else:
            st.warning("Backend unavailable — raw news cannot be loaded.")

    with tab_incidents:
        render_incidents_tab(incident_items, health_ok=health["ok"])

    with tab_drafts:
        render_drafts_tab(
            backend,
            base_url,
            health_ok=health["ok"],
            draft_items=draft_items,
            incident_items=incident_items,
            x_posting_enabled=x_posting_enabled,
        )

    with tab_ingestion:
        render_ingestion_tab(
            backend,
            base_url,
            embedded=embedded,
            health=health,
            raw_df=raw_df,
        )

    with tab_scweet:
        render_scweet_tab(
            backend,
            base_url,
            health_ok=health["ok"],
            raw_df=raw_df,
        )

    with tab_spiderfoot:
        render_spiderfoot_tab(
            backend,
            base_url,
            health_ok=health["ok"],
        )

    with tab_system:
        render_system_status(
            health=health,
            base_url=base_url or "embedded",
            metrics=metrics,
            raw_df=raw_df,
            last_refresh=last_refresh,
        )


if __name__ == "__main__":
    main()
