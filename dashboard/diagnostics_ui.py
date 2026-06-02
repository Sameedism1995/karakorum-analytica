"""System diagnostics — Ollama, Buffer, Supabase, pipeline tests."""

from __future__ import annotations

import os
from types import ModuleType
from typing import Any

import streamlit as st


def render_pipeline_diagnostics(backend: ModuleType, base_url: str, *, health: dict[str, Any]) -> None:
    st.markdown("### Pipeline diagnostics")
    st.caption(
        "Local Ollama runs on **your Mac** only. The Render API cannot reach `localhost:11434` on your machine."
    )

    ollama = backend.get_ollama_health(base_url)
    buffer = backend.get_buffer_health(base_url)
    supabase = backend.get_supabase_health(base_url)

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("**Ollama**")
        if ollama.get("ok"):
            data = ollama.get("data") or {}
            if data.get("server_reachable") and data.get("model_available"):
                st.success(f"Ready · {data.get('model', '')}")
            elif data.get("enabled"):
                st.error(data.get("error") or "Not reachable")
            else:
                st.warning("Disabled")
            if data.get("production_warning"):
                st.warning(data["production_warning"])
        else:
            st.error(ollama.get("error") or "Health check failed")

    with c2:
        st.markdown("**Buffer / @kkanalytica**")
        if buffer.get("ok"):
            data = buffer.get("data") or {}
            if data.get("api_key_configured") and data.get("channel_found"):
                st.success(f"Connected · channel {str(data.get('channel_id', ''))[:12]}…")
            elif data.get("api_key_configured"):
                st.error(data.get("error") or "Channel not found")
            else:
                st.warning("BUFFER_API_KEY not configured on API")
        else:
            st.error(buffer.get("error") or "Buffer health failed")

    with c3:
        st.markdown("**Supabase**")
        if supabase.get("ok"):
            data = supabase.get("data") or {}
            if data.get("connected"):
                st.success(f"Connected · {data.get('backend', 'postgres')}")
            else:
                st.error(data.get("error") or "Database disconnected")
        else:
            st.error(supabase.get("error") or "Supabase check failed")

    st.markdown("---")
    b1, b2, b3 = st.columns(3)
    with b1:
        if st.button("Test local draft", key="diag_test_draft"):
            payload = {
                "raw_text": "Initial reports suggest security activity near Quetta. Local sources claim an incident.",
                "source_name": "Diagnostics test",
                "source_url": "https://example.com/test",
                "location": "Quetta, Pakistan",
                "category": "conflict/security",
                "verification_status": "unverified",
                "source_grade": "C",
                "save": True,
            }
            with st.spinner("Drafting with Ollama…"):
                result = backend.draft_local_post(base_url, payload)
            if result.get("ok"):
                data = result.get("data") or {}
                st.success(f"Draft saved — post #{data.get('post_id')} · {data.get('status')}")
                st.code((data.get("post_text") or "")[:280])
            else:
                st.error(result.get("error") or "Draft failed")

    with b2:
        if st.button("Dry-run E2E pipeline", key="diag_e2e_dry"):
            with st.spinner("Running dry-run pipeline…"):
                result = backend.run_e2e_pipeline(base_url, dry_run=True)
            if result.get("ok"):
                st.success(result.get("message") or "Dry run OK")
            else:
                st.error(result.get("error") or "Dry run failed")
            steps = result.get("steps") or result.get("data", {}).get("steps")
            if steps:
                st.json(steps)

    with b3:
        secret = os.environ.get("ADMIN_TEST_SECRET") or os.environ.get("BUFFER_TEST_SECRET", "")
        if st.button("Live E2E → Buffer", key="diag_e2e_live", type="primary"):
            if not secret:
                st.warning("Set ADMIN_TEST_SECRET or BUFFER_TEST_SECRET locally to run live E2E.")
            else:
                with st.spinner("Running live pipeline (posts to Buffer)…"):
                    result = backend.run_e2e_pipeline(base_url, dry_run=False, admin_secret=secret)
                if result.get("ok"):
                    st.success(result.get("message") or "Sent to Buffer")
                else:
                    st.error(result.get("error") or "Live E2E failed")
