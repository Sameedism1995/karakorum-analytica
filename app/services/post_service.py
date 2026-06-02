"""Editorial posts queue — synced from draft_posts for Buffer publishing."""

from __future__ import annotations

from loguru import logger
from sqlalchemy.orm import Session

from app.models.draft_post import DraftPost
from app.models.incident import Incident
from app.models.post import Post
from app.services.buffer_validation_service import grade_from_confidence


def _draft_status_to_post_status(draft_status: str) -> str:
    mapping = {
        "pending": "needs_review",
        "approved": "approved",
        "rejected": "failed",
        "posted": "sent_to_buffer",
    }
    return mapping.get(draft_status, "drafted")


def _incident_source_url(incident: Incident | None) -> str:
    if not incident:
        return ""
    sources = (incident.matched_sources or "").split(",")
    first = sources[0].strip() if sources else ""
    return first if first.startswith("http") else ""


def sync_post_from_draft(db: Session, draft: DraftPost, *, incident: Incident | None = None) -> Post:
    """Create or update posts row from a draft_post."""
    if incident is None:
        incident = db.query(Incident).filter(Incident.id == draft.incident_id).first()

    post = db.query(Post).filter(Post.draft_post_id == draft.id).first()
    if not post:
        post = Post(draft_post_id=draft.id)
        db.add(post)

    post.post_text = (draft.post_text or "")[:280]
    post.headline = (incident.main_title or "")[:512] if incident else post.headline
    post.source_name = (incident.matched_sources or "")[:512] if incident else post.source_name
    post.source_url = _incident_source_url(incident) or post.source_url
    post.source_grade = grade_from_confidence(float(draft.confidence_score or 0))
    if not post.verification_status:
        post.verification_status = "unverified"
    post.status = _draft_status_to_post_status(draft.status)

    if draft.status == "approved" and post.status not in ("sent_to_buffer",):
        post.status = "approved"
        post.error_message = None
        post.failed_at = None

    db.commit()
    db.refresh(post)
    logger.debug(f"Synced post id={post.id} from draft_post_id={draft.id} status={post.status}")
    return post


def get_post(db: Session, post_id: int) -> Post | None:
    return db.query(Post).filter(Post.id == post_id).first()


def get_post_by_draft_id(db: Session, draft_post_id: int) -> Post | None:
    return db.query(Post).filter(Post.draft_post_id == draft_post_id).first()


def get_or_create_post_for_draft(db: Session, draft: DraftPost) -> Post:
    post = get_post_by_draft_id(db, draft.id)
    if post:
        return sync_post_from_draft(db, draft)
    return sync_post_from_draft(db, draft)


def list_posts(db: Session, limit: int = 100) -> list[Post]:
    return db.query(Post).order_by(Post.created_at.desc()).limit(limit).all()


def backfill_posts_from_drafts(db: Session) -> int:
    """Ensure every draft_post has a posts row."""
    drafts = db.query(DraftPost).all()
    created = 0
    for draft in drafts:
        if not get_post_by_draft_id(db, draft.id):
            sync_post_from_draft(db, draft)
            created += 1
    return created


def approve_post_for_draft(db: Session, draft: DraftPost) -> Post:
    post = sync_post_from_draft(db, draft)
    post.status = "approved"
    post.error_message = None
    post.failed_at = None
    db.commit()
    db.refresh(post)
    return post
