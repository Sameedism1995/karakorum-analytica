"""Supabase REST client helpers (Postgres remains the primary store via SQLAlchemy)."""

from __future__ import annotations

from typing import Any

from loguru import logger

from app.config import get_settings


def get_supabase_client():
    """Return a Supabase client or None if not configured."""
    settings = get_settings()
    if not settings.supabase_configured:
        return None

    try:
        from supabase import create_client
    except ImportError:
        logger.warning("supabase package not installed")
        return None

    return create_client(settings.supabase_url, settings.supabase_service_role_key)


def check_supabase_api() -> dict[str, Any]:
    """Verify Supabase REST API can read from the public schema."""
    client = get_supabase_client()
    if client is None:
        return {"ok": False, "configured": False, "error": "Supabase API not configured"}

    try:
        response = client.table("sources").select("id", count="exact").limit(1).execute()
        return {
            "ok": True,
            "configured": True,
            "sources_count": response.count,
        }
    except Exception as exc:
        return {
            "ok": False,
            "configured": True,
            "error": str(exc),
        }


def check_supabase_storage() -> dict[str, Any]:
    """Return a summary of row counts via Supabase REST (when tables exist)."""
    client = get_supabase_client()
    if client is None:
        return {"ok": False, "configured": False}

    tables = ("raw_news", "incidents", "draft_posts")
    counts: dict[str, int | None] = {}
    try:
        for table in tables:
            response = client.table(table).select("id", count="exact").limit(1).execute()
            counts[table] = response.count
        return {"ok": True, "configured": True, "counts": counts}
    except Exception as exc:
        return {"ok": False, "configured": True, "error": str(exc), "counts": counts}
