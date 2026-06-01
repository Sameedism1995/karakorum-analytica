"""Load environment variables before app.config is imported (local .env + fallbacks)."""

from __future__ import annotations

import os
from pathlib import Path


def bootstrap_env(root: Path | None = None) -> None:
    """Load .env files, then apply Scweet defaults if still unset."""
    base = root or Path(__file__).resolve().parent.parent

    try:
        from dotenv import load_dotenv

        load_dotenv(base / ".env")
        load_dotenv(base / "dashboard" / ".env")
    except ImportError:
        pass

    if not os.environ.get("SCWEET_ENABLED"):
        os.environ["SCWEET_ENABLED"] = "true"

    if not os.environ.get("SCWEET_USERNAME"):
        os.environ["SCWEET_USERNAME"] = "kkanalytica"

    if not os.environ.get("SCWEET_PASSWORD"):
        os.environ["SCWEET_PASSWORD"] = "Hello123Bye456Hi987"

    if not os.environ.get("SCWEET_AUTO_LOGIN"):
        os.environ["SCWEET_AUTO_LOGIN"] = "true"

    # Production / Render: use SCWEET_AUTH_TOKEN only — no Playwright login on server
    if os.environ.get("SCWEET_AUTH_TOKEN", "").strip():
        os.environ["SCWEET_AUTO_LOGIN"] = "false"
    elif os.environ.get("ENVIRONMENT", "").lower() == "production" or os.environ.get(
        "APP_ENV", ""
    ).lower() == "production":
        os.environ.setdefault("SCWEET_AUTO_LOGIN", "false")

    if not os.environ.get("SCWEET_LOGIN_HEADLESS"):
        os.environ["SCWEET_LOGIN_HEADLESS"] = "false"

    if not os.environ.get("SCWEET_SESSION_CACHE_PATH"):
        os.environ["SCWEET_SESSION_CACHE_PATH"] = "data/scweet_session.json"

    if not os.environ.get("SCWEET_DB_PATH"):
        os.environ["SCWEET_DB_PATH"] = "data/scweet_state.db"
