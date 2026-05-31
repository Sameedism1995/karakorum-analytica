"""Run Karakorum Analytica pipeline in-process (for Streamlit Cloud without Render API)."""

from __future__ import annotations

import os
from pathlib import Path
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

CLOUD_SQLITE = "sqlite:////tmp/karakorum-analytica.db"
LOCAL_SQLITE = "sqlite:///./local.db"


def _on_streamlit_cloud() -> bool:
    cwd = os.getcwd()
    root = str(Path(__file__).resolve().parent.parent)
    return "/mount/src" in cwd or root.startswith("/mount/src")


def _apply_secrets_to_env() -> None:
    """Load optional collector credentials from Streamlit secrets."""
    try:
        secret_keys = (
            "ACLED_EMAIL",
            "ACLED_API_KEY",
            "RELIEFWEB_APPNAME",
        )
        for key in secret_keys:
            if key in st.secrets:
                os.environ[key] = str(st.secrets[key])
    except Exception:
        pass
    get_settings.cache_clear()


def _seed_sources() -> None:
    from app.models.source import Source
    from app.database import SessionLocal as SL

    db = SL()
    try:
        if db.query(Source).count():
            return
        from app.bootstrap import DEFAULT_SOURCES

        for payload in DEFAULT_SOURCES:
            db.add(Source(**payload))
        db.commit()
    finally:
        db.close()


def _init_with_url(database_url: str) -> dict[str, Any]:
    os.environ["DATABASE_URL"] = database_url
    get_settings.cache_clear()
    reconfigure_engine()
    init_db()
    _seed_sources()
    return check_database_connection()


@st.cache_resource
def _bootstrap_database() -> dict[str, Any]:
    _apply_secrets_to_env()

    if _on_streamlit_cloud():
        return _init_with_url(CLOUD_SQLITE)

    if os.environ.get("DATABASE_URL"):
        status = _init_with_url(os.environ["DATABASE_URL"])
        if status.get("ok"):
            return status

    for url in (LOCAL_SQLITE, CLOUD_SQLITE):
        status = _init_with_url(url)
        if status.get("ok"):
            return status

    return {"ok": False, "error": "Could not initialize database"}


def _session():
    status = _bootstrap_database()
    if not status.get("ok"):
        raise RuntimeError(status.get("error") or "Database not ready")
    return SessionLocal()


def check_backend(base_url: str = "") -> dict[str, Any]:
    try:
        db_status = _bootstrap_database()
        if not db_status.get("ok"):
            return {"ok": False, "data": None, "error": db_status.get("error", "Database failed")}

        settings = get_settings()
        return {
            "ok": True,
            "data": {
                "app": settings.app_display_name,
                "app_slug": settings.app_name,
                "env": settings.runtime_environment,
                "status": "running",
                "x_posting_enabled": settings.x_posting_enabled,
                "acled_configured": settings.acled_configured,
                "database": {
                    "backend": settings.database_backend,
                    "using_supabase": settings.using_supabase,
                    "connected": True,
                    "error": None,
                },
                "supabase": {
                    "configured": settings.supabase_configured,
                    "api_ok": None,
                    "api_error": None,
                },
                "mode": "embedded",
            },
            "error": None,
        }
    except Exception as exc:
        return {"ok": False, "data": None, "error": str(exc)}


def run_collection(base_url: str = "") -> dict[str, Any]:
    try:
        db = _session()
    except Exception as exc:
        return {"ok": False, "data": None, "error": str(exc)}
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
    try:
        db = _session()
    except Exception:
        return []
    try:
        return [raw_news_to_dict(r) for r in get_recent_raw_news(db, limit=limit)]
    finally:
        db.close()


def get_incidents(base_url: str = "", limit: int = 500) -> list[dict[str, Any]]:
    try:
        db = _session()
    except Exception:
        return []
    try:
        return [incident_to_dict(r) for r in list_incidents(db, limit=limit)]
    finally:
        db.close()


def get_drafts(base_url: str = "", limit: int = 500) -> list[dict[str, Any]]:
    try:
        db = _session()
    except Exception:
        return []
    try:
        return [draft_to_dict(r) for r in list_drafts(db, limit=limit)]
    finally:
        db.close()


def approve_draft(draft_id: int, base_url: str = "") -> dict[str, Any]:
    try:
        db = _session()
    except Exception as exc:
        return {"ok": False, "data": None, "error": str(exc)}
    try:
        draft = approve_draft_record(db, draft_id)
        if not draft:
            return {"ok": False, "data": None, "error": "Draft not found"}
        return {"ok": True, "data": {"draft": draft_to_dict(draft)}, "error": None}
    finally:
        db.close()


def reject_draft(draft_id: int, base_url: str = "") -> dict[str, Any]:
    try:
        db = _session()
    except Exception as exc:
        return {"ok": False, "data": None, "error": str(exc)}
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

    try:
        db = _session()
    except Exception as exc:
        return {"ok": False, "data": None, "error": str(exc)}
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
