"""Scweet (X/Twitter) client factory for Karakorum Analytica."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from loguru import logger

from app.config import get_settings
from app.integrations.playwright_env import (
    effective_playwright_headless,
    is_server_runtime,
    playwright_login_allowed,
)
from app.integrations.x_session_login import get_or_create_x_session, load_cached_session
from app.scraping.proxy_pool import parse_proxy_urls

SOURCE_NAME = "X/Scweet"


def _scweet_login_id(settings) -> str:
    username = settings.scweet_username.strip()
    if username:
        return username
    return settings.scweet_email.strip()


def _account_record_from_settings(auth_token: str) -> dict[str, Any] | None:
    settings = get_settings()
    login = _scweet_login_id(settings)
    email = settings.scweet_email.strip()
    password = settings.scweet_password.strip()
    if not login and not auth_token:
        return None

    username = settings.scweet_username.strip() or (email.split("@", 1)[0] if email else "account")
    record: dict[str, Any] = {"username": username}
    if email:
        record["email"] = email
    if password:
        record["password"] = password
    if auth_token:
        record["auth_token"] = auth_token
    cached = load_cached_session(settings.scweet_session_cache_path)
    if cached and cached.get("ct0"):
        record["cookies"] = {"auth_token": auth_token, "ct0": cached["ct0"]}
    return record


def resolve_scweet_auth_token() -> str:
    """Resolve auth_token from env, cache, or email/password login."""
    settings = get_settings()
    token = settings.scweet_auth_token.strip()
    if token:
        return token

    cached = load_cached_session(settings.scweet_session_cache_path)
    if cached and cached.get("auth_token"):
        return str(cached["auth_token"])

    login = _scweet_login_id(settings)
    password = settings.scweet_password.strip()
    if not login or not password:
        return ""

    if not settings.scweet_auto_login or not playwright_login_allowed():
        return ""

    verification = settings.scweet_email.strip() or None
    if verification == login:
        verification = None

    session = get_or_create_x_session(
        login,
        password,
        verification_handle=verification,
        cache_path=settings.scweet_session_cache_path,
        headless=effective_playwright_headless(settings.scweet_login_headless),
    )
    return str(session.get("auth_token") or "")


def scweet_settings_summary() -> dict[str, Any]:
    settings = get_settings()
    db_path = Path(settings.scweet_db_path)
    cached = load_cached_session(settings.scweet_session_cache_path)
    token = settings.scweet_auth_token.strip() or (cached or {}).get("auth_token", "")
    return {
        "enabled": settings.scweet_enabled,
        "configured": settings.scweet_configured,
        "has_auth_token": bool(token),
        "has_credentials": bool(
            settings.scweet_password.strip()
            and (settings.scweet_username.strip() or settings.scweet_email.strip())
        ),
        "auto_login": settings.scweet_auto_login,
        "session_cached": bool(cached and cached.get("auth_token")),
        "has_cookies_file": bool(settings.scweet_cookies_file.strip()),
        "db_path": str(db_path),
        "db_exists": db_path.is_file(),
        "query_count": len(settings.scweet_search_queries_list),
        "playwright_login_allowed": playwright_login_allowed(),
        "server_runtime": is_server_runtime(),
    }


def build_scweet_client():
    """Return an initialized Scweet client or raise ValueError."""
    settings = get_settings()
    if not settings.scweet_enabled:
        raise ValueError("Scweet is disabled. Set SCWEET_ENABLED=true in .env.")

    if not settings.scweet_configured:
        raise ValueError(
            "Scweet credentials missing. Set SCWEET_USERNAME/SCWEET_PASSWORD (or email), "
            "SCWEET_AUTH_TOKEN, SCWEET_COOKIES_FILE, or data/scweet_state.db."
        )

    try:
        from Scweet import Scweet
    except ImportError as exc:
        raise ValueError(
            "Scweet is not installed. Run: pip install -r requirements-scweet.txt"
        ) from exc

    db_path = settings.scweet_db_path.strip() or "data/scweet_state.db"
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    kwargs: dict[str, Any] = {"db_path": db_path}

    proxy = settings.scweet_proxy.strip()
    if not proxy:
        proxies = parse_proxy_urls(settings.proxy_urls)
        if proxies:
            proxy = proxies[0]
    if proxy:
        kwargs["proxy"] = proxy

    cookies_file = settings.scweet_cookies_file.strip()
    auth_token = resolve_scweet_auth_token()

    if cookies_file:
        kwargs["cookies_file"] = cookies_file
    elif auth_token:
        account = _account_record_from_settings(auth_token)
        if account and account.get("cookies"):
            kwargs["cookies"] = [account]
        else:
            kwargs["auth_token"] = auth_token
    else:
        raise ValueError(
            "Could not obtain X session. Check SCWEET_USERNAME/SCWEET_PASSWORD or set "
            "SCWEET_AUTO_LOGIN=true (requires Playwright)."
        )

    logger.info(f"Initializing Scweet client (db={db_path}, proxy={'yes' if proxy else 'no'})")
    return Scweet(**kwargs)
