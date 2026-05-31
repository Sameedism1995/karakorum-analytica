"""Karakorum Analytica logo and brand assets."""

from __future__ import annotations

import base64
from pathlib import Path

import streamlit as st

ASSETS_DIR = Path(__file__).resolve().parent / "assets"
LOGO_PATH = ASSETS_DIR / "logo.png"
BRAND_NAME = "Karakorum Analytica"
LOGO_ALT = BRAND_NAME


def _logo_mime(data: bytes) -> str:
    if data[:2] == b"\xff\xd8":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    return "image/png"


def logo_data_uri() -> str:
    raw = LOGO_PATH.read_bytes()
    encoded = base64.b64encode(raw).decode("ascii")
    return f"data:{_logo_mime(raw)};base64,{encoded}"


def inject_brand_title() -> None:
    """Force browser tab title (Streamlit Cloud may override page_title)."""
    import streamlit.components.v1 as components

    components.html(
        f"<script>document.title = {BRAND_NAME!r};</script>",
        height=0,
        width=0,
    )


def render_sidebar_logo() -> None:
    st.markdown(
        f"""
        <div class="sidebar-logo-wrap">
            <img src="{logo_data_uri()}" alt="{LOGO_ALT}" class="sidebar-logo" />
        </div>
        """,
        unsafe_allow_html=True,
    )
