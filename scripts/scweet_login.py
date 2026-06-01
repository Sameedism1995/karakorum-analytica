#!/usr/bin/env python3
"""Log into X with SCWEET_USERNAME/SCWEET_PASSWORD and cache session for Scweet."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from app.config import get_settings
from app.integrations.scweet_client import (
    _scweet_login_id,
    build_scweet_client,
    resolve_scweet_auth_token,
    scweet_settings_summary,
)
from app.integrations.x_session_login import get_or_create_x_session


def main() -> int:
    settings = get_settings()
    print(json.dumps(scweet_settings_summary(), indent=2))

    login = _scweet_login_id(settings)
    password = settings.scweet_password.strip()
    if not login or not password:
        print("Set SCWEET_USERNAME (or SCWEET_EMAIL) and SCWEET_PASSWORD in .env")
        return 1

    verification = settings.scweet_email.strip() or None
    if verification == login:
        verification = None

    try:
        get_or_create_x_session(
            login,
            password,
            verification_handle=verification,
            cache_path=settings.scweet_session_cache_path,
            headless=settings.scweet_login_headless,
            force_refresh="--refresh" in sys.argv,
        )
        print("Session OK — auth_token captured (cached, not printed)")
        token = resolve_scweet_auth_token()
        if not token:
            print("Failed to resolve auth token after login")
            return 1
        build_scweet_client()
        print("Scweet client OK")
        return 0
    except Exception as exc:
        print(f"Login failed: {exc}")
        print("Tip: set SCWEET_LOGIN_HEADLESS=false to complete verification in a visible browser.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
