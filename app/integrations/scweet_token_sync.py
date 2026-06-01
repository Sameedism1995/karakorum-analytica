"""Refresh local Scweet session and sync SCWEET_AUTH_TOKEN to Render."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger

from app.config import get_settings
from app.integrations.render_client import RenderApiError, resolve_service_ids, trigger_deploy, update_env_var
from app.integrations.scweet_client import _scweet_login_id, build_scweet_client, resolve_scweet_auth_token
from app.integrations.x_session_login import SESSION_TTL_HOURS, get_or_create_x_session, load_cached_session
from app.services.scweet_service import refresh_scweet_session


def read_cached_session(cache_path: str | None = None) -> dict[str, Any] | None:
    settings = get_settings()
    return load_cached_session(cache_path or settings.scweet_session_cache_path)


def session_expires_at(cache_path: str | None = None) -> datetime | None:
    cached = read_cached_session(cache_path)
    if not cached:
        return None
    raw = cached.get("expires_at")
    if not raw:
        return None
    try:
        exp = datetime.fromisoformat(str(raw))
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        return exp
    except ValueError:
        return None


def is_session_expiring_soon(*, within_hours: float = 2.0, cache_path: str | None = None) -> bool:
    expires = session_expires_at(cache_path)
    if expires is None:
        return True
    remaining = expires - datetime.now(timezone.utc)
    return remaining.total_seconds() <= within_hours * 3600


def update_local_env(token: str, *, env_path: Path | None = None) -> None:
    """Write SCWEET_AUTH_TOKEN into .env and disable Playwright auto-login."""
    root = Path(__file__).resolve().parents[2]
    path = env_path or root / ".env"
    if not path.is_file():
        raise FileNotFoundError(f".env not found at {path}")

    text = path.read_text(encoding="utf-8")
    if re.search(r"^SCWEET_AUTH_TOKEN=", text, flags=re.M):
        text = re.sub(r"^SCWEET_AUTH_TOKEN=.*$", f"SCWEET_AUTH_TOKEN={token}", text, flags=re.M)
    else:
        text = text.rstrip() + f"\nSCWEET_AUTH_TOKEN={token}\n"
    text = re.sub(r"^SCWEET_AUTO_LOGIN=.*$", "SCWEET_AUTO_LOGIN=false", text, flags=re.M)
    path.write_text(text, encoding="utf-8")


def refresh_local_session(*, force: bool = False) -> str:
    """Log into X locally and return auth_token."""
    settings = get_settings()
    if force:
        result = refresh_scweet_session(force=True)
        if not result.get("ok"):
            raise RuntimeError(result.get("error") or "Session refresh failed")
        token = resolve_scweet_auth_token()
        if not token:
            raise RuntimeError("Login succeeded but auth_token is missing")
        return token

    login = _scweet_login_id(settings)
    password = settings.scweet_password.strip()
    if not login or not password:
        raise RuntimeError("Set SCWEET_USERNAME and SCWEET_PASSWORD in .env")

    verification = settings.scweet_email.strip() or None
    if verification == login:
        verification = None

    session = get_or_create_x_session(
        login,
        password,
        verification_handle=verification,
        cache_path=settings.scweet_session_cache_path,
        headless=settings.scweet_login_headless,
        force_refresh=False,
    )
    token = str(session.get("auth_token") or "")
    if not token:
        raise RuntimeError("Could not obtain auth_token from cached session or login")
    build_scweet_client()
    return token


def sync_token_to_render(
    token: str,
    *,
    service_names: list[str] | None = None,
    deploy: bool = False,
) -> list[str]:
    """Push SCWEET_AUTH_TOKEN to configured Render services."""
    settings = get_settings()
    names = service_names or settings.render_scweet_service_names_list
    if not names:
        raise RenderApiError("No Render service names configured (RENDER_SCWEET_SERVICE_NAMES)")

    service_ids = resolve_service_ids(names)
    updated: list[str] = []

    for name, service_id in service_ids.items():
        update_env_var(service_id, "SCWEET_AUTH_TOKEN", token)
        update_env_var(service_id, "SCWEET_AUTO_LOGIN", "false")
        update_env_var(service_id, "SCWEET_ENABLED", "true")
        logger.info(f"Updated SCWEET_AUTH_TOKEN on Render service {name} ({service_id})")
        updated.append(name)
        if deploy:
            trigger_deploy(service_id)
            logger.info(f"Triggered deploy for {name}")

    return updated


def run_sync(
    *,
    force_refresh: bool = False,
    if_expiring_within_hours: float | None = 2.0,
    skip_render: bool = False,
    deploy: bool = False,
    update_env: bool = True,
) -> dict[str, Any]:
    """Refresh token if needed, update .env, and sync to Render."""
    settings = get_settings()
    cache_path = settings.scweet_session_cache_path

    needs_refresh = force_refresh
    if not needs_refresh and if_expiring_within_hours is not None:
        needs_refresh = is_session_expiring_soon(within_hours=if_expiring_within_hours, cache_path=cache_path)

    cached = read_cached_session(cache_path)
    if needs_refresh:
        token = refresh_local_session(force=True)
    else:
        token = settings.scweet_auth_token.strip() or str((cached or {}).get("auth_token") or "")
        if not token:
            token = refresh_local_session(force=True)

    if update_env:
        update_local_env(token)

    expires = session_expires_at(cache_path)
    result: dict[str, Any] = {
        "ok": True,
        "refreshed": needs_refresh,
        "token_length": len(token),
        "expires_at": expires.isoformat() if expires else None,
        "render_services": [],
    }

    if skip_render:
        result["render_skipped"] = True
        return result

    if not settings.render_api_key.strip():
        result["render_skipped"] = True
        result["render_note"] = "Set RENDER_API_KEY in .env to auto-sync to Render"
        return result

    result["render_services"] = sync_token_to_render(token, deploy=deploy)
    return result
