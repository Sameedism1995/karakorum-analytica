"""X (Twitter) API v2 client helpers via tweepy."""

from __future__ import annotations

from typing import Any

from loguru import logger

from app.config import get_settings


def get_x_write_client():
    """
    OAuth 1.0a user-context client — required to post tweets.
    Bearer token alone cannot create tweets.
    """
    settings = get_settings()
    if not settings.x_oauth_configured:
        raise ValueError(
            "X OAuth credentials missing. Set X_API_KEY, X_API_SECRET, "
            "X_ACCESS_TOKEN, and X_ACCESS_TOKEN_SECRET in .env."
        )

    import tweepy

    return tweepy.Client(
        consumer_key=settings.x_api_key,
        consumer_secret=settings.x_api_secret,
        access_token=settings.x_access_token,
        access_token_secret=settings.x_access_token_secret,
    )


def get_x_read_client():
    """App or user context client for read-only API calls."""
    settings = get_settings()
    import tweepy

    if settings.x_oauth_configured:
        return get_x_write_client()
    if settings.x_bearer_token.strip():
        return tweepy.Client(bearer_token=settings.x_bearer_token.strip())
    raise ValueError(
        "X read credentials missing. Set X_BEARER_TOKEN or OAuth keys in .env."
    )


def check_x_connection() -> dict[str, Any]:
    """Verify X API credentials (OAuth preferred for full access)."""
    settings = get_settings()
    if not settings.x_configured:
        return {
            "ok": False,
            "configured": False,
            "posting_enabled": settings.x_posting_enabled,
            "error": "X API not configured. Add credentials to .env (see .env.example).",
        }

    try:
        if settings.x_oauth_configured:
            client = get_x_write_client()
            me = client.get_me(user_fields=["username", "name", "public_metrics"])
            user = me.data
            metrics = getattr(user, "public_metrics", None) or {}
            return {
                "ok": True,
                "configured": True,
                "mode": "oauth_user",
                "posting_enabled": settings.x_posting_enabled,
                "can_post": True,
                "username": user.username,
                "name": user.name,
                "user_id": str(user.id),
                "followers_count": metrics.get("followers_count"),
            }

        client = get_x_read_client()
        probe = client.get_user(username="X", user_fields=["username"])
        return {
            "ok": True,
            "configured": True,
            "mode": "bearer_read_only",
            "posting_enabled": settings.x_posting_enabled,
            "can_post": False,
            "username": probe.data.username if probe.data else None,
            "note": "Bearer token can read public data only. Add OAuth keys to post tweets.",
        }
    except Exception as exc:
        logger.warning(f"X API connection check failed: {exc}")
        return {
            "ok": False,
            "configured": True,
            "posting_enabled": settings.x_posting_enabled,
            "error": str(exc),
        }
