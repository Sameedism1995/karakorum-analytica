from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.integrations.supabase_client import check_supabase_api, check_supabase_storage
from pydantic import BaseModel, Field

from app.services.scweet_persist_service import persist_scweet_items
from app.services.scweet_service import (
    execute_scweet_operation,
    get_scweet_accounts,
    get_scweet_health,
    refresh_scweet_session,
    run_scweet_test_search,
)
from app.services.x_watch_service import (
    add_watch_account,
    fetch_watch_account,
    list_watch_accounts,
    remove_watch_account,
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
from app.integrations.supabase_read_service import (
    add_watch_account_rest,
    fetch_dashboard_stats_rest,
    fetch_drafts_rest,
    fetch_incidents_rest,
    fetch_raw_news_rest,
    fetch_watch_accounts_rest,
    remove_watch_account_rest,
)
from app.services.db_read_fallback import sql_or_rest
from app.services.incident_service import incident_to_dict, list_incidents
from app.services.stats_service import get_dashboard_stats
from app.services.spiderfoot_service import (
    delete_scan as delete_spiderfoot_scan,
    get_scan as get_spiderfoot_scan,
    get_scan_results as get_spiderfoot_scan_results,
    get_spiderfoot_health,
    list_modules as list_spiderfoot_modules,
    list_scans as list_spiderfoot_scans,
    start_scan as start_spiderfoot_scan,
    stop_scan as stop_spiderfoot_scan,
)

router = APIRouter()
settings = get_settings()

API_SERVICE_NAME = "karakorum-analytica-api"


class ScweetRunRequest(BaseModel):
    operation: str
    params: dict = Field(default_factory=dict)


class WatchAccountRequest(BaseModel):
    handle: str = Field(..., min_length=1, max_length=256)


class SpiderFootScanRequest(BaseModel):
    scan_name: str = Field(default="", max_length=256)
    target: str = Field(..., min_length=1, max_length=512)
    usecase: str = Field(default="passive")
    module_list: str = Field(default="")
    type_list: str = Field(default="")


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


@router.get("/scweet/watch")
def scweet_watch_list(db: Session = Depends(get_db)) -> dict:
    """List watched X profiles with last extraction time."""
    return sql_or_rest(
        lambda: {"ok": True, "count": len(items := list_watch_accounts(db)), "items": items},
        fetch_watch_accounts_rest,
    )


@router.post("/scweet/watch")
def scweet_watch_add(body: WatchAccountRequest, db: Session = Depends(get_db)) -> dict:
    """Add an X handle to the watch list."""
    return sql_or_rest(
        lambda: add_watch_account(db, body.handle),
        lambda: add_watch_account_rest(body.handle),
    )


@router.delete("/scweet/watch/{handle}")
def scweet_watch_remove(handle: str, db: Session = Depends(get_db)) -> dict:
    """Remove an X handle from the watch list."""
    return sql_or_rest(
        lambda: remove_watch_account(db, handle),
        lambda: remove_watch_account_rest(handle),
    )


@router.post("/scweet/watch/{handle}/fetch")
def scweet_watch_fetch(
    handle: str,
    limit: int = 50,
    db: Session = Depends(get_db),
) -> dict:
    """Fetch one watched profile now and save tweets to the database."""
    from app.database import check_database_connection

    if not check_database_connection().get("ok"):
        raise HTTPException(
            status_code=503,
            detail=(
                "Postgres is unreachable from this server. Set SUPABASE_DB_POOLER_URL "
                "on the API service (Supabase → Connect → Session pooler, port 5432), "
                "then redeploy."
            ),
        )
    return fetch_watch_account(db, handle, limit=limit)


@router.post("/scweet/watch/fetch-all")
def scweet_watch_fetch_all(db: Session = Depends(get_db)) -> dict:
    """Fetch all enabled watched profiles and save tweets."""
    from app.database import check_database_connection
    from app.services.x_watch_service import collect_all_watch_accounts

    if not check_database_connection().get("ok"):
        raise HTTPException(
            status_code=503,
            detail=(
                "Postgres is unreachable. Configure SUPABASE_DB_POOLER_URL on the API "
                "service to enable saving fetched tweets."
            ),
        )
    stats = collect_all_watch_accounts(db)
    return {"ok": True, **stats}


@router.post("/scweet/run")
def scweet_run(body: ScweetRunRequest, db: Session = Depends(get_db)) -> dict:
    """Execute a Scweet operation (search, profile tweets, followers, following, user info)."""
    result = execute_scweet_operation(body.operation, body.params)
    if result.get("ok") and body.params.get("persist") and result.get("items"):
        apply_filters = bool(body.params.get("apply_pipeline_filters"))
        result["persist"] = persist_scweet_items(
            db,
            result["items"],
            apply_pipeline_filters=apply_filters,
        )
    return result


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
    return sql_or_rest(
        lambda: get_dashboard_stats(db),
        fetch_dashboard_stats_rest,
    )


@router.get("/raw-news")
def get_raw_news(limit: int = 500, db: Session = Depends(get_db)) -> dict:
    def _sql() -> dict:
        records = get_recent_raw_news(db, limit=limit)
        total = db.query(func.count(RawNews.id)).scalar() or 0
        return {
            "count": len(records),
            "total": total,
            "items": [raw_news_to_dict(r) for r in records],
        }

    return sql_or_rest(_sql, lambda: fetch_raw_news_rest(limit=limit))


@router.get("/incidents")
def get_incidents(limit: int = 100, db: Session = Depends(get_db)) -> dict:
    return sql_or_rest(
        lambda: {
            "count": len(records := list_incidents(db, limit=limit)),
            "items": [incident_to_dict(r) for r in records],
        },
        lambda: fetch_incidents_rest(limit=limit),
    )


@router.get("/drafts")
def get_drafts(limit: int = 100, db: Session = Depends(get_db)) -> dict:
    return sql_or_rest(
        lambda: {
            "count": len(records := list_drafts(db, limit=limit)),
            "items": [draft_to_dict(r) for r in records],
        },
        lambda: fetch_drafts_rest(limit=limit),
    )


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


@router.get("/health/spiderfoot")
def spiderfoot_health() -> dict:
    """SpiderFoot web server readiness."""
    return {"spiderfoot": get_spiderfoot_health()}


@router.get("/spiderfoot/scans")
def spiderfoot_list_scans() -> dict:
    return list_spiderfoot_scans()


@router.get("/spiderfoot/scans/{scan_id}")
def spiderfoot_get_scan(scan_id: str) -> dict:
    result = get_spiderfoot_scan(scan_id)
    if not result.get("ok"):
        raise HTTPException(status_code=404, detail=result.get("error", "Scan not found"))
    return result


@router.get("/spiderfoot/scans/{scan_id}/results")
def spiderfoot_scan_results(
    scan_id: str,
    event_type: str = "",
    unique: bool = False,
    limit: int = 500,
) -> dict:
    result = get_spiderfoot_scan_results(
        scan_id,
        event_type=event_type,
        unique=unique,
        limit=limit,
    )
    if not result.get("ok"):
        raise HTTPException(status_code=502, detail=result.get("error", "Results unavailable"))
    return result


@router.post("/spiderfoot/scans")
def spiderfoot_start_scan(body: SpiderFootScanRequest) -> dict:
    result = start_spiderfoot_scan(
        scan_name=body.scan_name,
        target=body.target,
        usecase=body.usecase,
        module_list=body.module_list,
        type_list=body.type_list,
    )
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error", "Scan failed to start"))
    return result


@router.post("/spiderfoot/scans/{scan_id}/stop")
def spiderfoot_stop_scan(scan_id: str) -> dict:
    result = stop_spiderfoot_scan(scan_id)
    if not result.get("ok"):
        raise HTTPException(status_code=502, detail=result.get("error", "Stop failed"))
    return {"ok": True, "data": result.get("data")}


@router.delete("/spiderfoot/scans/{scan_id}")
def spiderfoot_delete_scan(scan_id: str) -> dict:
    result = delete_spiderfoot_scan(scan_id)
    if not result.get("ok"):
        raise HTTPException(status_code=502, detail=result.get("error", "Delete failed"))
    return {"ok": True, "data": result.get("data")}


@router.get("/spiderfoot/modules")
def spiderfoot_modules() -> dict:
    result = list_spiderfoot_modules()
    if not result.get("ok"):
        raise HTTPException(status_code=502, detail=result.get("error", "Modules unavailable"))
    return result
