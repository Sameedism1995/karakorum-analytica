"""CRUD and polling for watched X profile handles."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from loguru import logger
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.x_watch_account import XWatchAccount
from app.services.scweet_persist_service import persist_scweet_items
from app.services.scweet_service import execute_scweet_operation
from app.services.x_posting_analytics import compute_posting_stats, compute_posting_stats_map

_HANDLE_RE = re.compile(r"^[A-Za-z0-9_]{1,15}$")


def normalize_x_handle(raw: str) -> str | None:
    """Normalize @user, user, or x.com/user URL to lowercase handle."""
    text = (raw or "").strip()
    if not text:
        return None

    if "x.com/" in text or "twitter.com/" in text:
        try:
            path = urlparse(text if "://" in text else f"https://{text}").path
            parts = [p for p in path.split("/") if p]
            if parts:
                candidate = parts[0].lstrip("@")
                if candidate.lower() not in {"home", "search", "i", "intent"}:
                    text = candidate
        except Exception:
            pass

    text = text.lstrip("@").strip()
    if not text or not _HANDLE_RE.match(text):
        return None
    return text.lower()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _mins_ago(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    seconds = max(0, int((_utc_now() - dt).total_seconds()))
    if seconds < 60:
        return "just now"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} min ago"
    hours = minutes // 60
    if hours < 48:
        return f"{hours} hr ago"
    days = hours // 24
    return f"{days} day ago"


def watch_account_to_dict(
    record: XWatchAccount,
    *,
    posting: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "id": record.id,
        "handle": record.handle,
        "enabled": record.enabled,
        "added_at": record.added_at.isoformat() if record.added_at else None,
        "last_fetched_at": record.last_fetched_at.isoformat() if record.last_fetched_at else None,
        "last_fetched_mins_ago": _mins_ago(record.last_fetched_at),
        "last_tweet_count": record.last_tweet_count,
        "last_saved_count": record.last_saved_count,
        "total_tweets_fetched": record.total_tweets_fetched,
        "total_tweets_saved": record.total_tweets_saved,
        "last_error": record.last_error,
    }
    if posting is not None:
        payload["posting"] = posting
    return payload


def list_watch_accounts(db: Session, *, enabled_only: bool = False) -> list[dict[str, Any]]:
    query = db.query(XWatchAccount).order_by(XWatchAccount.handle.asc())
    if enabled_only:
        query = query.filter(XWatchAccount.enabled.is_(True))
    rows = query.all()
    stats_map = compute_posting_stats_map(db, [row.handle for row in rows])
    return [
        watch_account_to_dict(row, posting=stats_map.get(row.handle))
        for row in rows
    ]


def add_watch_account(db: Session, raw_handle: str) -> dict[str, Any]:
    handle = normalize_x_handle(raw_handle)
    if not handle:
        return {"ok": False, "error": "Invalid X handle or profile URL."}

    existing = db.query(XWatchAccount).filter(XWatchAccount.handle == handle).first()
    if existing:
        if not existing.enabled:
            existing.enabled = True
            existing.last_error = None
            db.commit()
            db.refresh(existing)
        posting = compute_posting_stats(db, existing.handle)
        return {
            "ok": True,
            "created": False,
            "account": watch_account_to_dict(existing, posting=posting),
        }

    record = XWatchAccount(
        handle=handle,
        enabled=True,
        added_at=_utc_now(),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    logger.info(f"Added X watch account @{handle}")
    posting = compute_posting_stats(db, handle)
    return {"ok": True, "created": True, "account": watch_account_to_dict(record, posting=posting)}


def remove_watch_account(db: Session, raw_handle: str) -> dict[str, Any]:
    handle = normalize_x_handle(raw_handle) or raw_handle.strip().lstrip("@").lower()
    record = db.query(XWatchAccount).filter(XWatchAccount.handle == handle).first()
    if not record:
        return {"ok": False, "error": f"@{handle} is not on the watch list."}
    db.delete(record)
    db.commit()
    logger.info(f"Removed X watch account @{handle}")
    return {"ok": True, "handle": handle}


def fetch_watch_account(
    db: Session,
    raw_handle: str,
    *,
    limit: int | None = None,
) -> dict[str, Any]:
    """Fetch one profile timeline and persist tweets to raw_news."""
    handle = normalize_x_handle(raw_handle)
    if not handle:
        return {"ok": False, "error": "Invalid X handle."}

    record = db.query(XWatchAccount).filter(XWatchAccount.handle == handle).first()
    if not record:
        add_result = add_watch_account(db, handle)
        if not add_result.get("ok"):
            return add_result
        record = db.query(XWatchAccount).filter(XWatchAccount.handle == handle).first()

    settings = get_settings()
    tweet_limit = limit if limit is not None else max(settings.x_watch_profile_limit, 1)

    result = execute_scweet_operation(
        "profile_tweets",
        {
            "users": handle,
            "limit": tweet_limit,
            "save": False,
            "resume": False,
            "max_empty_pages": 3,
        },
    )

    if not result.get("ok"):
        err = str(result.get("error") or "Fetch failed")
        record.last_error = err
        db.commit()
        posting = compute_posting_stats(db, handle)
        return {"ok": False, "error": err, "handle": handle, "account": watch_account_to_dict(record, posting=posting)}

    items = result.get("items") or []
    if not items:
        scweet_err = (result.get("scweet") or {}).get("error")
        err = scweet_err or f"No tweets returned for @{handle} (timeline empty or rate limited)."
        record.last_error = err
        record.last_fetched_at = _utc_now()
        record.last_tweet_count = 0
        record.last_saved_count = 0
        db.commit()
        posting = compute_posting_stats(db, handle)
        return {
            "ok": False,
            "error": err,
            "handle": handle,
            "count": 0,
            "account": watch_account_to_dict(record, posting=posting),
        }
    persist_stats = persist_scweet_items(db, items, apply_pipeline_filters=False)

    saved_now = int(persist_stats.get("saved", 0))
    fetched_now = len(items)
    record.last_fetched_at = _utc_now()
    record.last_tweet_count = fetched_now
    record.last_saved_count = saved_now
    record.total_tweets_fetched = int(record.total_tweets_fetched or 0) + fetched_now
    record.total_tweets_saved = int(record.total_tweets_saved or 0) + saved_now
    record.last_error = None
    db.commit()
    db.refresh(record)

    posting = compute_posting_stats(db, handle)
    return {
        **result,
        "handle": handle,
        "persist": persist_stats,
        "account": watch_account_to_dict(record, posting=posting),
    }


def collect_all_watch_accounts(
    db: Session,
    on_progress: Any | None = None,
) -> dict[str, int]:
    """Poll every enabled watched profile and save tweets to the database."""
    accounts = db.query(XWatchAccount).filter(XWatchAccount.enabled.is_(True)).all()
    total_saved = 0
    total_fetched = 0
    errors = 0
    error_details: list[dict[str, str]] = []

    for index, account in enumerate(accounts):
        if on_progress:
            pct = 60 + int((index / max(len(accounts), 1)) * 2)
            on_progress(
                f"Fetching @{account.handle} ({index + 1}/{len(accounts)})…",
                pct,
                "x_watch",
            )
        result = fetch_watch_account(db, account.handle)
        if result.get("ok"):
            total_fetched += result.get("count", len(result.get("items") or []))
            total_saved += (result.get("persist") or {}).get("saved", 0)
        else:
            errors += 1
            msg = str(result.get("error") or "Fetch failed")
            error_details.append({"handle": account.handle, "error": msg})
            logger.warning(f"Watch fetch failed for @{account.handle}: {msg}")

    return {
        "ok": errors < len(accounts),
        "handles": len(accounts),
        "tweets_fetched": total_fetched,
        "saved": total_saved,
        "errors": errors,
        "error_details": error_details,
    }
