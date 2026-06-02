from datetime import datetime, timezone

from loguru import logger
from sqlalchemy.orm import Session, joinedload

from app.models.draft_post import DraftPost
from app.models.incident import Incident
from app.processors.post_generator import generate_draft_post
from app.services.draft_llm_service import generate_post_text_for_incident, incident_to_raw_text
from app.services.post_service import approve_post_for_draft, sync_post_from_draft


def generate_drafts_for_incidents(db: Session) -> dict[str, int]:
    """Create draft posts for incidents that do not yet have a pending draft."""
    incidents = db.query(Incident).all()
    created = 0

    for incident in incidents:
        existing = (
            db.query(DraftPost)
            .filter(DraftPost.incident_id == incident.id)
            .filter(DraftPost.status.in_(["pending", "approved"]))
            .first()
        )
        if existing:
            continue

        post_text, _meta = generate_post_text_for_incident(db, incident)

        draft = DraftPost(
            incident_id=incident.id,
            post_text=post_text,
            keywords=incident.keywords,
            confidence_score=incident.confidence_score,
            status="pending",
        )
        db.add(draft)
        db.flush()
        sync_post_from_draft(db, draft)
        created += 1

    db.commit()
    logger.info(f"Draft posts created: {created}")
    return {"drafts_created": created}


def list_drafts(db: Session, limit: int = 100) -> list[DraftPost]:
    return (
        db.query(DraftPost)
        .options(joinedload(DraftPost.post))
        .order_by(DraftPost.created_at.desc())
        .limit(limit)
        .all()
    )


def get_draft(db: Session, draft_id: int) -> DraftPost | None:
    return (
        db.query(DraftPost)
        .options(joinedload(DraftPost.post))
        .filter(DraftPost.id == draft_id)
        .first()
    )


def approve_draft(db: Session, draft_id: int) -> DraftPost | None:
    draft = get_draft(db, draft_id)
    if not draft:
        return None
    draft.status = "approved"
    draft.approved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(draft)
    approve_post_for_draft(db, draft)
    return draft


def reject_draft(db: Session, draft_id: int) -> DraftPost | None:
    draft = get_draft(db, draft_id)
    if not draft:
        return None
    draft.status = "rejected"
    db.commit()
    db.refresh(draft)
    return draft


def update_draft_text(db: Session, draft_id: int, post_text: str) -> DraftPost | None:
    draft = get_draft(db, draft_id)
    if not draft:
        return None
    if draft.status not in ("pending", "approved"):
        return None
    draft.post_text = post_text.strip()[:280]
    db.commit()
    db.refresh(draft)
    sync_post_from_draft(db, draft)
    return draft


def regenerate_draft_with_llm(
    db: Session,
    draft_id: int,
    *,
    tone: str = "neutral",
) -> dict | None:
    draft = get_draft(db, draft_id)
    if not draft:
        return None
    incident = db.query(Incident).filter(Incident.id == draft.incident_id).first()
    if not incident:
        return None
    post_text, meta = generate_post_text_for_incident(db, incident, tone=tone)
    draft.post_text = post_text
    draft.status = "pending"
    db.commit()
    db.refresh(draft)
    sync_post_from_draft(db, draft)
    return {"draft": draft_to_dict(draft), "llm": meta}


def draft_to_dict(draft: DraftPost, *, post=None) -> dict:
    post_row = post if post is not None else getattr(draft, "post", None)
    payload = {
        "id": draft.id,
        "incident_id": draft.incident_id,
        "post_text": draft.post_text,
        "keywords": draft.keywords,
        "confidence_score": draft.confidence_score,
        "status": draft.status,
        "created_at": draft.created_at.isoformat(),
        "approved_at": draft.approved_at.isoformat() if draft.approved_at else None,
        "posted_at": draft.posted_at.isoformat() if draft.posted_at else None,
        "x_post_id": draft.x_post_id,
    }
    if post_row is not None:
        payload.update(
            {
                "post_id": post_row.id,
                "publish_status": post_row.status,
                "headline": post_row.headline,
                "source_url": post_row.source_url,
                "source_name": post_row.source_name,
                "verification_status": post_row.verification_status,
                "source_grade": post_row.source_grade,
                "error_message": post_row.error_message,
                "sent_to_buffer_at": post_row.sent_to_buffer_at.isoformat() if post_row.sent_to_buffer_at else None,
                "failed_at": post_row.failed_at.isoformat() if post_row.failed_at else None,
            }
        )
    return payload
