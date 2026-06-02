"""Approve editorial posts and publish immediately to X via Buffer (shareNow)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from loguru import logger
from sqlalchemy.orm import Session

from app.models.draft_post import DraftPost
from app.models.post import Post
from app.services.buffer_posting_service import post_to_dict
from app.services.buffer_service import buffer_service
from app.services.buffer_validation_service import validate_post_for_approval


def _mark_failed(db: Session, post: Post, reason: str, *, buffer_response: Any = None) -> None:
    post.status = "failed"
    post.error_message = reason
    post.failed_at = datetime.now(timezone.utc)
    if buffer_response is not None:
        post.buffer_response = buffer_response
    db.commit()
    db.refresh(post)
    logger.info(f"Approve-and-post post_id={post.id} final_status=failed reason={reason[:120]}")


def _sync_draft_after_post(db: Session, post: Post, *, published: bool) -> None:
    if not post.draft_post_id:
        return
    draft = db.query(DraftPost).filter(DraftPost.id == post.draft_post_id).first()
    if not draft:
        return
    if published:
        draft.status = "posted"
        draft.posted_at = post.posted_at or datetime.now(timezone.utc)
        draft.approved_at = post.approved_at or draft.posted_at
    else:
        draft.status = "approved"
        draft.approved_at = post.approved_at
    db.commit()


def approve_and_post_now(db: Session, post_id: int) -> dict[str, Any]:
    """
    Validate, approve, and publish immediately to X through Buffer (shareNow).
    Does not queue. Human must trigger via dashboard approve action.
    """
    logger.info(f"Approve-and-post requested post_id={post_id}")

    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        logger.warning(f"Approve-and-post post_id={post_id} not found")
        return {"ok": False, "error": "Post not found", "status": "failed"}

    ok, reason = validate_post_for_approval(post)
    logger.info(f"Approve-and-post post_id={post_id} validation={'pass' if ok else 'fail'} reason={reason or 'ok'}")

    if not ok:
        _mark_failed(db, post, reason)
        return {
            "ok": False,
            "success": False,
            "error": reason,
            "status": post.status,
            "post": post_to_dict(post),
        }

    if not buffer_service.is_configured():
        reason = "BUFFER_API_KEY is not configured on the server"
        _mark_failed(db, post, reason)
        return {"ok": False, "success": False, "error": reason, "status": post.status, "post": post_to_dict(post)}

    now = datetime.now(timezone.utc)
    post.status = "approved"
    post.approved_at = now
    post.error_message = None
    post.failed_at = None
    db.commit()
    db.refresh(post)
    logger.info(f"Approve-and-post post_id={post_id} approved_at={post.approved_at.isoformat()}")

    channel_id, resolution = buffer_service.resolve_channel_id()
    logger.info(
        f"Approve-and-post post_id={post_id} channel_id={channel_id or 'none'} "
        f"resolution_source={resolution.get('source', 'unknown')}"
    )

    if not channel_id:
        reason = resolution.get("error") or "Buffer channel not found for @kkanalytica"
        _mark_failed(db, post, reason)
        return {"ok": False, "success": False, "error": reason, "status": post.status, "post": post_to_dict(post)}

    logger.info(f"Approve-and-post post_id={post_id} Buffer publish-now started channel_id={channel_id[:8]}…")
    buffer_result = buffer_service.post_now_to_buffer(post.post_text, channel_id=channel_id)

    if buffer_result.get("ok"):
        published_at = datetime.now(timezone.utc)
        post.status = "posted"
        post.posted_at = published_at
        post.sent_to_buffer_at = published_at
        post.error_message = None
        post.failed_at = None
        post.buffer_response = buffer_result.get("buffer_response") or buffer_result.get("post")
        db.commit()
        db.refresh(post)
        _sync_draft_after_post(db, post, published=True)
        logger.info(f"Approve-and-post post_id={post_id} final_status=posted supabase_update=ok")
        return {
            "ok": True,
            "success": True,
            "status": "posted",
            "message": "Post approved and published to X through Buffer.",
            "post": post_to_dict(post),
            "buffer_response": post.buffer_response,
            "channel_id": buffer_result.get("channel_id"),
            "publish_mode": "shareNow",
        }

    reason = str(buffer_result.get("error") or "Buffer publish-now failed")
    post.buffer_response = buffer_result.get("buffer_response") or {"error": reason}
    _mark_failed(db, post, reason)
    logger.error(f"Approve-and-post post_id={post_id} Buffer failed error={reason[:120]}")
    return {
        "ok": False,
        "success": False,
        "error": reason,
        "status": post.status,
        "post": post_to_dict(post),
        "buffer_response": post.buffer_response,
    }
