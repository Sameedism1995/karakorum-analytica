"""Read-only dashboard queries via Supabase REST when Postgres is unreachable."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any

from loguru import logger

from app.integrations.supabase_client import get_supabase_client
from app.services.x_watch_service import normalize_x_handle

_WATCH_COLUMNS = (
    "id,handle,enabled,added_at,last_fetched_at,last_tweet_count,last_saved_count,"
    "total_tweets_fetched,total_tweets_saved,last_error"
)


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()
    return str(value)


def _table_count(client, table: str) -> int:
    response = client.table(table).select("id", count="exact").limit(1).execute()
    return int(response.count or 0)


def rest_reads_available() -> bool:
    client = get_supabase_client()
    if client is None:
        return False
    try:
        client.table("raw_news").select("id", count="exact").limit(1).execute()
        return True
    except Exception:
        return False


def fetch_dashboard_stats_rest() -> dict[str, Any] | None:
    client = get_supabase_client()
    if client is None:
        return None

    try:
        total_raw = _table_count(client, "raw_news")
        total_incidents = _table_count(client, "incidents")
        total_drafts = _table_count(client, "draft_posts")

        sources_resp = client.table("raw_news").select("source_name").limit(5000).execute()
        sources_active = len({row["source_name"] for row in (sources_resp.data or []) if row.get("source_name")})

        status_resp = client.table("incidents").select("status").limit(5000).execute()
        status_counts = Counter(row.get("status") for row in (status_resp.data or []) if row.get("status"))

        last_collection = "—"
        latest_resp = (
            client.table("raw_news")
            .select("collected_at")
            .order("collected_at", desc=True)
            .limit(1)
            .execute()
        )
        if latest_resp.data:
            collected_at = latest_resp.data[0].get("collected_at")
            if collected_at:
                last_collection = str(collected_at).replace("T", " ").split("+")[0].split(".")[0] + " UTC"

        return {
            "total_raw": total_raw,
            "total_incidents": total_incidents,
            "total_drafts": total_drafts,
            "sources_active": sources_active,
            "ready_for_review": status_counts.get("ready_for_review", 0),
            "needs_review": status_counts.get("needs_review", 0),
            "save_only": status_counts.get("save_only", 0),
            "last_collection": last_collection,
            "_via": "supabase_rest",
        }
    except Exception as exc:
        logger.warning(f"Supabase REST stats failed: {exc}")
        return None


def fetch_raw_news_rest(*, limit: int = 500) -> dict[str, Any] | None:
    client = get_supabase_client()
    if client is None:
        return None

    try:
        total = _table_count(client, "raw_news")
        response = (
            client.table("raw_news")
            .select(
                "id,source_name,title,summary,url,published_at,collected_at,"
                "country,province,city,content_hash,status"
            )
            .order("collected_at", desc=True)
            .limit(limit)
            .execute()
        )
        items = [_raw_news_row_to_dict(row) for row in (response.data or [])]
        return {"count": len(items), "total": total, "items": items, "_via": "supabase_rest"}
    except Exception as exc:
        logger.warning(f"Supabase REST raw_news failed: {exc}")
        return None


def fetch_incidents_rest(*, limit: int = 100) -> dict[str, Any] | None:
    client = get_supabase_client()
    if client is None:
        return None

    try:
        response = (
            client.table("incidents")
            .select(
                "id,main_title,country,province,city,event_type,confidence_score,"
                "matched_sources,keywords,status,event_at,created_at"
            )
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        items = [_incident_row_to_dict(row) for row in (response.data or [])]
        return {"count": len(items), "items": items, "_via": "supabase_rest"}
    except Exception as exc:
        logger.warning(f"Supabase REST incidents failed: {exc}")
        return None


def fetch_drafts_rest(*, limit: int = 100) -> dict[str, Any] | None:
    client = get_supabase_client()
    if client is None:
        return None

    try:
        response = (
            client.table("draft_posts")
            .select(
                "id,incident_id,post_text,keywords,confidence_score,status,"
                "created_at,approved_at,posted_at,x_post_id"
            )
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        items = [_draft_row_to_dict(row) for row in (response.data or [])]
        return {"count": len(items), "items": items, "_via": "supabase_rest"}
    except Exception as exc:
        logger.warning(f"Supabase REST drafts failed: {exc}")
        return None


def _raw_news_row_to_dict(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "source_name": row.get("source_name"),
        "title": row.get("title"),
        "summary": row.get("summary"),
        "url": row.get("url"),
        "published_at": _iso(row.get("published_at")),
        "collected_at": _iso(row.get("collected_at")) or "",
        "country": row.get("country"),
        "province": row.get("province"),
        "city": row.get("city"),
        "content_hash": row.get("content_hash"),
        "status": row.get("status"),
    }


def _incident_row_to_dict(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "main_title": row.get("main_title"),
        "country": row.get("country"),
        "province": row.get("province"),
        "city": row.get("city"),
        "event_type": row.get("event_type"),
        "confidence_score": row.get("confidence_score"),
        "matched_sources": row.get("matched_sources"),
        "keywords": row.get("keywords"),
        "status": row.get("status"),
        "event_at": _iso(row.get("event_at")),
        "created_at": _iso(row.get("created_at")) or "",
    }


def _mins_ago_label(dt_value: Any) -> str | None:
    if not dt_value:
        return None
    try:
        text = str(dt_value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    seconds = max(0, int((datetime.now(timezone.utc) - dt).total_seconds()))
    if seconds < 60:
        return "just now"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} min ago"
    hours = minutes // 60
    if hours < 48:
        return f"{hours} hr ago"
    return f"{hours // 24} day ago"


def _watch_row_to_dict(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "handle": row.get("handle"),
        "enabled": row.get("enabled", True),
        "added_at": _iso(row.get("added_at")),
        "last_fetched_at": _iso(row.get("last_fetched_at")),
        "last_fetched_mins_ago": _mins_ago_label(row.get("last_fetched_at")),
        "last_tweet_count": row.get("last_tweet_count") or 0,
        "last_saved_count": row.get("last_saved_count") or 0,
        "total_tweets_fetched": row.get("total_tweets_fetched") or 0,
        "total_tweets_saved": row.get("total_tweets_saved") or 0,
        "last_error": row.get("last_error"),
        "posting": {
            "ready": False,
            "sample_size": 0,
            "summary": "Posting stats unavailable in REST mode",
        },
    }


def fetch_watch_accounts_rest() -> dict[str, Any] | None:
    client = get_supabase_client()
    if client is None:
        return None
    try:
        response = (
            client.table("x_watch_accounts")
            .select(_WATCH_COLUMNS)
            .order("handle")
            .execute()
        )
        items = [_watch_row_to_dict(row) for row in (response.data or [])]
        return {"ok": True, "count": len(items), "items": items, "_via": "supabase_rest"}
    except Exception as exc:
        logger.warning(f"Supabase REST x_watch_accounts list failed: {exc}")
        return None


def add_watch_account_rest(raw_handle: str) -> dict[str, Any] | None:
    client = get_supabase_client()
    if client is None:
        return None
    handle = normalize_x_handle(raw_handle)
    if not handle:
        return {"ok": False, "error": "Invalid X handle or profile URL."}

    try:
        existing = (
            client.table("x_watch_accounts")
            .select(_WATCH_COLUMNS)
            .eq("handle", handle)
            .limit(1)
            .execute()
        )
        if existing.data:
            row = existing.data[0]
            if not row.get("enabled", True):
                updated = (
                    client.table("x_watch_accounts")
                    .update({"enabled": True, "last_error": None})
                    .eq("id", row["id"])
                    .execute()
                )
                row = (updated.data or [row])[0]
            account = _watch_row_to_dict(row)
            return {"ok": True, "created": False, "account": account, "_via": "supabase_rest"}

        now = datetime.now(timezone.utc).isoformat()
        inserted = (
            client.table("x_watch_accounts")
            .insert({"handle": handle, "enabled": True, "added_at": now})
            .execute()
        )
        row = (inserted.data or [None])[0]
        if not row:
            return {"ok": False, "error": "Insert failed."}
        return {
            "ok": True,
            "created": True,
            "account": _watch_row_to_dict(row),
            "_via": "supabase_rest",
        }
    except Exception as exc:
        logger.warning(f"Supabase REST add watch account failed: {exc}")
        return {"ok": False, "error": str(exc)}


def remove_watch_account_rest(raw_handle: str) -> dict[str, Any] | None:
    client = get_supabase_client()
    if client is None:
        return None
    handle = normalize_x_handle(raw_handle) or raw_handle.strip().lstrip("@").lower()
    try:
        client.table("x_watch_accounts").delete().eq("handle", handle).execute()
        return {"ok": True, "handle": handle, "_via": "supabase_rest"}
    except Exception as exc:
        logger.warning(f"Supabase REST remove watch account failed: {exc}")
        return {"ok": False, "error": str(exc)}


def _draft_row_to_dict(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "incident_id": row.get("incident_id"),
        "post_text": row.get("post_text"),
        "keywords": row.get("keywords"),
        "confidence_score": row.get("confidence_score"),
        "status": row.get("status"),
        "created_at": _iso(row.get("created_at")) or "",
        "approved_at": _iso(row.get("approved_at")),
        "posted_at": _iso(row.get("posted_at")),
        "x_post_id": row.get("x_post_id"),
    }
