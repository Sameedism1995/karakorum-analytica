"""Karakorum Analytica — Streamlit monitoring dashboard."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType

import streamlit as st
from streamlit_autorefresh import st_autorefresh

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard import api_client, embedded_backend
from dashboard.branding import BRAND_NAME, LOGO_PATH, render_sidebar_logo
from dashboard.collection_ui import handle_run_collection_click, render_collection_progress
from dashboard.metrics_cache import load_metrics
from dashboard.scweet_ui import render_scweet_tab
from dashboard.styles import CUSTOM_CSS
from dashboard.ui_components import (
    drafts_to_dataframe,
    filter_raw_news_df,
    incidents_to_dataframe,
    inject_styles,
    raw_news_to_dataframe,
    render_draft_card,
    render_header,
    render_incident_card,
    render_overview_charts,
    render_overview_kpis,
    render_raw_news_cards,
    render_system_status,
)

REFRESH_OPTIONS = {
    "Off": 0,
    "30 seconds": 30,
    "1 minute": 60,
    "5 minutes": 300,
}

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


def _api_reachable(url: str) -> bool:
    if not url:
        return False
    return bool(api_client.check_backend(url).get("ok"))


def _choose_backend() -> tuple[ModuleType, str, bool]:
    """Return backend module, display label, and whether mode is embedded."""
    is_cloud = _is_streamlit_cloud()
    api_url = _configured_api_url()

    if api_url and _api_reachable(api_url):
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

    backend, backend_label, embedded = _choose_backend()
    base_url = "" if embedded else (_configured_api_url() or LOCAL_API_URL)

    with st.sidebar:
        render_sidebar_logo()
        st.markdown("### Controls")

        if embedded:
            st.info(
                "Running in **embedded mode** — collection runs inside this app. "
                "No separate Render API needed."
            )
            st.text_input("Backend mode", value=backend_label, disabled=True)
        else:
            st.text_input(
                "API base URL",
                value=base_url,
                disabled=_is_streamlit_cloud(),
                help="FastAPI backend address",
            )

        refresh_label = st.selectbox(
            "Auto-refresh",
            list(REFRESH_OPTIONS.keys()),
            index=0,
        )
        refresh_seconds = REFRESH_OPTIONS[refresh_label]

        if st.button("Run Collection Now", type="primary", use_container_width=True):
            if handle_run_collection_click(backend, base_url):
                st.rerun()

        if render_collection_progress(backend, base_url):
            st.rerun()

        health = backend.check_backend(base_url)
        connected = health.get("ok", False)

        st.markdown('<div class="sidebar-status-box">', unsafe_allow_html=True)
        if connected:
            label = "Embedded backend active" if embedded else "Backend connected"
            st.markdown(
                f'<span class="status-pill status-connected">{label}</span>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<span class="status-pill status-disconnected">Backend not connected</span>',
                unsafe_allow_html=True,
            )
            err = health.get("detail") or health.get("error")
            if err and err != "not_found":
                st.caption(err)
            if embedded:
                st.caption("Try rebooting the app from Streamlit Cloud manage menu.")
        st.markdown("</div>", unsafe_allow_html=True)

        if _is_streamlit_cloud() and not embedded:
            st.link_button(
                "Deploy API on Render",
                "https://render.com/deploy?repo=https://github.com/Sameedism1995/karakorum-analytica",
                use_container_width=True,
            )

        st.divider()
        st.caption("Human review only · No auto-posting by default · GDELT · ReliefWeb · ACLED · Scweet")

    if refresh_seconds > 0:
        st_autorefresh(interval=refresh_seconds * 1000, key="dashboard_autorefresh")

    health = backend.check_backend(base_url)
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

    tab_overview, tab_raw, tab_incidents, tab_drafts, tab_scweet, tab_system = st.tabs(
        ["Overview", "Raw News", "Incidents", "Drafts", "X / Scweet", "System Status"]
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
        st.markdown('<div class="section-title">Grouped incidents</div>', unsafe_allow_html=True)
        if not health["ok"]:
            st.warning("Backend unavailable — incidents cannot be loaded.")
        elif not incident_items:
            st.info("No incidents yet. Run collection to group matching reports.")
        else:
            for incident in incident_items:
                render_incident_card(incident)

    with tab_drafts:
        st.markdown('<div class="section-title">Draft posts for review</div>', unsafe_allow_html=True)
        if not health["ok"]:
            st.warning("Backend unavailable — drafts cannot be loaded.")
        elif not draft_items:
            st.info("No draft posts yet. Incidents will generate neutral drafts after collection.")
        else:

            def handle_draft_action(action: str, draft_id: int) -> None:
                if action == "approve":
                    result = backend.approve_draft(draft_id, base_url)
                elif action == "reject":
                    result = backend.reject_draft(draft_id, base_url)
                elif action == "post":
                    result = backend.post_draft(draft_id, base_url)
                else:
                    return
                if result["ok"]:
                    st.success(f"Draft #{draft_id} {action}d successfully.")
                    st.rerun()
                else:
                    st.error(result.get("error") or f"Failed to {action} draft #{draft_id}.")

            for draft in draft_items:
                render_draft_card(
                    draft,
                    x_posting_enabled=x_posting_enabled,
                    base_url=base_url or "embedded",
                    on_action=handle_draft_action,
                )

    with tab_scweet:
        render_scweet_tab(
            backend,
            base_url,
            health_ok=health["ok"],
            raw_df=raw_df,
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
