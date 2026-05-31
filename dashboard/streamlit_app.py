"""KarakorumAnalytica — Streamlit monitoring dashboard."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st
from streamlit_autorefresh import st_autorefresh

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard import api_client
from dashboard.styles import CUSTOM_CSS
from dashboard.ui_components import (
    compute_overview_metrics,
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


def _now_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _default_api_url() -> str:
    """Prefer Streamlit Cloud secrets, then env, then localhost."""
    try:
        url = st.secrets.get("API_BASE_URL", "")
        if url:
            return str(url).strip().rstrip("/")
    except Exception:
        pass
    return api_client.resolve_base_url()


def _handle_draft_action(action: str, draft_id: int, base_url: str) -> None:
    if action == "approve":
        result = api_client.approve_draft(draft_id, base_url)
    elif action == "reject":
        result = api_client.reject_draft(draft_id, base_url)
    elif action == "post":
        result = api_client.post_draft(draft_id, base_url)
    else:
        return

    if result["ok"]:
        st.success(f"Draft #{draft_id} {action}d successfully.")
        st.rerun()
    else:
        st.error(result.get("error") or f"Failed to {action} draft #{draft_id}.")


def main() -> None:
    st.set_page_config(
        page_title="KarakorumAnalytica",
        page_icon="📡",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    inject_styles(CUSTOM_CSS)
    render_header()

    with st.sidebar:
        st.markdown("### Controls")
        deployed = bool(os.environ.get("STREAMLIT_SHARING_MODE") or os.environ.get("API_BASE_URL"))
        default_url = _default_api_url()
        if deployed and default_url != api_client.DEFAULT_BASE_URL:
            base_url = default_url
            st.text_input("API base URL", value=base_url, disabled=True, help="Set via Streamlit secrets")
        else:
            base_url = st.text_input(
                "API base URL",
                value=default_url,
                help="FastAPI backend address",
            ).strip().rstrip("/") or default_url

        refresh_label = st.selectbox(
            "Auto-refresh",
            list(REFRESH_OPTIONS.keys()),
            index=0,
        )
        refresh_seconds = REFRESH_OPTIONS[refresh_label]

        if st.button("Run Collection Now", type="primary", use_container_width=True):
            with st.spinner("Running collection pipeline…"):
                result = api_client.run_collection(base_url)
            if result["ok"]:
                data = result["data"] or {}
                collection = data.get("collection", {})
                st.success(
                    f"Collection complete — saved {collection.get('saved', 0)}, "
                    f"incidents {data.get('incidents', {})}, "
                    f"drafts {data.get('drafts', {})}."
                )
                st.rerun()
            else:
                st.error(result.get("error") or "Collection failed.")

        health = api_client.check_backend(base_url)
        connected = health.get("ok", False)

        st.markdown('<div class="sidebar-status-box">', unsafe_allow_html=True)
        if connected:
            st.markdown(
                '<span class="status-pill status-connected">Backend connected</span>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<span class="status-pill status-disconnected">Backend not connected</span>',
                unsafe_allow_html=True,
            )
            if health.get("error"):
                st.caption(health["error"])
        st.markdown("</div>", unsafe_allow_html=True)

        st.divider()
        st.caption("Human review only · No auto-posting · No X scraping")

    if refresh_seconds > 0:
        st_autorefresh(interval=refresh_seconds * 1000, key="dashboard_autorefresh")

    health = api_client.check_backend(base_url)
    raw_items = api_client.get_raw_news(base_url) if health["ok"] else []
    incident_items = api_client.get_incidents(base_url) if health["ok"] else []
    draft_items = api_client.get_drafts(base_url) if health["ok"] else []

    raw_df = raw_news_to_dataframe(raw_items)
    incidents_df = incidents_to_dataframe(incident_items)
    drafts_df = drafts_to_dataframe(draft_items)

    metrics = compute_overview_metrics(raw_df, incidents_df, drafts_df)
    last_refresh = _now_str()
    x_posting_enabled = bool((health.get("data") or {}).get("x_posting_enabled", False))

    if not health["ok"]:
        st.markdown(
            f'<div class="error-box">Cannot reach backend at <strong>{base_url}</strong>. '
            f'Start the API with <code>uvicorn app.main:app --reload</code> then refresh.</div>',
            unsafe_allow_html=True,
        )

    tab_overview, tab_raw, tab_incidents, tab_drafts, tab_system = st.tabs(
        ["Overview", "Raw News", "Incidents", "Drafts", "System Status"]
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
            for draft in draft_items:
                render_draft_card(
                    draft,
                    x_posting_enabled=x_posting_enabled,
                    base_url=base_url,
                    on_action=lambda action, draft_id, url=base_url: _handle_draft_action(
                        action, draft_id, url
                    ),
                )

    with tab_system:
        render_system_status(
            health=health,
            base_url=base_url,
            metrics=metrics,
            raw_df=raw_df,
            last_refresh=last_refresh,
        )


if __name__ == "__main__":
    main()
