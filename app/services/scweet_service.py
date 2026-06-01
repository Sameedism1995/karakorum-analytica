"""Scweet operations for the API and dashboard."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from loguru import logger

from app.collectors.scweet_collector import DEFAULT_QUERY, _tweet_to_item
from app.config import get_settings
from app.integrations.scweet_client import (
    SOURCE_NAME,
    _scweet_login_id,
    build_scweet_client,
    resolve_scweet_auth_token,
    scweet_settings_summary,
)
from app.integrations.playwright_env import (
    effective_playwright_headless,
    playwright_login_allowed,
    playwright_login_blocked_message,
)
from app.integrations.x_session_login import get_or_create_x_session

VALID_OPERATIONS = frozenset(
    {"search", "profile_tweets", "followers", "following", "user_info"}
)

TWEET_TYPE_OPTIONS = (
    "all",
    "originals_only",
    "replies_only",
    "retweets_only",
    "exclude_replies",
    "exclude_retweets",
)


def get_scweet_health() -> dict[str, Any]:
    """Return Scweet configuration and client readiness."""
    summary = dict(scweet_settings_summary())
    summary["source_name"] = SOURCE_NAME
    summary["default_query"] = DEFAULT_QUERY
    summary["operations"] = sorted(VALID_OPERATIONS)

    if summary.get("enabled") and summary.get("configured"):
        try:
            build_scweet_client()
            summary["client_ok"] = True
            summary["error"] = None
        except Exception as exc:
            summary["client_ok"] = False
            summary["error"] = str(exc)
    else:
        summary["client_ok"] = False
        summary["error"] = None

    return summary


def _parse_users(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        items = value
    else:
        items = str(value).replace("\n", ",").split(",")
    users: list[str] = []
    for item in items:
        handle = str(item).strip().lstrip("@")
        if handle and handle not in users:
            users.append(handle)
    return users


def _parse_words(value: Any) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, list):
        words = [str(w).strip() for w in value if str(w).strip()]
    else:
        text = str(value).strip()
        if not text:
            return None
        words = [w.strip() for w in text.replace("\n", ",").split(",") if w.strip()]
    return words or None


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def _optional_bool(value: Any) -> bool | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _default_since(days: int | None = None) -> str:
    settings = get_settings()
    span = days if days is not None else max(settings.scweet_since_days, 1)
    return (datetime.now(timezone.utc) - timedelta(days=span)).strftime("%Y-%m-%d")


def _default_until() -> str:
    return date.today().strftime("%Y-%m-%d")


def _ensure_session() -> dict[str, Any] | None:
    settings = get_settings()
    if not settings.scweet_enabled:
        return {"ok": False, "error": "Scweet is disabled (SCWEET_ENABLED=false)."}
    if resolve_scweet_auth_token() or settings.scweet_auth_token.strip():
        return None
    if not playwright_login_allowed():
        return {
            "ok": False,
            "error": playwright_login_blocked_message(),
            "scweet": get_scweet_health(),
        }
    refresh = refresh_scweet_session(force=False)
    if not refresh.get("ok"):
        return {
            "ok": False,
            "error": refresh.get("error") or "Could not obtain X session.",
            "scweet": refresh.get("scweet"),
        }
    return None


def refresh_scweet_session(*, force: bool = False, headless: bool | None = None) -> dict[str, Any]:
    """Log into X and cache session cookies for Scweet."""
    settings = get_settings()

    if not playwright_login_allowed():
        return {
            "ok": False,
            "error": playwright_login_blocked_message(),
            "scweet": get_scweet_health(),
        }

    login = _scweet_login_id(settings)
    password = settings.scweet_password.strip()

    if not login or not password:
        return {
            "ok": False,
            "error": "Set SCWEET_USERNAME (or SCWEET_EMAIL) and SCWEET_PASSWORD in .env",
            "scweet": get_scweet_health(),
        }

    verification = settings.scweet_email.strip() or None
    if verification == login:
        verification = None

    use_headless = effective_playwright_headless(
        settings.scweet_login_headless if headless is None else headless
    )

    try:
        session = get_or_create_x_session(
            login,
            password,
            verification_handle=verification,
            cache_path=settings.scweet_session_cache_path,
            headless=use_headless,
            force_refresh=force,
        )
        token = str(session.get("auth_token") or "")
        if not token:
            return {
                "ok": False,
                "error": "Login finished but no auth_token cookie was captured.",
                "scweet": get_scweet_health(),
            }

        build_scweet_client()
        return {
            "ok": True,
            "message": "X session refreshed and Scweet client verified.",
            "session_cached": True,
            "has_auth_token": True,
            "scweet": get_scweet_health(),
        }
    except Exception as exc:
        logger.exception("Scweet session refresh failed")
        return {
            "ok": False,
            "error": str(exc),
            "scweet": get_scweet_health(),
        }


def get_scweet_accounts(*, runs_limit: int = 10) -> dict[str, Any]:
    """Return provisioned Scweet account pool and recent runs."""
    settings = get_settings()
    db_path = Path(settings.scweet_db_path.strip() or "data/scweet_state.db")
    if not db_path.is_file():
        return {
            "ok": True,
            "db_path": str(db_path),
            "summary": {"total": 0},
            "accounts": [],
            "runs": [],
        }

    try:
        from Scweet import ScweetDB

        db = ScweetDB(str(db_path))
        return {
            "ok": True,
            "db_path": str(db_path),
            "summary": db.accounts_summary(),
            "accounts": db.list_accounts(include_cookies=True),
            "runs": db.list_runs(limit=max(runs_limit, 1)),
        }
    except Exception as exc:
        logger.exception("Failed to read Scweet DB")
        return {"ok": False, "error": str(exc), "accounts": [], "runs": []}


def _output_options(params: dict[str, Any]) -> dict[str, Any]:
    opts: dict[str, Any] = {"save": bool(params.get("save"))}
    save_format = str(params.get("save_format") or "").strip()
    if save_format:
        opts["save_format"] = save_format
    save_name = str(params.get("save_name") or "").strip()
    if save_name:
        opts["save_name"] = save_name
    return opts


def _pagination_options(params: dict[str, Any]) -> dict[str, Any]:
    opts: dict[str, Any] = {
        "limit": _optional_int(params.get("limit")),
        "resume": bool(params.get("resume")),
    }
    max_empty = _optional_int(params.get("max_empty_pages"))
    if max_empty is not None:
        opts["max_empty_pages"] = max_empty
    return opts


def execute_scweet_operation(operation: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Run a Scweet library operation and return structured results."""
    op = (operation or "").strip().lower()
    if op not in VALID_OPERATIONS:
        return {
            "ok": False,
            "error": f"Unknown operation '{operation}'. Valid: {', '.join(sorted(VALID_OPERATIONS))}",
        }

    payload = dict(params or {})
    session_error = _ensure_session()
    if session_error:
        return session_error

    settings = get_settings()
    try:
        client = build_scweet_client()
    except Exception as exc:
        return {"ok": False, "error": str(exc), "operation": op}

    try:
        if op == "search":
            result = _run_search(client, payload, settings)
        elif op == "profile_tweets":
            result = _run_profile_tweets(client, payload)
        elif op in {"followers", "following"}:
            result = _run_follows(client, payload, op)
        else:
            result = _run_user_info(client, payload)

        result["operation"] = op
        result["scweet"] = get_scweet_health()
        return result
    except Exception as exc:
        logger.exception(f"Scweet operation '{op}' failed")
        return {"ok": False, "error": str(exc), "operation": op, "scweet": get_scweet_health()}


def _run_search(client, params: dict[str, Any], settings) -> dict[str, Any]:
    query = str(params.get("query") or "").strip()
    since = str(params.get("since") or "").strip() or _default_since()
    until = str(params.get("until") or "").strip() or _default_until()
    limit = _optional_int(params.get("limit"))
    if limit is None:
        limit = max(min(settings.scweet_limit, 100), 1)

    kwargs: dict[str, Any] = {
        "query": query,
        "since": since,
        "until": until,
        "limit": limit,
        "lang": str(params.get("lang") or settings.scweet_lang or "").strip() or None,
        "display_type": str(params.get("display_type") or "Top"),
        **_pagination_options(params),
        **_output_options(params),
    }

    filter_fields = (
        "all_words",
        "any_words",
        "exact_phrases",
        "exclude_words",
        "hashtags_any",
        "hashtags_exclude",
        "from_users",
        "to_users",
        "mentioning_users",
        "place",
        "geocode",
        "near",
        "within",
    )
    for field in filter_fields:
        if field.endswith("_users") or field in {"from_users", "to_users", "mentioning_users"}:
            parsed = _parse_users(params.get(field))
            if parsed:
                kwargs[field] = parsed
        else:
            parsed = _parse_words(params.get(field))
            if parsed:
                kwargs[field] = parsed

    for field in ("tweet_type",):
        value = str(params.get(field) or "").strip()
        if value and value in TWEET_TYPE_OPTIONS:
            kwargs[field] = value

    for field in (
        "verified_only",
        "blue_verified_only",
        "has_images",
        "has_videos",
        "has_links",
        "has_mentions",
        "has_hashtags",
    ):
        parsed = _optional_bool(params.get(field))
        if parsed is not None:
            kwargs[field] = parsed

    for field in ("min_likes", "min_replies", "min_retweets"):
        parsed = _optional_int(params.get(field))
        if parsed is not None:
            kwargs[field] = parsed

    tweets = client.search(**kwargs)
    items = [_tweet_to_item(t) for t in (tweets or []) if isinstance(t, dict)]
    return {
        "ok": True,
        "result_type": "tweets",
        "count": len(items),
        "items": items,
        "raw": tweets or [],
        "params": {k: v for k, v in kwargs.items() if v is not None},
    }


def _run_profile_tweets(client, params: dict[str, Any]) -> dict[str, Any]:
    users = _parse_users(params.get("users"))
    if not users:
        return {"ok": False, "error": "Provide at least one username for profile tweets."}

    limit = _optional_int(params.get("limit"))
    if limit is None:
        limit = 50

    kwargs = {"limit": limit, **_pagination_options(params), **_output_options(params)}
    tweets = client.get_profile_tweets(users, **kwargs)
    items = [_tweet_to_item(t) for t in (tweets or []) if isinstance(t, dict)]
    return {
        "ok": True,
        "result_type": "tweets",
        "count": len(items),
        "items": items,
        "raw": tweets or [],
        "params": {"users": users, **kwargs},
    }


def _run_follows(client, params: dict[str, Any], follow_type: str) -> dict[str, Any]:
    users = _parse_users(params.get("users"))
    if not users:
        return {"ok": False, "error": f"Provide at least one username for {follow_type}."}

    limit = _optional_int(params.get("limit"))
    if limit is None:
        limit = 100

    kwargs = {
        "limit": limit,
        "raw_json": bool(params.get("raw_json")),
        **_pagination_options(params),
        **_output_options(params),
    }
    method = client.get_followers if follow_type == "followers" else client.get_following
    records = method(users, **kwargs)
    return {
        "ok": True,
        "result_type": "users",
        "count": len(records or []),
        "items": records or [],
        "params": {"users": users, "follow_type": follow_type, **kwargs},
    }


def _run_user_info(client, params: dict[str, Any]) -> dict[str, Any]:
    users = _parse_users(params.get("users"))
    if not users:
        return {"ok": False, "error": "Provide at least one username for user info."}

    kwargs = _output_options(params)
    profiles = client.get_user_info(users, **kwargs)
    return {
        "ok": True,
        "result_type": "users",
        "count": len(profiles or []),
        "items": profiles or [],
        "params": {"users": users, **kwargs},
    }


def run_scweet_test_search(
    *,
    query: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Run a live Scweet search and return sample tweets (does not persist)."""
    settings = get_settings()
    search_query = (query or "").strip() or DEFAULT_QUERY
    tweet_limit = max(limit or min(settings.scweet_limit, 10), 1)
    return execute_scweet_operation(
        "search",
        {
            "query": search_query,
            "limit": tweet_limit,
            "since": _default_since(),
            "until": _default_until(),
            "lang": settings.scweet_lang or None,
        },
    )
