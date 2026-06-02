"""Reusable Streamlit UI components for Karakorum Analytica."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from app.config import TARGET_KEYWORDS
from dashboard.branding import BRAND_NAME, LOGO_ALT, logo_data_uri
from dashboard.theme import (
    CHART_SEQUENCE,
    MIDNIGHT_NAVY,
    SIGNAL_CRIMSON,
    SLATE_BLUE,
    STATUS_CHART_COLORS,
    STEEL_MIST,
)

STATUS_BADGE_CLASS = {
    "save_only": "badge-grey",
    "needs_review": "badge-orange",
    "ready_for_review": "badge-green",
    "pending": "badge-blue",
    "drafted": "badge-blue",
    "approved": "badge-green",
    "rejected": "badge-red",
    "posted": "badge-purple",
    "sent_to_buffer": "badge-purple",
    "failed": "badge-red",
    "collected": "badge-blue",
}

STATUS_LABEL = {
    "save_only": "Save only",
    "needs_review": "Needs review",
    "ready_for_review": "Ready for review",
    "pending": "Pending",
    "drafted": "Drafted",
    "approved": "Approved",
    "rejected": "Rejected",
    "posted": "Posted",
    "sent_to_buffer": "Sent to Buffer",
    "failed": "Failed",
    "collected": "Collected",
}

SOURCE_CLASS = {
    "GDELT": "source-gdelt",
    "ReliefWeb": "source-reliefweb",
    "ACLED": "source-acled",
}

EXPECTED_SOURCES = ("GDELT", "ReliefWeb", "ACLED")


def inject_styles(css: str) -> None:
    st.markdown(css, unsafe_allow_html=True)


def render_header() -> None:
    logo_uri = logo_data_uri()
    st.markdown(
        f"""
        <div class="main-header">
            <div class="main-header-inner">
                <div class="main-header-logo-wrap">
                    <img src="{logo_uri}" alt="{LOGO_ALT}" class="main-header-logo" />
                </div>
                <div class="main-header-text">
                    <h1 class="main-header-title">{BRAND_NAME}</h1>
                    <p class="main-header-tagline">
                        Security intelligence · GDELT, ReliefWeb, ACLED, Scweet · Human review only
                    </p>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_kpi_card(label: str, value: str | int, sub: str = "") -> None:
    sub_html = f'<div class="kpi-sub">{sub}</div>' if sub else ""
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-label">{label}</div>
            <div class="kpi-value">{value}</div>
            {sub_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def status_badge_html(status: str | None) -> str:
    key = (status or "unknown").lower()
    css_class = STATUS_BADGE_CLASS.get(key, "badge-grey")
    label = STATUS_LABEL.get(key, key.replace("_", " ").title())
    return f'<span class="badge {css_class}">{label}</span>'


def source_tag_html(source_name: str | None) -> str:
    name = source_name or "Unknown"
    css_class = SOURCE_CLASS.get(name, "badge-grey")
    return f'<span class="source-tag {css_class}">{name}</span>'


def format_datetime(value: Any) -> str:
    """Format API/DB/pandas datetime values for display."""
    if value is None:
        return "—"
    try:
        if isinstance(value, float):
            if pd.isna(value):
                return "—"
            return _format_epoch(value)
        if isinstance(value, int):
            return _format_epoch(float(value))
        if isinstance(value, datetime):
            dt = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
            return dt.strftime("%Y-%m-%d %H:%M UTC")
        if hasattr(value, "to_pydatetime"):
            dt = value.to_pydatetime()
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.strftime("%Y-%m-%d %H:%M UTC")
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return "—"
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.strftime("%Y-%m-%d %H:%M UTC")
    except (ValueError, TypeError, OSError, OverflowError):
        return str(value)
    return str(value)


def _format_epoch(ts: float) -> str:
    """Unix timestamp (seconds or milliseconds) → display string."""
    if ts > 1e12:
        ts = ts / 1000.0
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M UTC")


def extract_keywords(title: str | None, summary: str | None) -> list[str]:
    combined = f"{title or ''} {summary or ''}".lower()
    matched = [kw for kw in TARGET_KEYWORDS if kw in combined]
    return sorted(set(matched))


def raw_news_to_dataframe(items: list[dict[str, Any]]) -> pd.DataFrame:
    if not items:
        return pd.DataFrame(
            columns=[
                "id",
                "source_name",
                "title",
                "summary",
                "url",
                "published_at",
                "collected_at",
                "country",
                "province",
                "city",
                "status",
                "keywords",
            ]
        )

    rows = []
    for item in items:
        keywords = extract_keywords(item.get("title"), item.get("summary"))
        rows.append(
            {
                **item,
                "keywords": ", ".join(keywords) if keywords else "—",
                "keywords_list": keywords,
            }
        )
    return pd.DataFrame(rows)


def incidents_to_dataframe(items: list[dict[str, Any]]) -> pd.DataFrame:
    if not items:
        return pd.DataFrame()
    return pd.DataFrame(items)


def drafts_to_dataframe(items: list[dict[str, Any]]) -> pd.DataFrame:
    if not items:
        return pd.DataFrame()
    return pd.DataFrame(items)


def compute_overview_metrics(
    raw_df: pd.DataFrame,
    incidents_df: pd.DataFrame,
    drafts_df: pd.DataFrame,
) -> dict[str, Any]:
    incident_status_counts = {}
    if not incidents_df.empty and "status" in incidents_df.columns:
        incident_status_counts = incidents_df["status"].value_counts().to_dict()

    sources_active = 0
    if not raw_df.empty and "source_name" in raw_df.columns:
        sources_active = raw_df["source_name"].nunique()

    last_collection = "—"
    if not raw_df.empty and "collected_at" in raw_df.columns:
        try:
            latest = pd.to_datetime(raw_df["collected_at"], utc=True, errors="coerce").max()
            if pd.notna(latest):
                last_collection = latest.strftime("%Y-%m-%d %H:%M UTC")
        except Exception:
            pass

    return {
        "total_raw": len(raw_df),
        "total_incidents": len(incidents_df),
        "total_drafts": len(drafts_df),
        "ready_for_review": incident_status_counts.get("ready_for_review", 0),
        "needs_review": incident_status_counts.get("needs_review", 0),
        "save_only": incident_status_counts.get("save_only", 0),
        "sources_active": sources_active,
        "last_collection": last_collection,
    }


def render_overview_kpis(metrics: dict[str, Any]) -> None:
    row1 = st.columns(4)
    with row1[0]:
        render_kpi_card("Total raw news", metrics["total_raw"])
    with row1[1]:
        render_kpi_card("Total incidents", metrics["total_incidents"])
    with row1[2]:
        render_kpi_card("Total draft posts", metrics["total_drafts"])
    with row1[3]:
        render_kpi_card("Sources active", metrics["sources_active"], "GDELT · ReliefWeb · ACLED")

    row2 = st.columns(4)
    with row2[0]:
        render_kpi_card("Ready for review", metrics["ready_for_review"])
    with row2[1]:
        render_kpi_card("Needs review", metrics["needs_review"])
    with row2[2]:
        render_kpi_card("Save only", metrics["save_only"])
    with row2[3]:
        render_kpi_card("Last collection", metrics["last_collection"])


def _empty_chart(message: str) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        xref="paper",
        yref="paper",
        x=0.5,
        y=0.5,
        showarrow=False,
        font={"size": 14, "color": STEEL_MIST},
    )
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis={"visible": False},
        yaxis={"visible": False},
        margin={"l": 20, "r": 20, "t": 30, "b": 20},
        height=320,
    )
    return fig


def chart_news_by_source(raw_df: pd.DataFrame) -> go.Figure:
    if raw_df.empty or "source_name" not in raw_df.columns:
        return _empty_chart("No raw news yet — run collection")
    counts = raw_df["source_name"].value_counts().reset_index()
    counts.columns = ["source", "count"]
    fig = px.bar(
        counts,
        x="source",
        y="count",
        color="source",
        title="News by source",
        text="count",
        color_discrete_sequence=CHART_SEQUENCE,
    )
    fig.update_traces(marker_line_width=0)
    fig.update_layout(
        showlegend=False,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin={"l": 20, "r": 20, "t": 40, "b": 20},
        height=320,
        xaxis_title="",
        yaxis_title="Articles",
        coloraxis_showscale=False,
        font={"color": MIDNIGHT_NAVY},
        title_font={"color": MIDNIGHT_NAVY, "size": 16},
    )
    return fig


def chart_incidents_by_status(incidents_df: pd.DataFrame) -> go.Figure:
    if incidents_df.empty or "status" not in incidents_df.columns:
        return _empty_chart("No incidents yet")
    counts = incidents_df["status"].value_counts().reset_index()
    counts.columns = ["status", "count"]
    counts["label"] = counts["status"].map(
        lambda s: STATUS_LABEL.get(s, s.replace("_", " ").title())
    )
    colors = STATUS_CHART_COLORS
    fig = px.pie(
        counts,
        names="label",
        values="count",
        title="Incidents by confidence status",
        color="status",
        color_discrete_map={
            k: colors.get(k, STEEL_MIST)
            for k in counts["status"]
        },
        hole=0.45,
    )
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        margin={"l": 20, "r": 20, "t": 40, "b": 20},
        height=320,
        showlegend=True,
        legend={"orientation": "h", "y": -0.1},
        font={"color": MIDNIGHT_NAVY},
        title_font={"color": MIDNIGHT_NAVY, "size": 16},
    )
    return fig


def chart_top_keywords(incidents_df: pd.DataFrame, raw_df: pd.DataFrame) -> go.Figure:
    keyword_counts: dict[str, int] = {}

    if not incidents_df.empty and "keywords" in incidents_df.columns:
        for kw_str in incidents_df["keywords"].dropna():
            for kw in str(kw_str).split(","):
                kw = kw.strip()
                if kw:
                    keyword_counts[kw] = keyword_counts.get(kw, 0) + 1

    if not keyword_counts and not raw_df.empty:
        for _, row in raw_df.iterrows():
            for kw in extract_keywords(row.get("title"), row.get("summary")):
                keyword_counts[kw] = keyword_counts.get(kw, 0) + 1

    if not keyword_counts:
        return _empty_chart("No keywords detected yet")

    top = sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True)[:12]
    df = pd.DataFrame(top, columns=["keyword", "count"])
    fig = px.bar(
        df,
        x="count",
        y="keyword",
        orientation="h",
        title="Top detected keywords",
        text="count",
    )
    fig.update_traces(marker_color=SIGNAL_CRIMSON, marker_line_width=0)
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin={"l": 20, "r": 20, "t": 40, "b": 20},
        height=320,
        yaxis={"categoryorder": "total ascending"},
        xaxis_title="Mentions",
        yaxis_title="",
        font={"color": MIDNIGHT_NAVY},
        title_font={"color": MIDNIGHT_NAVY, "size": 16},
    )
    return fig


def chart_news_by_location(raw_df: pd.DataFrame) -> go.Figure:
    if raw_df.empty:
        return _empty_chart("No location data yet")

    location_counts: dict[str, int] = {}
    for _, row in raw_df.iterrows():
        province = row.get("province")
        city = row.get("city")
        if city and province:
            label = f"{city}, {province}"
        elif province:
            label = str(province)
        elif city:
            label = str(city)
        else:
            label = "Unknown"
        location_counts[label] = location_counts.get(label, 0) + 1

    if not location_counts or list(location_counts.keys()) == ["Unknown"]:
        return _empty_chart("No province/city data available")

    top = sorted(location_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    df = pd.DataFrame(top, columns=["location", "count"])
    fig = px.bar(
        df,
        x="count",
        y="location",
        orientation="h",
        title="News by province / city",
        text="count",
    )
    fig.update_traces(marker_color=SLATE_BLUE, marker_line_width=0)
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin={"l": 20, "r": 20, "t": 40, "b": 20},
        height=320,
        yaxis={"categoryorder": "total ascending"},
        xaxis_title="Articles",
        yaxis_title="",
        font={"color": MIDNIGHT_NAVY},
        title_font={"color": MIDNIGHT_NAVY, "size": 16},
    )
    return fig


def render_overview_charts(raw_df: pd.DataFrame, incidents_df: pd.DataFrame) -> None:
    st.markdown('<div class="section-title">Collection analytics</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(chart_news_by_source(raw_df), use_container_width=True)
    with c2:
        st.plotly_chart(chart_incidents_by_status(incidents_df), use_container_width=True)

    c3, c4 = st.columns(2)
    with c3:
        st.plotly_chart(chart_top_keywords(incidents_df, raw_df), use_container_width=True)
    with c4:
        st.plotly_chart(chart_news_by_location(raw_df), use_container_width=True)


def filter_raw_news_df(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        st.info("No raw news collected yet. Click **Run Collection Now** in the sidebar.")
        return df

    st.markdown('<div class="section-title">Filters</div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1:
        sources = ["All"] + sorted(df["source_name"].dropna().unique().tolist())
        source_filter = st.selectbox("Source", sources, key="raw_source_filter")
    with c2:
        provinces = ["All"] + sorted(
            [p for p in df["province"].dropna().unique().tolist() if p]
        )
        province_filter = st.selectbox("Province", provinces, key="raw_province_filter")
    with c3:
        cities = ["All"] + sorted([c for c in df["city"].dropna().unique().tolist() if c])
        city_filter = st.selectbox("City", cities, key="raw_city_filter")

    c4, c5, c6 = st.columns(3)
    with c4:
        statuses = ["All"] + sorted(df["status"].dropna().unique().tolist())
        status_filter = st.selectbox("Status", statuses, key="raw_status_filter")
    with c5:
        all_keywords = sorted(
            {
                kw
                for kws in df.get("keywords_list", pd.Series([], dtype=object))
                for kw in (kws if isinstance(kws, list) else [])
            }
        )
        keyword_filter = st.selectbox(
            "Keyword",
            ["All"] + all_keywords,
            key="raw_keyword_filter",
        )
    with c6:
        search = st.text_input("Search title / summary", "", key="raw_search")

    date_min = date_max = None
    if "collected_at" in df.columns:
        dates = pd.to_datetime(df["collected_at"], utc=True, errors="coerce").dropna()
        if not dates.empty:
            c7, c8 = st.columns(2)
            with c7:
                date_min = st.date_input(
                    "Collected from",
                    value=dates.min().date(),
                    key="raw_date_min",
                )
            with c8:
                date_max = st.date_input(
                    "Collected to",
                    value=dates.max().date(),
                    key="raw_date_max",
                )

    filtered = df.copy()
    if source_filter != "All":
        filtered = filtered[filtered["source_name"] == source_filter]
    if province_filter != "All":
        filtered = filtered[filtered["province"] == province_filter]
    if city_filter != "All":
        filtered = filtered[filtered["city"] == city_filter]
    if status_filter != "All":
        filtered = filtered[filtered["status"] == status_filter]
    if keyword_filter != "All" and "keywords_list" in filtered.columns:
        filtered = filtered[
            filtered["keywords_list"].apply(
                lambda kws: keyword_filter in kws if isinstance(kws, list) else False
            )
        ]
    if search.strip():
        needle = search.strip().lower()
        filtered = filtered[
            filtered["title"].fillna("").str.lower().str.contains(needle, na=False)
            | filtered["summary"].fillna("").str.lower().str.contains(needle, na=False)
        ]
    if date_min and date_max and "collected_at" in filtered.columns:
        collected = pd.to_datetime(filtered["collected_at"], utc=True, errors="coerce")
        filtered = filtered[
            (collected.dt.date >= date_min) & (collected.dt.date <= date_max)
        ]

    st.caption(f"Showing {len(filtered)} of {len(df)} items")
    return filtered


def render_raw_news_cards(df: pd.DataFrame) -> None:
    if df.empty:
        return

    for _, row in df.iterrows():
        url = row.get("url") or ""
        url_html = (
            f'<a href="{url}" target="_blank" rel="noopener noreferrer">Open source ↗</a>'
            if url
            else "—"
        )
        st.markdown(
            f"""
            <div class="item-card">
                <div class="item-card-title">{row.get('title') or 'Untitled'}</div>
                <div>{source_tag_html(row.get('source_name'))} {status_badge_html(row.get('status'))}</div>
                <div class="item-meta"><strong>Location:</strong> {row.get('city') or '—'}, {row.get('province') or '—'}</div>
                <div class="item-meta"><strong>Published:</strong> {format_datetime(row.get('published_at'))}</div>
                <div class="item-meta"><strong>Collected:</strong> {format_datetime(row.get('collected_at'))}</div>
                <div class="item-meta"><strong>Keywords:</strong> {row.get('keywords') or '—'}</div>
                <div class="item-meta"><strong>URL:</strong> {url_html}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_incident_card(incident: dict[str, Any]) -> None:
    score = float(incident.get("confidence_score") or 0)
    bar_width = min(max(score, 0), 100)
    location = ", ".join(
        p for p in [incident.get("city"), incident.get("province")] if p
    ) or "—"

    st.markdown(
        f"""
        <div class="item-card">
            <div class="item-card-title">{incident.get('main_title') or 'Untitled incident'}</div>
            <div style="margin-bottom: 0.5rem;">{status_badge_html(incident.get('status'))}</div>
            <div class="item-meta"><strong>Location:</strong> {location}</div>
            <div class="item-meta"><strong>Event type:</strong> {incident.get('event_type') or '—'}</div>
            <div class="item-meta"><strong>Matched sources:</strong> {incident.get('matched_sources') or '—'}</div>
            <div class="item-meta"><strong>Keywords:</strong> {incident.get('keywords') or '—'}</div>
            <div class="item-meta"><strong>Event date:</strong> {format_datetime(incident.get('event_at'))}</div>
            <div class="item-meta"><strong>Grouped:</strong> {format_datetime(incident.get('created_at'))}</div>
            <div class="item-meta"><strong>Confidence:</strong> {score:.2f}%</div>
            <div class="confidence-bar-wrap">
                <div class="confidence-bar-fill" style="width: {bar_width}%;"></div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_draft_card(
    draft: dict[str, Any],
    x_posting_enabled: bool,
    base_url: str,
    on_action,
) -> None:
    draft_id = draft.get("id")
    status = draft.get("status", "pending")

    st.markdown(
        f"""
        <div class="item-card">
            <div style="margin-bottom: 0.5rem;">{status_badge_html(status)}</div>
            <div class="draft-text">{draft.get('post_text') or ''}</div>
            <div class="item-meta"><strong>Keywords:</strong> {draft.get('keywords') or '—'}</div>
            <div class="item-meta"><strong>Confidence:</strong> {float(draft.get('confidence_score') or 0):.2f}%</div>
            <div class="item-meta"><strong>Created:</strong> {format_datetime(draft.get('created_at'))}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if status in ("approved", "rejected", "posted"):
        return

    c1, c2, c3 = st.columns([1, 1, 2])
    with c1:
        if st.button("Approve", key=f"approve_{draft_id}", type="primary"):
            on_action("approve", draft_id)
    with c2:
        if st.button("Reject", key=f"reject_{draft_id}"):
            on_action("reject", draft_id)
    with c3:
        if x_posting_enabled:
            if st.button("Post to X", key=f"post_{draft_id}"):
                on_action("post", draft_id)
        else:
            st.markdown(
                '<div class="info-box">X posting is disabled for safety. Enable it later from .env.</div>',
                unsafe_allow_html=True,
            )


def render_system_status(
    health: dict[str, Any],
    base_url: str,
    metrics: dict[str, Any],
    raw_df: pd.DataFrame,
    last_refresh: str,
) -> None:
    connected = health.get("ok", False)
    data = health.get("data") or {}

    status_class = "status-connected" if connected else "status-disconnected"
    status_text = "Backend connected" if connected else "Backend not connected"

    st.markdown(
        f"""
        <div class="item-card">
            <div class="item-meta"><strong>Backend status:</strong>
                <span class="status-pill {status_class}">{status_text}</span>
            </div>
            <div class="item-meta"><strong>API URL:</strong> {base_url}</div>
            <div class="item-meta"><strong>App:</strong> {data.get('app', '—')}</div>
            <div class="item-meta"><strong>Environment:</strong> {data.get('env', '—')}</div>
            <div class="item-meta"><strong>Database:</strong> {(data.get('database') or {}).get('backend', '—')} · {'connected' if (data.get('database') or {}).get('connected') else 'disconnected'}</div>
            <div class="item-meta"><strong>Supabase:</strong> {'active' if (data.get('database') or {}).get('using_supabase') else 'not configured'}</div>
            <div class="item-meta"><strong>Last refresh:</strong> {last_refresh}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns(3)
    with c1:
        render_kpi_card("Raw news", metrics["total_raw"])
    with c2:
        render_kpi_card("Incidents", metrics["total_incidents"])
    with c3:
        render_kpi_card("Drafts", metrics["total_drafts"])

    x_enabled = data.get("x_posting_enabled", False)
    x_conn = data.get("x_connection") or {}
    if x_conn.get("ok"):
        username = x_conn.get("username", "—")
        mode = x_conn.get("mode", "unknown")
        st.markdown(
            f'<div class="info-box"><strong>X API connected</strong> (@{username}, {mode}). '
            f'Posting {"enabled" if x_enabled else "disabled — set X_POSTING_ENABLED=true to allow draft posts"}.</div>',
            unsafe_allow_html=True,
        )
    elif data.get("x_configured") and x_conn.get("error"):
        st.markdown(
            f'<div class="error-box"><strong>X API error:</strong> {x_conn.get("error")}</div>',
            unsafe_allow_html=True,
        )
    elif x_enabled:
        st.markdown(
            '<div class="warn-box"><strong>X posting is enabled.</strong> Use with caution — drafts still require human approval before posting.</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div class="info-box"><strong>X posting is disabled.</strong> Set <code>X_POSTING_ENABLED=true</code> in .env to enable later.</div>',
            unsafe_allow_html=True,
        )

    scweet = data.get("scweet") or {}
    if scweet.get("enabled") and scweet.get("configured"):
        st.markdown(
            '<div class="info-box"><strong>Scweet (X search) enabled.</strong> '
            "Tweets are collected during Run Collection Now when queries match Pakistan/security filters.</div>",
            unsafe_allow_html=True,
        )
    elif scweet.get("enabled"):
        st.markdown(
            '<div class="warn-box"><strong>Scweet enabled but not configured.</strong> '
            "Set <code>SCWEET_USERNAME</code> and <code>SCWEET_PASSWORD</code> in .env, "
            "then use the <strong>X / Scweet</strong> tab to connect.</div>",
            unsafe_allow_html=True,
        )

    db_info = data.get("database") or {}
    supabase_info = data.get("supabase") or {}
    if db_info.get("using_supabase"):
        if db_info.get("connected"):
            st.markdown(
                '<div class="info-box"><strong>Supabase PostgreSQL connected.</strong> Raw news, incidents, and drafts are persisted in your Supabase project.</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f'<div class="error-box"><strong>Supabase database error:</strong> {db_info.get("error", "Connection failed")}</div>',
                unsafe_allow_html=True,
            )
    elif connected:
        st.markdown(
            '<div class="info-box"><strong>Using local SQLite.</strong> Set <code>SUPABASE_DB_URL</code> in .env to persist data in Supabase.</div>',
            unsafe_allow_html=True,
        )

    if supabase_info.get("configured") and supabase_info.get("api_ok") is False:
        st.markdown(
            f'<div class="warn-box"><strong>Supabase REST API:</strong> {supabase_info.get("api_error", "Unavailable")}</div>',
            unsafe_allow_html=True,
        )

    warnings: list[str] = []
    if connected and not data.get("acled_configured", False):
        warnings.append("ACLED credentials are not configured — ACLED collection is skipped.")

    if not raw_df.empty and "source_name" in raw_df.columns:
        present = set(raw_df["source_name"].dropna().unique())
        if "ReliefWeb" not in present:
            warnings.append(
                "No ReliefWeb items found — check RELIEFWEB_APPNAME in .env (pre-approved appname required)."
            )
        if "ACLED" not in present and not data.get("acled_configured", False):
            pass  # already warned above
        elif "ACLED" not in present and data.get("acled_configured", False):
            warnings.append("ACLED is configured but no ACLED items collected yet.")
    elif connected:
        warnings.append(
            "No data collected yet — run collection to verify GDELT, ReliefWeb, and ACLED sources."
        )

    if warnings:
        st.markdown('<div class="section-title">Configuration notes</div>', unsafe_allow_html=True)
        for warning in warnings:
            st.markdown(f'<div class="warn-box">{warning}</div>', unsafe_allow_html=True)

    if not connected and health.get("error"):
        st.markdown(
            f'<div class="error-box">Connection error: {health["error"]}</div>',
            unsafe_allow_html=True,
        )

    st.markdown('<div class="section-title">Expected sources</div>', unsafe_allow_html=True)
    for source in EXPECTED_SOURCES:
        active = (
            not raw_df.empty
            and "source_name" in raw_df.columns
            and source in raw_df["source_name"].values
        )
        badge = status_badge_html("ready_for_review" if active else "save_only")
        label = "Receiving data" if active else "No data yet"
        st.markdown(
            f'<div class="item-meta">{source_tag_html(source)} {badge} — {label}</div>',
            unsafe_allow_html=True,
        )
