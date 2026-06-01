"""Detect server/CI environments and safe Playwright launch settings."""

from __future__ import annotations

import os
import sys

from app.config import get_settings


def is_server_runtime() -> bool:
    """True on Render, CI, or when APP_ENV/ENVIRONMENT is production."""
    if os.environ.get("RENDER"):
        return True
    if os.environ.get("CI", "").lower() in {"1", "true", "yes"}:
        return True
    settings = get_settings()
    return settings.is_production


def playwright_login_allowed() -> bool:
    """Playwright X login is local-dev only; production uses SCWEET_AUTH_TOKEN."""
    settings = get_settings()
    if is_server_runtime():
        return False
    return settings.scweet_auto_login


def playwright_login_blocked_message() -> str:
    return (
        "Playwright X login is not available on Render/production. "
        "Set SCWEET_AUTH_TOKEN on the service — from your machine run: "
        "python scripts/sync_scweet_token_to_render.py --deploy --write-env"
    )


def effective_playwright_headless(requested: bool | None = None) -> bool:
    """
    Resolve headless mode for Playwright.

    Headed browsers require a display. On Linux servers without $DISPLAY (Render, CI),
    always force headless=True even if SCWEET_LOGIN_HEADLESS=false.
    """
    settings = get_settings()
    headless = settings.scweet_login_headless if requested is None else requested

    if is_server_runtime():
        return True

    # Linux without X11/Wayland cannot launch headed Chromium
    if sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
        return True

    return headless
