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
        draft, buffer_result = approve_draft_record(db, draft_id)
        if not draft:
            return {"ok": False, "data": None, "error": "Draft not found"}
        data: dict[str, Any] = {"draft": draft_to_dict(draft)}
        if buffer_result is not None:
            data["buffer"] = buffer_result
        return {"ok": True, "data": data, "error": None}
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


def get_spiderfoot_status(base_url: str = "") -> dict[str, Any]:
    from app.services.spiderfoot_service import get_spiderfoot_health

    return {"ok": True, "data": {"spiderfoot": get_spiderfoot_health()}}


def list_spiderfoot_scans(base_url: str = "") -> dict[str, Any]:
    from app.services.spiderfoot_service import list_scans

    return list_scans()


def get_spiderfoot_scan(base_url: str = "", scan_id: str = "") -> dict[str, Any]:
    from app.services.spiderfoot_service import get_scan

    return get_scan(scan_id)


def get_spiderfoot_scan_results(
    base_url: str = "",
    scan_id: str = "",
    *,
    event_type: str = "",
    unique: bool = False,
    limit: int = 500,
) -> dict[str, Any]:
    from app.services.spiderfoot_service import get_scan_results

    return get_scan_results(scan_id, event_type=event_type, unique=unique, limit=limit)


def start_spiderfoot_scan(
    base_url: str = "",
    *,
    scan_name: str = "",
    target: str = "",
    usecase: str = "passive",
    module_list: str = "",
    type_list: str = "",
) -> dict[str, Any]:
    from app.services.spiderfoot_service import start_scan

    return start_scan(
        scan_name=scan_name,
        target=target,
        usecase=usecase,
        module_list=module_list,
        type_list=type_list,
    )


def stop_spiderfoot_scan(base_url: str = "", scan_id: str = "") -> dict[str, Any]:
    from app.services.spiderfoot_service import stop_scan

    return stop_scan(scan_id)


def delete_spiderfoot_scan(base_url: str = "", scan_id: str = "") -> dict[str, Any]:
    from app.services.spiderfoot_service import delete_scan

    return delete_scan(scan_id)


def list_spiderfoot_modules(base_url: str = "") -> dict[str, Any]:
    from app.services.spiderfoot_service import list_modules

    return list_modules()


def get_llm_health(base_url: str = "") -> dict[str, Any]:
    from app.services.draft_llm_service import get_llm_health as _health

    return {"ok": True, "data": {"llm": _health()}}


def update_draft(base_url: str, draft_id: int, post_text: str) -> dict[str, Any]:
    from app.services.draft_service import draft_to_dict, update_draft_text

    try:
        db = _session()
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    try:
        draft = update_draft_text(db, draft_id, post_text)
        if not draft:
            return {"ok": False, "error": "Draft not found or not editable"}
        return {"ok": True, "draft": draft_to_dict(draft)}
    finally:
        db.close()


def regenerate_draft(
    base_url: str,
    draft_id: int,
    *,
    tone: str = "neutral",
) -> dict[str, Any]:
    from app.services.draft_service import regenerate_draft_with_llm

    try:
        db = _session()
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    try:
        result = regenerate_draft_with_llm(db, draft_id, tone=tone)
        if not result:
            return {"ok": False, "error": "Draft or incident not found"}
        return {"ok": True, **result}
    finally:
        db.close()


def audit_draft(base_url: str, draft_id: int) -> dict[str, Any]:
    from app.models.incident import Incident
    from app.services.draft_llm_service import audit_draft_text, incident_to_raw_text
    from app.services.draft_service import get_draft

    try:
        db = _session()
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    try:
        draft = get_draft(db, draft_id)
        if not draft:
            return {"ok": False, "error": "Draft not found"}
        incident = db.query(Incident).filter(Incident.id == draft.incident_id).first()
        raw = incident_to_raw_text(incident) if incident else ""
        source = ""
        location = ""
        incident_type = ""
        if incident:
            source = f"Confidence {incident.confidence_score:.0f}%; {incident.matched_sources or ''}"
            location = ", ".join(p for p in [incident.city, incident.province] if p)
            incident_type = incident.event_type or ""
        return {
            "ok": True,
            "audit": audit_draft_text(
                draft.post_text or "",
                source_info=source,
                raw_report=raw,
                db=db,
                location=location,
                incident_type=incident_type,
            ),
        }
    finally:
        db.close()


def llm_generate_post(base_url: str, payload: dict[str, Any]) -> dict[str, Any]:
    from app.schemas.llm_dashboard import GeneratePostRequest
    from app.services.llm_newsroom_service import generate_post

    try:
        body = GeneratePostRequest(**payload)
        return {"ok": True, "data": generate_post(body).model_dump()}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def llm_audit_post(
    base_url: str,
    *,
    draft_post: str,
    raw_report: str = "",
    source_information: str = "",
) -> dict[str, Any]:
    from app.schemas.llm_dashboard import AuditPostRequest
    from app.services.llm_newsroom_service import audit_post

    try:
        result = audit_post(
            AuditPostRequest(
                draft_post=draft_post,
                raw_report_text=raw_report,
                source_information=source_information,
            )
        )
        return {"ok": True, "data": result.model_dump()}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def draft_newsroom_post_local(base_url: str, payload: dict[str, Any]) -> dict[str, Any]:
    from app.database import SessionLocal
    from app.schemas.local_newsroom import NewsroomDraftRequest
    from app.services.local_llm_service import local_llm_service

    try:
        db = SessionLocal()
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    try:
        body = NewsroomDraftRequest(**payload)
        result = local_llm_service.draft_newsroom_post(db, body)
        return {"ok": True, "data": result.model_dump()}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    finally:
        db.close()


def audit_source_local(base_url: str, payload: dict[str, Any]) -> dict[str, Any]:
    from app.schemas.local_newsroom import NewsroomAuditRequest
    from app.services.local_llm_service import local_llm_service

    try:
        body = NewsroomAuditRequest(**payload)
        result = local_llm_service.audit_source(body)
        return {"ok": True, "data": result.model_dump()}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def save_training_example(base_url: str, payload: dict[str, Any]) -> dict[str, Any]:
    from app.database import SessionLocal
    from app.schemas.local_newsroom import SaveTrainingExampleRequest
    from app.services.local_llm_service import local_llm_service

    try:
        db = SessionLocal()
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    try:
        body = SaveTrainingExampleRequest(**payload)
        row = local_llm_service.save_training_example(db, body)
        return {"ok": True, "id": row.id}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    finally:
        db.close()


def export_training_jsonl(base_url: str) -> dict[str, Any]:
    from app.database import SessionLocal
    from app.services.local_llm_service import local_llm_service

    try:
        db = SessionLocal()
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    try:
        content = local_llm_service.export_training_jsonl(db)
        return {"ok": True, "content": content}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    finally:
        db.close()


def send_approved_batch(base_url: str, *, limit: int = 50) -> dict[str, Any]:
    from app.database import SessionLocal
    from app.services.buffer_posting_service import send_all_approved_posts

    try:
        db = SessionLocal()
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    try:
        return send_all_approved_posts(db, limit=limit)
    finally:
        db.close()


def send_post_to_buffer(base_url: str, post_id: int) -> dict[str, Any]:
    from app.database import SessionLocal
    from app.services.buffer_posting_service import send_post_to_buffer as _send

    try:
        db = SessionLocal()
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    try:
        return _send(db, post_id)
    finally:
        db.close()


def test_buffer(base_url: str = "", *, admin_secret: str = "") -> dict[str, Any]:
    from app.services.buffer_posting_service import send_test_post

    return send_test_post()


def get_buffer_channels(base_url: str = "") -> dict[str, Any]:
    from app.services.buffer_service import buffer_service

    return buffer_service.discover_channels_payload()


def get_ollama_health(base_url: str = "") -> dict[str, Any]:
    from app.services.local_llm_service import get_ollama_health as _health

    return {"ok": True, "data": _health()}


def get_buffer_health(base_url: str = "") -> dict[str, Any]:
    from app.services.buffer_service import get_buffer_health as _health

    return {"ok": True, "data": _health()}


def get_supabase_health(base_url: str = "") -> dict[str, Any]:
    from app.database import check_database_connection
    from app.config import get_settings

    db = check_database_connection()
    settings = get_settings()
    return {
        "ok": True,
        "data": {
            "connected": db.get("ok", False),
            "backend": db.get("backend"),
            "using_supabase": db.get("using_supabase", False),
            "supabase_url_configured": bool(settings.supabase_url.strip()),
            "error": db.get("error"),
        },
    }


def draft_local_post(base_url: str, payload: dict[str, Any]) -> dict[str, Any]:
    from app.database import SessionLocal
    from app.schemas.local_newsroom import LocalDraftRequest
    from app.services.local_llm_service import local_llm_service

    try:
        db = SessionLocal()
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    try:
        body = LocalDraftRequest(**payload)
        result = local_llm_service.draft_local(db, body)
        return {"ok": True, "data": result.model_dump()}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    finally:
        db.close()


def approve_post(base_url: str, post_id: int) -> dict[str, Any]:
    from app.database import SessionLocal
    from app.services.post_service import approve_post_by_id
    from app.services.buffer_posting_service import post_to_dict

    try:
        db = SessionLocal()
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    try:
        post = approve_post_by_id(db, post_id)
        return {"ok": True, "post": post_to_dict(post)}
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    finally:
        db.close()


def run_e2e_pipeline(base_url: str = "", *, dry_run: bool = True, admin_secret: str = "") -> dict[str, Any]:
    from app.database import SessionLocal
    from app.services.e2e_pipeline_service import run_e2e_local_to_buffer

    try:
        db = SessionLocal()
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    try:
        return run_e2e_local_to_buffer(db, dry_run=dry_run)
    finally:
        db.close()
