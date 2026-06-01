from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.integrations.supabase_client import check_supabase_api, check_supabase_storage
from pydantic import BaseModel, Field

from app.services.scweet_service import (
    execute_scweet_operation,
    get_scweet_accounts,
    get_scweet_health,
    refresh_scweet_session,
    run_scweet_test_search,
)
from app.integrations.x_client import check_x_connection
from app.models.raw_news import RawNews
from app.publishers.x_publisher import post_draft_to_x
from app.services.collection_job import get_collection_job_status, start_collection_job
from app.services.collection_service import get_recent_raw_news, raw_news_to_dict
from app.services.draft_service import (
    approve_draft,
    draft_to_dict,
    get_draft,
    list_drafts,
    reject_draft,
)
from app.services.incident_service import incident_to_dict, list_incidents
from app.services.stats_service import get_dashboard_stats

router = APIRouter()
settings = get_settings()

API_SERVICE_NAME = "karakorum-analytica-api"


class ScweetRunRequest(BaseModel):
    operation: str
    params: dict = Field(default_factory=dict)


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "service": API_SERVICE_NAME}


@router.get("/")
def root() -> dict:
    from app.database import check_database_connection

    db_status = check_database_connection()
    supabase_api = check_supabase_api() if settings.supabase_configured else None
    x_status = check_x_connection() if settings.x_configured else None

    return {
        "message": "Karakorum Analytica API is running",
        "app": settings.app_display_name,
        "app_slug": settings.app_name,
        "env": settings.runtime_environment,
        "status": "running",
        "x_posting_enabled": settings.x_posting_enabled,
        "x_configured": settings.x_configured,
        "x_oauth_configured": settings.x_oauth_configured,
        "x_connection": x_status,
        "scweet": get_scweet_health(),
        "acled_configured": settings.acled_configured,
        "database": {
            "backend": settings.database_backend,
            "using_supabase": settings.using_supabase,
            "connected": db_status.get("ok", False),
            "error": db_status.get("error"),
        },
        "supabase": {
            "configured": settings.supabase_configured,
            "api_ok": supabase_api.get("ok") if supabase_api else None,
            "api_error": supabase_api.get("error") if supabase_api else None,
        },
    }


@router.get("/health/database")
def database_health() -> dict:
    from app.database import check_database_connection

    db_status = check_database_connection()
    supabase_storage = check_supabase_storage() if settings.supabase_configured else None
    return {
        "database": db_status,
        "supabase_storage": supabase_storage,
    }


@router.get("/health/x")
def x_health() -> dict:
    """Verify X (Twitter) API credentials and connection."""
    return {"x": check_x_connection()}


@router.get("/health/scweet")
def scweet_health() -> dict:
    """Scweet collector configuration and client readiness."""
    return {"scweet": get_scweet_health()}


@router.post("/scweet/session/refresh")
def scweet_refresh_session(force: bool = False) -> dict:
    """Log into X and cache session cookies for Scweet."""
    return refresh_scweet_session(force=force)


@router.post("/scweet/search/test")
def scweet_test_search(query: str = "", limit: int = 5) -> dict:
    """Run a live Scweet search (preview only, does not persist)."""
    return run_scweet_test_search(query=query or None, limit=limit)


@router.get("/scweet/accounts")
def scweet_accounts(runs_limit: int = 10) -> dict:
    """List provisioned Scweet accounts and recent runs."""
    return get_scweet_accounts(runs_limit=runs_limit)


@router.post("/scweet/run")
def scweet_run(body: ScweetRunRequest) -> dict:
    """Execute a Scweet operation (search, profile tweets, followers, following, user info)."""
    return execute_scweet_operation(body.operation, body.params)


@router.post("/collect/run")
def run_collection() -> dict:
    """Start collection in the background (returns immediately for Render/dashboard)."""
    payload = start_collection_job()
    if payload["status"] == "running" and payload.get("message") == "Collection already in progress":
        return payload
    return payload


@router.get("/collect/status")
def collection_status() -> dict:
    """Poll background collection job state."""
    return get_collection_job_status()


@router.get("/stats")
def dashboard_stats(db: Session = Depends(get_db)) -> dict:
    """Cumulative dashboard totals from the database."""
    return get_dashboard_stats(db)


@router.get("/raw-news")
def get_raw_news(limit: int = 500, db: Session = Depends(get_db)) -> dict:
    records = get_recent_raw_news(db, limit=limit)
    total = db.query(func.count(RawNews.id)).scalar() or 0
    return {
        "count": len(records),
        "total": total,
        "items": [raw_news_to_dict(r) for r in records],
    }


@router.get("/incidents")
def get_incidents(limit: int = 100, db: Session = Depends(get_db)) -> dict:
    records = list_incidents(db, limit=limit)
    return {"count": len(records), "items": [incident_to_dict(r) for r in records]}


@router.get("/drafts")
def get_drafts(limit: int = 100, db: Session = Depends(get_db)) -> dict:
    records = list_drafts(db, limit=limit)
    return {"count": len(records), "items": [draft_to_dict(r) for r in records]}


@router.post("/drafts/{draft_id}/approve")
def approve_draft_endpoint(draft_id: int, db: Session = Depends(get_db)) -> dict:
    draft = approve_draft(db, draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    return {"message": "Draft approved", "draft": draft_to_dict(draft)}


@router.post("/drafts/{draft_id}/reject")
def reject_draft_endpoint(draft_id: int, db: Session = Depends(get_db)) -> dict:
    draft = reject_draft(db, draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    return {"message": "Draft rejected", "draft": draft_to_dict(draft)}


@router.post("/drafts/{draft_id}/post")
def post_draft_endpoint(draft_id: int, db: Session = Depends(get_db)) -> dict:
    draft = get_draft(db, draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    result = post_draft_to_x(db, draft)
    if not result.get("success"):
        raise HTTPException(status_code=403, detail=result.get("error", "Posting failed"))
    return result
