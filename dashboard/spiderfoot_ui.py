"""SpiderFoot OSINT explorer tab for Karakorum Analytica."""

from __future__ import annotations

from types import ModuleType
from typing import Any

import pandas as pd
import streamlit as st

USECASE_OPTIONS = ["passive", "investigate", "footprint", "all"]
RUNNING_STATUSES = {"RUNNING", "STARTING", "STARTED", "INITIALIZING", "ABORT-REQUESTED"}


def _status_pill(ok: bool, label_ok: str, label_bad: str) -> str:
    css = "status-connected" if ok else "status-disconnected"
    label = label_ok if ok else label_bad
    return f'<span class="status-pill {css}">{label}</span>'


def _render_status_cards(sf: dict[str, Any]) -> None:
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown("**Enabled**")
        st.markdown(_status_pill(sf.get("enabled"), "Yes", "No"), unsafe_allow_html=True)
    with c2:
        st.markdown("**Installed**")
        st.markdown(_status_pill(sf.get("installed"), "Yes", "No"), unsafe_allow_html=True)
    with c3:
        st.markdown("**Web server**")
        st.markdown(_status_pill(sf.get("reachable"), "Online", "Offline"), unsafe_allow_html=True)
    with c4:
        st.markdown("**Default mode**")
        st.caption(sf.get("default_usecase") or "passive")


def _render_new_scan(backend: ModuleType, base_url: str, *, health_ok: bool) -> None:
    st.markdown("**Start a new OSINT scan**")
    st.caption(
        "Targets: domain, IP, e-mail, phone, username, subnet, etc. "
        "Use **passive** on production (no active probing)."
    )

    with st.form("spiderfoot_new_scan"):
        c1, c2 = st.columns(2)
        with c1:
            scan_name = st.text_input("Scan name", placeholder="Pakistan domain footprint")
        with c2:
            usecase = st.selectbox("Module group", USECASE_OPTIONS, index=0)
        target = st.text_input("Target", placeholder="example.com or 203.0.113.1 or user@domain.com")
        with st.expander("Advanced module selection"):
            module_list = st.text_input("Module list (comma-separated)", help="Leave blank to use module group")
            type_list = st.text_input("Event types (comma-separated)", help="Optional — filter by output types")
        submitted = st.form_submit_button("Start scan", type="primary", disabled=not health_ok)

    if submitted:
        if not target.strip():
            st.warning("Enter a scan target.")
            return
        with st.spinner("Starting SpiderFoot scan…"):
            result = backend.start_spiderfoot_scan(
                base_url,
                scan_name=scan_name.strip(),
                target=target.strip(),
                usecase=usecase,
                module_list=module_list.strip(),
                type_list=type_list.strip(),
            )
        if result.get("ok"):
            scan_id = result.get("scan_id")
            st.success(f"Scan started — ID **{scan_id}**")
            st.session_state["spiderfoot_selected_scan"] = scan_id
            st.rerun()
        else:
            st.error(result.get("error") or "Failed to start scan.")


def _scan_rows(scans: list[dict[str, Any]]) -> pd.DataFrame:
    if not scans:
        return pd.DataFrame()
    rows = []
    for scan in scans:
        risk = scan.get("risk") or {}
        rows.append(
            {
                "ID": scan.get("id"),
                "Name": scan.get("name"),
                "Target": scan.get("target"),
                "Status": scan.get("status"),
                "Created": scan.get("created"),
                "Started": scan.get("started"),
                "Finished": scan.get("finished"),
                "Elements": scan.get("elements"),
                "High": risk.get("HIGH", 0),
                "Medium": risk.get("MEDIUM", 0),
                "Low": risk.get("LOW", 0),
            }
        )
    return pd.DataFrame(rows)


def _render_scan_list(backend: ModuleType, base_url: str) -> None:
    payload = backend.list_spiderfoot_scans(base_url)
    if not payload.get("ok"):
        st.error(payload.get("error") or "Could not load scans.")
        return

    scans = payload.get("scans") or []
    st.metric("Total scans", payload.get("count", len(scans)))

    if not scans:
        st.info("No scans yet. Start one from the **New scan** tab.")
        return

    df = _scan_rows(scans)
    st.dataframe(df, use_container_width=True, hide_index=True)

    running = [s for s in scans if str(s.get("status", "")).upper() in RUNNING_STATUSES]
    if running:
        st.info(f"{len(running)} scan(s) still running — refresh to update status.")

    st.markdown("**Manage scan**")
    options = {f"{s.get('name')} ({s.get('id')})": s.get("id") for s in scans}
    selected_label = st.selectbox("Select scan", list(options.keys()), key="spiderfoot_scan_picker")
    scan_id = options.get(selected_label, "")

    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("View results", use_container_width=True, key="sf_view_results"):
            st.session_state["spiderfoot_selected_scan"] = scan_id
            st.rerun()
    with c2:
        if st.button("Stop scan", use_container_width=True, key="sf_stop_scan"):
            result = backend.stop_spiderfoot_scan(base_url, scan_id)
            if result.get("ok"):
                st.success("Stop requested.")
                st.rerun()
            else:
                st.error(result.get("error") or "Stop failed.")
    with c3:
        if st.button("Delete scan", use_container_width=True, key="sf_delete_scan"):
            result = backend.delete_spiderfoot_scan(base_url, scan_id)
            if result.get("ok"):
                st.success("Scan deleted.")
                if st.session_state.get("spiderfoot_selected_scan") == scan_id:
                    st.session_state.pop("spiderfoot_selected_scan", None)
                st.rerun()
            else:
                st.error(result.get("error") or "Delete failed.")


def _render_scan_results(backend: ModuleType, base_url: str) -> None:
    scan_id = st.session_state.get("spiderfoot_selected_scan", "")
    manual_id = st.text_input("Scan ID", value=scan_id, key="spiderfoot_results_scan_id")
    if manual_id:
        scan_id = manual_id.strip()

    if not scan_id:
        st.info("Select a scan from **Scan list** or enter a scan ID.")
        return

    detail = backend.get_spiderfoot_scan(base_url, scan_id)
    if not detail.get("ok"):
        st.error(detail.get("error") or "Scan not found.")
        return

    scan = detail.get("scan") or {}
    st.markdown(f"### {scan.get('name') or 'Scan'} — `{scan.get('id')}`")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Status", scan.get("status") or "—")
    m2.metric("Created", scan.get("created") or "—")
    m3.metric("Started", scan.get("started") or "—")
    m4.metric("Finished", scan.get("finished") or "—")

    summary = detail.get("summary") or []
    if summary:
        st.markdown("**Results by type**")
        summary_df = pd.DataFrame(summary)
        st.dataframe(summary_df, use_container_width=True, hide_index=True)

    c1, c2, c3 = st.columns(3)
    with c1:
        event_type = st.text_input("Filter event type", placeholder="e.g. EMAILADDR, DOMAIN_NAME")
    with c2:
        unique_only = st.checkbox("Unique results only", value=False)
    with c3:
        limit = st.number_input("Max rows", min_value=50, max_value=5000, value=500, step=50)

    if st.button("Load results", type="primary", key="sf_load_results"):
        with st.spinner("Fetching scan results…"):
            results = backend.get_spiderfoot_scan_results(
                base_url,
                scan_id,
                event_type=event_type.strip(),
                unique=unique_only,
                limit=int(limit),
            )
        if not results.get("ok"):
            st.error(results.get("error") or "Could not load results.")
            return
        items = results.get("items") or []
        st.success(f"Loaded {results.get('count', len(items))} result(s).")
        if items:
            rows = [
                {
                    "type": item.get("type"),
                    "data": item.get("data"),
                    "module": item.get("module"),
                    "confidence": item.get("confidence"),
                    "risk": item.get("risk"),
                    "generated": item.get("generated"),
                }
                for item in items
            ]
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def _render_modules(backend: ModuleType, base_url: str) -> None:
    payload = backend.list_spiderfoot_modules(base_url)
    if not payload.get("ok"):
        st.error(payload.get("error") or "Could not load modules.")
        return
    modules = payload.get("modules") or []
    st.metric("Available modules", len(modules))
    if not modules:
        st.info("No module metadata returned.")
        return
    if isinstance(modules[0], list):
        df = pd.DataFrame(
            modules,
            columns=["name", "descr", "flags"][: len(modules[0])],
        )
    else:
        df = pd.DataFrame(modules)
    st.dataframe(df, use_container_width=True, hide_index=True)


def render_spiderfoot_tab(
    backend: ModuleType,
    base_url: str,
    *,
    health_ok: bool,
) -> None:
    """Render SpiderFoot OSINT tab."""
    st.markdown('<div class="section-title">SpiderFoot OSINT</div>', unsafe_allow_html=True)
    st.caption("Automated footprinting — domains, IPs, e-mails, usernames, and more.")

    sf_resp = backend.get_spiderfoot_status(base_url)
    sf = (sf_resp.get("data") or {}).get("spiderfoot") or sf_resp.get("spiderfoot") or {}

    _render_status_cards(sf)

    if not sf.get("enabled"):
        st.warning("SpiderFoot is disabled. Set **SPIDERFOOT_ENABLED=true** on the API service.")
        return
    if not sf.get("installed"):
        st.error(f"SpiderFoot is not installed at `{sf.get('dir')}`. Run the API build script to clone it.")
        return
    if not sf.get("reachable"):
        st.error(sf.get("error") or "SpiderFoot web server is not reachable.")
        st.info(
            "Locally: `cd third_party/spiderfoot && ./venv/bin/python sf.py -l 127.0.0.1:5001`\n\n"
            "On Render: the API start script auto-starts SpiderFoot when **SPIDERFOOT_AUTOSTART=true**."
        )
        return

    tab_new, tab_list, tab_results, tab_modules = st.tabs(
        ["New scan", "Scan list", "Results", "Modules"]
    )
    with tab_new:
        _render_new_scan(backend, base_url, health_ok=health_ok)
    with tab_list:
        _render_scan_list(backend, base_url)
    with tab_results:
        _render_scan_results(backend, base_url)
    with tab_modules:
        _render_modules(backend, base_url)
