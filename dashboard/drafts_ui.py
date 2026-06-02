"""Draft posts & LLM newsroom tab."""

from __future__ import annotations

from types import ModuleType
from typing import Any

import streamlit as st

from dashboard.ui_components import format_datetime, status_badge_html
from dashboard.widget_state import prepare_widgets

TONE_OPTIONS = ["neutral", "urgent", "detailed", "short"]
STATUS_FILTERS = ["All", "pending", "approved", "rejected", "posted"]
RISK_COLORS = {
    "safe_to_publish": "#22c55e",
    "publish_with_caution": "#eab308",
    "needs_verification": "#f97316",
    "do_not_publish": "#ef4444",
}


def _char_meter(text: str) -> str:
    n = len(text or "")
    color = "#22c55e" if n <= 260 else "#eab308" if n <= 280 else "#ef4444"
    return f'<span style="color:{color};font-weight:600;">{n}/280</span>'


def _llm_mode_badge(mode: str) -> str:
    if mode == "openai":
        return '<span class="status-pill status-connected">OpenAI</span>'
    if mode in {"local_ollama", "local_llm"}:
        return '<span class="status-pill status-connected">Local Ollama</span>'
    if mode == "local_ollama_unavailable":
        return '<span class="status-pill status-degraded">Ollama offline</span>'
    if mode in {"generated", "template"}:
        return '<span class="status-pill status-connected">Newsroom template</span>'
    return f'<span class="status-pill">{mode or "template"}</span>'


def _render_local_audit(audit: dict[str, Any]) -> None:
    if not audit:
        return
    rec = audit.get("publish_recommendation") or audit.get("publish_status", "")
    color = RISK_COLORS.get(rec, "#94a3b8")
    st.markdown(
        f'<div class="llm-audit-box" style="border-left:4px solid {color};">'
        f"<strong>Source grade:</strong> {audit.get('source_grade', '—')} · "
        f"<strong>Verification:</strong> {audit.get('verification_status', '—')} · "
        f"<strong>Recommendation:</strong> {rec or '—'}</div>",
        unsafe_allow_html=True,
    )
    flags = audit.get("risk_flags") or []
    if flags:
        st.warning("Risk flags: " + "; ".join(flags[:5]))
    notes = audit.get("editor_notes") or []
    if notes:
        st.caption("Editor notes:")
        for note in notes[:5]:
            st.write(f"• {note}")
    rewrite = audit.get("safer_rewrite") or audit.get("safer_rewritten_version")
    if rewrite:
        st.caption("Safer rewrite suggestion:")
        st.code(str(rewrite)[:280])


def _render_llm_status(backend: ModuleType, base_url: str) -> dict[str, Any]:
    resp = backend.get_llm_health(base_url)
    llm = (resp.get("data") or {}).get("llm") or resp.get("llm") or {}
    local = llm.get("local_llm") or {}
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown("**LLM provider**")
        st.caption(llm.get("provider") or "placeholder")
    with c2:
        st.markdown("**Model**")
        st.caption(llm.get("model") or "template-v1")
    with c3:
        st.markdown("**Mode**")
        st.markdown(_llm_mode_badge(llm.get("mode", "template")), unsafe_allow_html=True)
    with c4:
        st.markdown("**Local Ollama**")
        if llm.get("local_llm_enabled"):
            if local.get("reachable") and local.get("model_ready"):
                st.caption(f"Ready · {local.get('model', '')}")
            else:
                st.caption(local.get("error") or "Not reachable")
        else:
            st.caption("Disabled")
    if llm.get("local_llm_enabled"):
        if local.get("reachable") and local.get("model_ready"):
            st.success(
                "Local Ollama is active — drafts use on-device inference. "
                "Human approval required before publishing."
            )
        else:
            st.error(
                local.get("error")
                or "Ollama not running. Start with `ollama serve` and `ollama pull qwen3:4b`."
            )
    elif not llm.get("openai_configured"):
        st.info(
            "Using **template newsroom** (no OpenAI key). Set `LOCAL_LLM_ENABLED=true` for Ollama, "
            "or `LLM_PROVIDER=openai` + `OPENAI_API_KEY` for cloud inference."
        )
    else:
        st.success("OpenAI is configured — regenerate and studio use live LLM inference.")
    return llm


def _incident_map(incidents: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    return {int(i["id"]): i for i in incidents if i.get("id") is not None}


def _filter_drafts(drafts: list[dict[str, Any]], status: str) -> list[dict[str, Any]]:
    if status == "All":
        return drafts
    return [d for d in drafts if d.get("status") == status]


def _render_draft_card(
    backend: ModuleType,
    base_url: str,
    draft: dict[str, Any],
    incident: dict[str, Any] | None,
    *,
    x_posting_enabled: bool,
) -> None:
    draft_id = draft.get("id")
    status = draft.get("status", "pending")
    post_text = draft.get("post_text") or ""
    incident_title = (incident or {}).get("main_title") or f"Incident #{draft.get('incident_id')}"
    location = ", ".join(
        p for p in [(incident or {}).get("city"), (incident or {}).get("province")] if p
    ) or "Pakistan"

    st.markdown(
        f"""
        <div class="item-card draft-card">
            <div class="draft-card-header">
                <div class="item-card-title">{incident_title}</div>
                <div>{status_badge_html(status)}</div>
            </div>
            <div class="item-meta"><strong>Location:</strong> {location} ·
            <strong>Confidence:</strong> {float(draft.get('confidence_score') or 0):.1f}% ·
            <strong>Chars:</strong> {_char_meter(post_text)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    edit_key = f"draft_edit_{draft_id}"
    prepare_widgets({edit_key: post_text})
    edited = st.text_area(
        "X post draft",
        height=120,
        key=edit_key,
        label_visibility="collapsed",
        disabled=status in ("posted", "rejected"),
    )

    if status not in ("posted", "rejected") and edited.strip() != post_text.strip():
        if st.button("Save edits", key=f"save_draft_{draft_id}"):
            result = backend.update_draft(base_url, draft_id, edited.strip())
            if result.get("ok"):
                st.success("Draft updated.")
                st.rerun()
            else:
                st.error(result.get("error") or "Could not save draft.")

    with st.expander("LLM tools", expanded=False):
        t1, t2 = st.columns(2)
        with t1:
            tone = st.selectbox("Tone", TONE_OPTIONS, key=f"tone_{draft_id}")
        with t2:
            if st.button("Regenerate with LLM", key=f"regen_{draft_id}"):
                with st.spinner("Regenerating…"):
                    result = backend.regenerate_draft(base_url, draft_id, tone=tone)
                if result.get("ok"):
                    mode = (result.get("llm") or {}).get("mode", "generated")
                    st.success(f"Regenerated ({mode}).")
                    st.rerun()
                else:
                    st.error(result.get("error") or "Regeneration failed.")

        raw_for_local = ""
        loc_for_local = location
        inc_type = (incident or {}).get("event_type") or "security incident"
        if incident:
            raw_for_local = "\n".join(
                filter(
                    None,
                    [
                        incident.get("main_title"),
                        f"Location: {location}",
                        f"Keywords: {incident.get('keywords')}",
                        f"Sources: {incident.get('matched_sources')}",
                    ],
                )
            )

        b1, b2 = st.columns(2)
        with b1:
            if st.button("Draft with Local LLM", key=f"local_draft_{draft_id}"):
                payload = {
                    "raw_text": raw_for_local or post_text,
                    "source_name": (incident or {}).get("matched_sources") or "open-source",
                    "source_type": (incident or {}).get("matched_sources") or "open-source",
                    "location": loc_for_local,
                    "incident_type": inc_type,
                }
                with st.spinner("Drafting with Ollama…"):
                    result = backend.draft_newsroom_post_local(base_url, payload)
                if result.get("ok"):
                    data = result.get("data") or {}
                    st.session_state[f"local_audit_{draft_id}"] = data
                    if data.get("post_text") and status not in ("posted", "rejected"):
                        backend.update_draft(base_url, draft_id, data["post_text"])
                    st.success(f"Local draft ready (RAG examples: {data.get('rag_examples_used', 0)}).")
                    st.rerun()
                else:
                    st.error(result.get("error") or "Local LLM draft failed.")
        with b2:
            if st.button("Run Source Audit", key=f"local_audit_{draft_id}"):
                payload = {
                    "raw_text": raw_for_local,
                    "post_text": edited.strip() or post_text,
                    "source_name": (incident or {}).get("matched_sources") or "",
                    "source_type": (incident or {}).get("matched_sources") or "",
                    "location": loc_for_local,
                    "incident_type": inc_type,
                }
                with st.spinner("Auditing with Ollama…"):
                    result = backend.audit_source_local(base_url, payload)
                if result.get("ok"):
                    st.session_state[f"local_audit_{draft_id}"] = result.get("data") or {}
                    st.rerun()
                else:
                    st.error(result.get("error") or "Source audit failed.")

        cached = st.session_state.get(f"local_audit_{draft_id}")
        if cached:
            _render_local_audit(cached)

        if st.button("Run editorial audit", key=f"audit_{draft_id}"):
            with st.spinner("Auditing…"):
                audit_resp = backend.audit_draft(base_url, draft_id)
            audit = (audit_resp.get("audit") or {}) if audit_resp.get("ok") else {}
            if audit:
                if audit.get("risk_score") is not None:
                    score = audit.get("risk_score", 0)
                    label = audit.get("publish_status_label", "")
                    color = RISK_COLORS.get(audit.get("publish_status", ""), "#94a3b8")
                    st.markdown(
                        f'<div class="llm-audit-box" style="border-left:4px solid {color};">'
                        f"<strong>Risk score:</strong> {score}/100 · {label}</div>",
                        unsafe_allow_html=True,
                    )
                else:
                    _render_local_audit(audit)
                if audit.get("unsupported_claims"):
                    st.warning("Unsupported: " + "; ".join(audit["unsupported_claims"][:3]))
            else:
                st.error(audit_resp.get("error") or "Audit failed.")

    if status in ("approved", "rejected", "posted"):
        if draft.get("posted_at"):
            st.caption(f"Posted {format_datetime(draft.get('posted_at'))}")
        return

    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("Approve", key=f"approve_{draft_id}", type="primary"):
            result = backend.approve_draft(draft_id, base_url)
            if result.get("ok"):
                st.success("Approved.")
                st.rerun()
            else:
                st.error(result.get("error") or "Approve failed.")
    with c2:
        if st.button("Reject", key=f"reject_{draft_id}"):
            result = backend.reject_draft(draft_id, base_url)
            if result.get("ok"):
                st.success("Rejected.")
                st.rerun()
            else:
                st.error(result.get("error") or "Reject failed.")
    with c3:
        if x_posting_enabled and status == "approved":
            if st.button("Post to X", key=f"post_{draft_id}"):
                result = backend.post_draft(draft_id, base_url)
                if result.get("ok"):
                    st.success("Posted to X.")
                    st.rerun()
                else:
                    st.error(result.get("error") or "Post failed.")
        elif not x_posting_enabled:
            st.caption("X posting disabled")


def _render_review_queue(
    backend: ModuleType,
    base_url: str,
    drafts: list[dict[str, Any]],
    incidents: list[dict[str, Any]],
    *,
    x_posting_enabled: bool,
) -> None:
    inc_map = _incident_map(incidents)
    status_filter = st.selectbox("Filter by status", STATUS_FILTERS, key="drafts_status_filter")
    filtered = _filter_drafts(drafts, status_filter)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total", len(drafts))
    m2.metric("Pending", sum(1 for d in drafts if d.get("status") == "pending"))
    m3.metric("Approved", sum(1 for d in drafts if d.get("status") == "approved"))
    m4.metric("Posted", sum(1 for d in drafts if d.get("status") == "posted"))

    if not filtered:
        st.info("No drafts in this filter.")
        return

    for draft in filtered:
        inc = inc_map.get(int(draft.get("incident_id") or 0))
        _render_draft_card(
            backend,
            base_url,
            draft,
            inc,
            x_posting_enabled=x_posting_enabled,
        )
        st.divider()


def _render_llm_studio(
    backend: ModuleType,
    base_url: str,
    incidents: list[dict[str, Any]],
) -> None:
    st.markdown("**Generate a new post** from an incident or custom text.")
    source = st.radio("Input source", ["From incident", "Custom text"], horizontal=True)

    raw_text = ""
    main_kw = ""
    region = ""
    city = ""

    if source == "From incident" and incidents:
        labels = {
            f"#{i['id']} — {(i.get('main_title') or 'Untitled')[:60]}": i for i in incidents
        }
        pick = st.selectbox("Incident", list(labels.keys()))
        inc = labels[pick]
        raw_text = "\n".join(
            filter(
                None,
                [
                    inc.get("main_title"),
                    f"Location: {inc.get('city')}, {inc.get('province')}",
                    f"Keywords: {inc.get('keywords')}",
                    f"Sources: {inc.get('matched_sources')}",
                ],
            )
        )
        kws = (inc.get("keywords") or "").split(",")
        main_kw = kws[0].strip() if kws else "security"
        region = inc.get("province") or ""
        city = inc.get("city") or ""
    else:
        raw_text = st.text_area("Incident / source text", height=120, placeholder="Paste verified OSINT summary…")
        main_kw = st.text_input("Main keyword", placeholder="e.g. Quetta blast")
        region = st.text_input("Region / province", value="Balochistan")
        city = st.text_input("City", value="")

    c1, c2, c3 = st.columns(3)
    with c1:
        tone = st.selectbox("Tone", TONE_OPTIONS, key="studio_tone")
    with c2:
        grade = st.selectbox("Source grade", ["A", "B", "C", "D", "E"], index=2)
    with c3:
        platform = st.selectbox("Platform", ["x", "website", "telegram", "instagram"])

    if st.button("Generate with LLM", type="primary", key="studio_generate"):
        payload = {
            "raw_incident_text": raw_text,
            "main_keyword": main_kw,
            "seo_keywords": main_kw,
            "region": region,
            "country": "Pakistan",
            "city_district": city,
            "source_reliability_grade": grade,
            "tone": tone,
            "platform": platform,
        }
        with st.spinner("Generating…"):
            result = backend.llm_generate_post(base_url, payload)
        if not result.get("ok") and result.get("error"):
            st.error(result.get("error"))
            return
        data = result.get("data") or result
        st.session_state["studio_last_output"] = data
        st.rerun()

    if st.button("Draft with Local LLM", key="studio_local_draft"):
        payload = {
            "raw_text": raw_text,
            "source_name": "manual input",
            "source_type": f"grade {grade}",
            "location": ", ".join(p for p in [city, region] if p) or "Pakistan",
            "incident_type": main_kw or "security incident",
        }
        with st.spinner("Drafting with Ollama…"):
            result = backend.draft_newsroom_post_local(base_url, payload)
        if result.get("ok"):
            data = result.get("data") or {}
            st.session_state["studio_last_output"] = {
                "mode": "local_llm",
                "short_x_post": data.get("post_text", ""),
                "seo_headline": data.get("headline", ""),
                "verification_warning": f"Verification: {data.get('verification_status', '')}",
                "local_audit": data,
            }
            st.rerun()
        else:
            st.error(result.get("error") or "Local LLM draft failed.")

    if st.button("Run Source Audit", key="studio_local_audit"):
        post = (st.session_state.get("studio_last_output") or {}).get("short_x_post", "")
        payload = {
            "raw_text": raw_text,
            "post_text": post or raw_text[:280],
            "source_type": f"grade {grade}",
            "location": ", ".join(p for p in [city, region] if p) or "Pakistan",
            "incident_type": main_kw or "security incident",
        }
        with st.spinner("Auditing…"):
            result = backend.audit_source_local(base_url, payload)
        if result.get("ok"):
            st.session_state["studio_local_audit"] = result.get("data") or {}
            st.rerun()
        else:
            st.error(result.get("error") or "Audit failed.")

    studio_audit = st.session_state.get("studio_local_audit")
    if studio_audit:
        _render_local_audit(studio_audit)

    output = st.session_state.get("studio_last_output")
    if output:
        st.markdown(f"**Mode:** {_llm_mode_badge(output.get('mode', 'generated'))}", unsafe_allow_html=True)
        if output.get("verification_warning"):
            st.warning(output["verification_warning"])
        st.markdown("#### X post")
        st.code((output.get("short_x_post") or "")[:280])
        st.markdown(f"Characters: {_char_meter(output.get('short_x_post', ''))}", unsafe_allow_html=True)
        with st.expander("Website / long form"):
            st.write(output.get("website_post") or "")
        with st.expander("SEO"):
            st.write(f"**Headline:** {output.get('seo_headline')}")
            st.write(f"**Meta:** {output.get('meta_description')}")
            st.write("**Hashtags:** " + " ".join(output.get("suggested_hashtags") or []))
        if st.button("Audit this draft", key="studio_audit"):
            audit = backend.llm_audit_post(
                base_url,
                draft_post=output.get("short_x_post", ""),
                raw_report=raw_text,
                source_information=f"Grade {grade}",
            )
            if audit.get("ok"):
                a = audit.get("data") or audit.get("audit") or {}
                st.json(a)
            else:
                st.error(audit.get("error") or "Audit failed.")


def render_drafts_tab(
    backend: ModuleType,
    base_url: str,
    *,
    health_ok: bool,
    draft_items: list[dict[str, Any]],
    incident_items: list[dict[str, Any]],
    x_posting_enabled: bool,
) -> None:
    st.markdown('<div class="section-title">LLM Newsroom & drafts</div>', unsafe_allow_html=True)
    st.caption(
        "AI-assisted X posts from incidents — human review required before publishing. "
        "Never auto-posts."
    )

    if not health_ok:
        st.warning("Backend unavailable — drafts cannot be loaded.")
        return

    _render_llm_status(backend, base_url)

    tab_queue, tab_studio = st.tabs(["Review queue", "LLM studio"])

    with tab_queue:
        if not draft_items:
            st.info(
                "No draft posts yet. Run **Re-run full ingestion pipeline** in the sidebar "
                "to collect incidents and auto-generate LLM drafts."
            )
        else:
            _render_review_queue(
                backend,
                base_url,
                draft_items,
                incident_items,
                x_posting_enabled=x_posting_enabled,
            )

    with tab_studio:
        _render_llm_studio(backend, base_url, incident_items)

    with st.expander("Fine-tuning export (LoRA/QLoRA)"):
        st.caption("Export human-approved examples as JSONL for future local model fine-tuning.")
        if st.button("Download training JSONL", key="export_training_jsonl"):
            result = backend.export_training_jsonl(base_url)
            if result.get("ok"):
                st.download_button(
                    "Save newsroom_training.jsonl",
                    data=result.get("content") or "",
                    file_name="newsroom_training.jsonl",
                    mime="application/x-ndjson",
                )
            else:
                st.error(result.get("error") or "Export failed.")
