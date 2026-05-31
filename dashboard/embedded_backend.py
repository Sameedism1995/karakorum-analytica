"""Run KarakorumAnalytica pipeline in-process (for Streamlit Cloud without Render API)."""

from __future__ import annotations

import os
from typing import Any

import streamlit as st

from app.config import get_settings
from app.database import SessionLocal, check_database_connection, init_db, reconfigure_engine
from app.services.collection_service import collect_all, get_recent_raw_news, raw_news_to_dict
from app.services.draft_service import (
    approve_draft as approve_draft_record,
    draft_to_dict,
    generate_drafts_for_incidents,
    list_drafts,
    reject_draft as reject_draft_record,
)
from app.services.incident_service import incident_to_dict, list_incidents, process_incidents


def _apply_secrets_to_env() -> None:
    """Load optional collector credentials from Streamlit secrets."""
    try:
        secret_keys = (
            "ACLED_EMAIL",
            "ACLED_API_KEY",
            "RELIEFWEB_APPNAME",
            "SUPABASE_URL",
            "SUPABASE_SERVICE_ROLE_KEY",
            "SUPABASE_DB_URL",
            "SUPABASE_DB_PASSWORD",
            "DATABASE_URL",
        )
        for key in secret_keys:
            if key in st.secrets:
                os.environ[key] = str(st.secrets[key])
    except Exception:
        pass
    get_settings.cache_clear()


@st.cache_resource
def _bootstrap_database() -> bool:
    _apply_secrets_to_env()
    if not os.environ.get("DATABASE_URL"):
        os.environ["DATABASE_URL"] = "sqlite:////tmp/karakorum-analytica.db"
        get_settings.cache_clear()
    reconfigure_engine()
    init_db()
    from scripts.init_db import main as seed_sources

    seed_sources()
    return True


def _session():
    _bootstrap_database()
    return SessionLocal()


def check_backend(base_url: str = "") -> dict[str, Any]:
    _bootstrap_database()
    settings = get_settings()
    db_status = check_database_connection()
    return {
        "ok": db_status.get("ok", False),
        "data": {
            "app": settings.app_name,
            "env": "streamlit-embedded",
            "status": "running",
            "x_posting_enabled": settings.x_posting_enabled,
            "acled_configured": settings.acled_configured,
            "database": {
                "backend": settings.database_backend,
                "using_supabase": settings.using_supabase,
                "connected": db_status.get("ok", False),
                "error": db_status.get("error"),
            },
            "supabase": {
                "configured": settings.supabase_configured,
                "api_ok": None,
                "api_error": None,
            },
            "mode": "embedded",
        },
        "error": db_status.get("error"),
    }


def run_collection(base_url: str = "") -> dict[str, Any]:
    db = _session()
    try:
        collection = collect_all(db)
        incidents = process_incidents(db)
        drafts = generate_drafts_for_incidents(db)
        return {
            "ok": True,
            "data": {"collection": collection, "incidents": incidents, "drafts": drafts},
            "error": None,
        }
    except Exception as exc:
        return {"ok": False, "data": None, "error": str(exc)}
    finally:
        db.close()


def get_raw_news(base_url: str = "", limit: int = 500) -> list[dict[str, Any]]:
    db = _session()
    try:
        return [raw_news_to_dict(r) for r in get_recent_raw_news(db, limit=limit)]
    finally:
        db.close()


def get_incidents(base_url: str = "", limit: int = 500) -> list[dict[str, Any]]:
    db = _session()
    try:
        return [incident_to_dict(r) for r in list_incidents(db, limit=limit)]
    finally:
        db.close()


def get_drafts(base_url: str = "", limit: int = 500) -> list[dict[str, Any]]:
    db = _session()
    try:
        return [draft_to_dict(r) for r in list_drafts(db, limit=limit)]
    finally:
        db.close()


def approve_draft(draft_id: int, base_url: str = "") -> dict[str, Any]:
    db = _session()
    try:
        draft = approve_draft_record(db, draft_id)
        if not draft:
            return {"ok": False, "data": None, "error": "Draft not found"}
        return {"ok": True, "data": {"draft": draft_to_dict(draft)}, "error": None}
    finally:
        db.close()


def reject_draft(draft_id: int, base_url: str = "") -> dict[str, Any]:
    db = _session()
    try:
        draft = reject_draft_record(db, draft_id)
        if not draft:
            return {"ok": False, "data": None, "error": "Draft not found"}
        return {"ok": True, "data": {"draft": draft_to_dict(draft)}, "error": None}
    finally:
        db.close()


def post_draft(draft_id: int, base_url: str = "") -> dict[str, Any]:
    from app.publishers.x_publisher import post_draft_to_x
    from app.services.draft_service import get_draft

    db = _session()
    try:
        draft = get_draft(db, draft_id)
        if not draft:
            return {"ok": False, "data": None, "error": "Draft not found"}
        result = post_draft_to_x(db, draft)
        if not result.get("success"):
            return {"ok": False, "data": None, "error": result.get("error", "Posting failed")}
        return {"ok": True, "data": result, "error": None}
    finally:
        db.close()
