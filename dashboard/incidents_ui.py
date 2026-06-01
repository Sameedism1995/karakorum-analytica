"""Incidents tab with keyword, date, and location filters."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import streamlit as st

from app.services.incident_filter import (
    IncidentFilterCriteria,
    collect_location_options,
    filter_incidents,
)
from dashboard.ui_components import render_incident_card
from dashboard.widget_state import prepare_widgets, schedule_widget_resets


def _default_date_range() -> tuple[date, date]:
    today = date.today()
    return today - timedelta(days=30), today


def render_incidents_tab(
    incident_items: list[dict[str, Any]],
    *,
    health_ok: bool,
) -> None:
    st.markdown('<div class="section-title">Grouped incidents</div>', unsafe_allow_html=True)
    st.caption(
        "Incidents are grouped from raw news. Filter by keyword, reported event date, or location."
    )

    if not health_ok:
        st.warning("Backend unavailable — incidents cannot be loaded.")
        return

    if not incident_items:
        st.info(
            "No incidents yet. Use **Re-run full ingestion pipeline** in the sidebar "
            "to collect and group matching reports."
        )
        return

    location_options = ["All locations"] + collect_location_options(incident_items)
    date_from_default, date_to_default = _default_date_range()

    prepare_widgets(
        {
            "incidents_filter_keyword": "",
            "incidents_use_date_filter": False,
            "incidents_filter_location": "All locations",
            "incidents_filter_date_from": date_from_default,
            "incidents_filter_date_to": date_to_default,
        }
    )

    with st.expander("Filters", expanded=True):
        f1, f2, f3 = st.columns([2, 2, 2])
        with f1:
            keyword = st.text_input(
                "Keyword",
                placeholder="e.g. blast Karachi militant",
                help="Matches title, keywords, event type, sources, and location fields.",
                key="incidents_filter_keyword",
            )
        with f2:
            use_date_filter = st.checkbox(
                "Filter by date",
                value=False,
                key="incidents_use_date_filter",
            )
            d1, d2 = st.columns(2)
            with d1:
                date_from = st.date_input(
                    "From",
                    value=date_from_default,
                    disabled=not use_date_filter,
                    key="incidents_filter_date_from",
                )
            with d2:
                date_to = st.date_input(
                    "To",
                    value=date_to_default,
                    disabled=not use_date_filter,
                    key="incidents_filter_date_to",
                )
        with f3:
            location = st.selectbox(
                "Location",
                location_options,
                index=0,
                key="incidents_filter_location",
            )

        if st.button("Clear filters", key="incidents_clear_filters"):
            schedule_widget_resets(
                {
                    "incidents_filter_keyword": "",
                    "incidents_use_date_filter": False,
                    "incidents_filter_location": "All locations",
                    "incidents_filter_date_from": date_from_default,
                    "incidents_filter_date_to": date_to_default,
                }
            )
            st.rerun()

    criteria = IncidentFilterCriteria(
        keyword=keyword.strip(),
        date_from=date_from if use_date_filter else None,
        date_to=date_to if use_date_filter else None,
        location="" if location == "All locations" else location,
    )

    if use_date_filter and date_from > date_to:
        st.error("Date range invalid: **From** must be on or before **To**.")
        return

    filtered = filter_incidents(incident_items, criteria)
    st.markdown(
        f"**Showing {len(filtered)} of {len(incident_items)}** incident(s)"
        + (
            f" · keyword `{criteria.keyword}`"
            if criteria.keyword
            else ""
        )
        + (
            f" · {criteria.date_from} → {criteria.date_to}"
            if use_date_filter
            else ""
        )
        + (
            f" · {criteria.location}"
            if criteria.location
            else ""
        )
    )

    if not filtered:
        st.warning("No incidents match the current filters. Try clearing filters or widening the date range.")
        return

    for incident in filtered:
        render_incident_card(incident)
