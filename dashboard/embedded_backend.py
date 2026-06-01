"""Run Karakorum Analytica pipeline in-process (for Streamlit Cloud without Render API)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import streamlit as st

from app.config import get_settings
from app.database import SessionLocal, check_database_connection, init_db, reconfigure_engine
from app.services.scweet_service import (
    execute_scweet_operation as execute_scweet_operation_service,
    get_scweet_accounts as get_scweet_accounts_service,
    get_scweet_health,
    refresh_scweet_session as refresh_scweet_session_service,
    run_scweet_test_search as run_scweet_test_search_service,
)
from app.integrations.x_client import check_x_connection
from app.services.collection_service import get_recent_raw_news, raw_news_to_dict
from app.services.draft_service import (
    approve_draft as approve_draft_record,
    draft_to_dict,
    list_drafts,
    reject_draft as reject_draft_record,
)
from app.services.incident_service import incident_to_dict, list_incidents
from app.services.stats_service import get_dashboard_stats

CLOUD_SQLITE = "sqlite:////tmp/karakorum-analytica.db"
LOCAL_SQLITE = "sqlite:///./local.db"


def _on_render() -> bool:
    return bool(os.environ.get("RENDER"))


def _database_config_fingerprint() -> str:
    """Cache key so a changed SUPABASE_DB_URL re-initializes the engine."""
    return "|".join(
        [
            os.environ.get("SUPABASE_DB_URL", "").strip(),
            os.environ.get("DATABASE_URL", "").strip(),
            "render" if _on_render() else "local",
        ]
    )


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
            "SCWEET_ENABLED",
            "SCWEET_USERNAME",
            "SCWEET_PASSWORD",
            "SCWEET_EMAIL",
            "SCWEET_AUTH_TOKEN",
            "SCWEET_AUTO_LOGIN",
            "SCWEET_LOGIN_HEADLESS",
            "SCWEET_SESSION_CACHE_PATH",
            "SCWEET_DB_PATH",
            "SUPABASE_DB_URL",
            "DATABASE_URL",
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
def _bootstrap_database(_config_fingerprint: str) -> dict[str, Any]:
    del _config_fingerprint  # only used to bust cache when env changes
    _apply_secrets_to_env()

    supabase_url = os.environ.get("SUPABASE_DB_URL", "").strip()
    if supabase_url:
        status = _init_with_url(supabase_url)
        if status.get("ok"):
            status["persistent"] = True
            return status
        if _on_render():
            return {
                "ok": False,
                "persistent": False,
                "error": f"Supabase connection failed: {status.get('error')}. "
                "Check SUPABASE_DB_URL on the Render dashboard service.",
            }

    if _on_render():
        return {
            "ok": False,
            "persistent": False,
            "error": (
                "SUPABASE_DB_URL is not set on this Render service. "
                "Add the same Postgres URL as karakorum-analytica-api so the watch list "
                "and collected tweets persist."
            ),
        }

    if _on_streamlit_cloud():
        status = _init_with_url(CLOUD_SQLITE)
        status["persistent"] = False
        return status

    if os.environ.get("DATABASE_URL"):
        status = _init_with_url(os.environ["DATABASE_URL"])
        if status.get("ok"):
            settings = get_settings()
            status["persistent"] = settings.using_supabase
            return status

    for url in (LOCAL_SQLITE, CLOUD_SQLITE):
        status = _init_with_url(url)
        if status.get("ok"):
            status["persistent"] = url.startswith("postgresql")
            return status

    return {"ok": False, "persistent": False, "error": "Could not initialize database"}


def get_database_status() -> dict[str, Any]:
    """Current DB connection info for dashboard UI."""
    status = _bootstrap_database(_database_config_fingerprint())
    settings = get_settings()
    return {
        **status,
        "backend": settings.database_backend,
        "using_supabase": settings.using_supabase,
        "on_render": _on_render(),
    }


def _session():
    status = _bootstrap_database(_database_config_fingerprint())
    if not status.get("ok"):
        raise RuntimeError(status.get("error") or "Database not ready")
    return SessionLocal()


def check_backend(base_url: str = "") -> dict[str, Any]:
    try:
        db_status = _bootstrap_database(_database_config_fingerprint())
        if not db_status.get("ok"):
            return {"ok": False, "data": None, "error": db_status.get("error", "Database failed")}

        settings = get_settings()
        scweet = get_scweet_health()

        return {
            "ok": True,
            "data": {
                "app": settings.app_display_name,
                "app_slug": settings.app_name,
                "env": settings.runtime_environment,
                "status": "running",
                "x_posting_enabled": settings.x_posting_enabled,
                "x_configured": settings.x_configured,
                "x_oauth_configured": settings.x_oauth_configured,
                "x_connection": check_x_connection() if settings.x_configured else None,
                "scweet": scweet,
                "database_persistent": db_status.get("persistent", settings.using_supabase),
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
    from app.services.collection_job import start_collection_job

    try:
        payload = start_collection_job()
        return {"ok": True, "data": payload, "error": None, "async": True}
    except Exception as exc:
        return {"ok": False, "data": None, "error": str(exc)}


def get_collection_status(base_url: str = "") -> dict[str, Any]:
    from app.services.collection_job import get_collection_job_status

    try:
        return {"ok": True, "data": get_collection_job_status(), "error": None}
    except Exception as exc:
        return {"ok": False, "data": None, "error": str(exc)}


def get_stats(base_url: str = "") -> dict[str, Any]:
    try:
        db = _session()
    except Exception as exc:
        return {"ok": False, "data": None, "error": str(exc)}
    try:
        return {"ok": True, "data": get_dashboard_stats(db), "error": None}
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


def get_scweet_status(base_url: str = "") -> dict[str, Any]:
    try:
        return {"ok": True, "data": {"scweet": get_scweet_health()}, "error": None}
    except Exception as exc:
        return {"ok": False, "data": None, "error": str(exc)}


def refresh_scweet_session(base_url: str = "", *, force: bool = False) -> dict[str, Any]:
    try:
        return refresh_scweet_session_service(force=force)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def run_scweet_test_search(
    base_url: str = "",
    *,
    query: str = "",
    limit: int = 5,
) -> dict[str, Any]:
    try:
        return run_scweet_test_search_service(query=query or None, limit=limit)
    except Exception as exc:
        return {"ok": False, "error": str(exc), "items": []}


def get_scweet_accounts(base_url: str = "", *, runs_limit: int = 10) -> dict[str, Any]:
    try:
        return get_scweet_accounts_service(runs_limit=runs_limit)
    except Exception as exc:
        return {"ok": False, "error": str(exc), "accounts": [], "runs": []}


def get_x_watch_list(base_url: str = "") -> dict[str, Any]:
    from app.services.x_watch_service import list_watch_accounts

    try:
        db = _session()
    except Exception as exc:
        return {"ok": False, "error": str(exc), "items": []}
    try:
        items = list_watch_accounts(db)
        return {"ok": True, "count": len(items), "items": items}
    finally:
        db.close()


def add_x_watch_account(base_url: str = "", *, handle: str) -> dict[str, Any]:
    from app.services.x_watch_service import add_watch_account

    try:
        db = _session()
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    try:
        return add_watch_account(db, handle)
    finally:
        db.close()


def remove_x_watch_account(base_url: str = "", *, handle: str) -> dict[str, Any]:
    from app.services.x_watch_service import remove_watch_account

    try:
        db = _session()
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    try:
        return remove_watch_account(db, handle)
    finally:
        db.close()


def fetch_x_watch_account(
    base_url: str = "",
    *,
    handle: str,
    limit: int = 50,
) -> dict[str, Any]:
    from app.services.x_watch_service import fetch_watch_account

    try:
        db = _session()
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    try:
        return fetch_watch_account(db, handle, limit=limit)
    finally:
        db.close()


def fetch_all_x_watch_accounts(base_url: str = "") -> dict[str, Any]:
    from app.services.x_watch_service import collect_all_watch_accounts

    try:
        db = _session()
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    try:
        stats = collect_all_watch_accounts(db)
        return {"ok": True, **stats}
    finally:
        db.close()


def run_scweet_operation(
    base_url: str = "",
    *,
    operation: str,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from app.services.scweet_persist_service import persist_scweet_items

    payload = params or {}
    try:
        db = _session()
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    try:
        result = execute_scweet_operation_service(operation, payload)
        if result.get("ok") and payload.get("persist") and result.get("items"):
            result["persist"] = persist_scweet_items(
                db,
                result["items"],
                apply_pipeline_filters=bool(payload.get("apply_pipeline_filters")),
            )
        return result
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    finally:
        db.close()
