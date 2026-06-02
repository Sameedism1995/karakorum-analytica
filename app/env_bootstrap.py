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

    is_render = bool(os.environ.get("RENDER"))
    is_prod = os.environ.get("ENVIRONMENT", "").lower() in {"production", "prod"} or os.environ.get(
        "APP_ENV", ""
    ).lower() in {"production", "prod"}

    # Production / Render: never default to Playwright login on the server
    if os.environ.get("SCWEET_AUTH_TOKEN", "").strip():
        os.environ["SCWEET_AUTO_LOGIN"] = "false"
    elif is_render or is_prod:
        os.environ["SCWEET_AUTO_LOGIN"] = "false"
    elif not os.environ.get("SCWEET_AUTO_LOGIN"):
        os.environ["SCWEET_AUTO_LOGIN"] = "true"

    if not os.environ.get("SCWEET_LOGIN_HEADLESS"):
        is_prod = os.environ.get("ENVIRONMENT", "").lower() in {"production", "prod"} or os.environ.get(
            "APP_ENV", ""
        ).lower() in {"production", "prod"}
        is_render = bool(os.environ.get("RENDER"))
        is_ci = os.environ.get("CI", "").lower() in {"1", "true", "yes"}
        # Servers have no display — default headless; local dev defaults to visible browser
        os.environ["SCWEET_LOGIN_HEADLESS"] = "true" if (is_prod or is_render or is_ci) else "false"

    if not os.environ.get("SCWEET_SESSION_CACHE_PATH"):
        os.environ["SCWEET_SESSION_CACHE_PATH"] = "data/scweet_session.json"

    if not os.environ.get("SCWEET_DB_PATH"):
        os.environ["SCWEET_DB_PATH"] = "data/scweet_state.db"

    # Local Ollama: default on for developer machines (not Render/production servers)
    if not os.environ.get("LOCAL_LLM_ENABLED"):
        if not is_render and not is_prod:
            os.environ["LOCAL_LLM_ENABLED"] = "true"

    if not os.environ.get("LOCAL_LLM_BASE_URL"):
        os.environ["LOCAL_LLM_BASE_URL"] = "http://localhost:11434"

    if not os.environ.get("LOCAL_LLM_MODEL"):
        os.environ["LOCAL_LLM_MODEL"] = "qwen3:4b"
