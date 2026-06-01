"""Resolve SCWEET_AUTH_TOKEN from local env, session cache, or Scweet SQLite DB."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from loguru import logger

from app.config import get_settings
from app.integrations.x_session_login import load_cached_session


def read_auth_token_from_scweet_db(db_path: str | None = None) -> str | None:
    """
    Read auth_token from Scweet account pool (data/scweet_state.db → accounts table).
    """
    settings = get_settings()
    path = Path(db_path or settings.scweet_db_path or "data/scweet_state.db")
    if not path.is_file():
        return None

    try:
        conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                """
                SELECT auth_token, cookies_json, username
                FROM accounts
                WHERE (auth_token IS NOT NULL AND TRIM(auth_token) != '')
                   OR (cookies_json IS NOT NULL AND TRIM(cookies_json) != '')
                ORDER BY last_used DESC, id DESC
                LIMIT 5
                """
            ).fetchall()
        except sqlite3.OperationalError as exc:
            logger.warning(f"Could not read accounts from {path}: {exc}")
            return None
        finally:
            conn.close()

        for row in rows:
            token = (row["auth_token"] or "").strip()
            if token:
                logger.debug(f"auth_token from scweet_state.db account {row['username']}")
                return token
            cookies_raw = row["cookies_json"]
            if not cookies_raw:
                continue
            token = _token_from_cookies_json(cookies_raw)
            if token:
                logger.debug(f"auth_token from cookies_json in scweet_state.db ({row['username']})")
                return token
    except Exception as exc:
        logger.warning(f"Failed to read scweet_state.db: {exc}")
    return None


def _token_from_cookies_json(raw: str) -> str | None:
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None
    if isinstance(data, dict):
        token = str(data.get("auth_token") or "").strip()
        return token or None
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and item.get("name") == "auth_token":
                value = str(item.get("value") or "").strip()
                if value:
                    return value
    return None


def resolve_local_auth_token() -> tuple[str, str]:
    """
    Resolve auth token without Playwright.

    Priority:
    1. SCWEET_AUTH_TOKEN environment variable / .env
    2. data/scweet_session.json (Playwright login cache)
    3. data/scweet_state.db (Scweet accounts table)

    Returns (token, source_label).
    """
    settings = get_settings()

    env_token = settings.scweet_auth_token.strip()
    if env_token:
        return env_token, "environment"

    cached = load_cached_session(settings.scweet_session_cache_path)
    if cached and cached.get("auth_token"):
        return str(cached["auth_token"]).strip(), "session_cache"

    db_token = read_auth_token_from_scweet_db()
    if db_token:
        return db_token, "scweet_state.db"

    return "", "none"


def token_source_summary() -> dict[str, Any]:
    """Non-secret summary for CLI / health output."""
    settings = get_settings()
    token, source = resolve_local_auth_token()
    return {
        "has_token": bool(token),
        "source": source,
        "session_cache_path": settings.scweet_session_cache_path,
        "scweet_db_path": settings.scweet_db_path,
        "session_cache_exists": Path(settings.scweet_session_cache_path).is_file(),
        "scweet_db_exists": Path(settings.scweet_db_path).is_file(),
    }
