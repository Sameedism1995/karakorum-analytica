from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.publishers.x_publisher import post_draft_to_x
from app.services.collection_service import collect_all, get_recent_raw_news, raw_news_to_dict
from app.services.draft_service import (
    approve_draft,
    draft_to_dict,
    generate_drafts_for_incidents,
    get_draft,
    list_drafts,
    reject_draft,
)
from app.services.incident_service import incident_to_dict, list_incidents, process_incidents

router = APIRouter()
settings = get_settings()


@router.get("/")
def root() -> dict:
    return {
        "app": settings.app_name,
        "env": settings.app_env,
        "status": "running",
        "x_posting_enabled": settings.x_posting_enabled,
        "acled_configured": settings.acled_configured,
    }


@router.post("/collect/run")
def run_collection(db: Session = Depends(get_db)) -> dict:
    stats = collect_all(db)
    incident_stats = process_incidents(db)
    draft_stats = generate_drafts_for_incidents(db)
    return {"collection": stats, "incidents": incident_stats, "drafts": draft_stats}


@router.get("/raw-news")
def get_raw_news(limit: int = 100, db: Session = Depends(get_db)) -> dict:
    records = get_recent_raw_news(db, limit=limit)
    return {"count": len(records), "items": [raw_news_to_dict(r) for r in records]}


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
