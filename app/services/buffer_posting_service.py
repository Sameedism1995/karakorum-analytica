"""Send approved posts directly to Buffer API (no Zapier)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from loguru import logger
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.post import Post
from app.services.buffer_service import buffer_service
from app.services.buffer_validation_service import validate_post_for_buffer


def post_to_dict(post: Post) -> dict[str, Any]:
    return {
        "id": post.id,
        "draft_post_id": post.draft_post_id,
        "status": post.status,
        "post_text": post.post_text,
        "headline": post.headline,
        "source_url": post.source_url,
        "source_name": post.source_name,
        "verification_status": post.verification_status,
        "source_grade": post.source_grade,
        "image_url": post.image_url,
        "scheduled_time": post.scheduled_time.isoformat() if post.scheduled_time else None,
        "graphic_content": post.graphic_content,
        "error_message": post.error_message,
        "risk_flags": post.risk_flags,
        "editor_notes": post.editor_notes,
        "publish_recommendation": post.publish_recommendation,
        "approved_at": post.approved_at.isoformat() if post.approved_at else None,
        "posted_at": post.posted_at.isoformat() if getattr(post, "posted_at", None) else None,
        "buffer_response": post.buffer_response,
        "sent_to_buffer_at": post.sent_to_buffer_at.isoformat() if post.sent_to_buffer_at else None,
        "failed_at": post.failed_at.isoformat() if post.failed_at else None,
        "created_at": post.created_at.isoformat() if post.created_at else None,
    }


def send_test_post() -> dict[str, Any]:
    logger.info(f"Buffer test post api_configured={buffer_service.is_configured()}")
    result = buffer_service.queue_text_post("Test post from Karakorum Analytica via Buffer API.")
    if result.get("ok"):
        return {"ok": True, "message": "Test post queued in Buffer", **result}
    return {"ok": False, "error": result.get("error") or "Buffer test failed", **result}


def send_post_to_buffer(db: Session, post_id: int) -> dict[str, Any]:
    logger.info(
        f"Buffer send requested post_id={post_id} api_configured={buffer_service.is_configured()}"
    )

    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        logger.warning(f"Buffer send post_id={post_id} validation=fail reason=not found")
        return {"ok": False, "error": "Post not found", "status": "failed"}

    ok, reason = validate_post_for_buffer(post)
    logger.info(f"Buffer send post_id={post_id} validation={'pass' if ok else 'fail'} reason={reason or 'ok'}")

    if not ok:
        _mark_failed(db, post, reason)
        return {"ok": False, "error": reason, "status": post.status, "post": post_to_dict(post)}

    db.commit()
    db.refresh(post)

    if not buffer_service.is_configured():
        reason = "BUFFER_API_KEY is not configured on the server"
        _mark_failed(db, post, reason)
        return {"ok": False, "error": reason, "status": post.status, "post": post_to_dict(post)}

    channel_id, resolution = buffer_service.resolve_channel_id()
    logger.info(
        f"Buffer send post_id={post_id} channel_id={channel_id or 'none'} "
        f"resolution_source={resolution.get('source', 'unknown')}"
    )

    buffer_result = buffer_service.queue_post_to_buffer(post.post_text, channel_id=channel_id)

    if buffer_result.get("ok"):
        post.status = "sent_to_buffer"
        post.sent_to_buffer_at = datetime.now(timezone.utc)
        post.error_message = None
        post.failed_at = None
        post.buffer_response = buffer_result.get("buffer_response") or buffer_result.get("post")
        db.commit()
        db.refresh(post)
        logger.info(f"Buffer send post_id={post_id} final_status=sent_to_buffer supabase_update=ok")
        return {
            "ok": True,
            "success": True,
            "message": "Post sent to Buffer queue",
            "status": "sent_to_buffer",
            "post": post_to_dict(post),
            "buffer_response": post.buffer_response,
            "channel_id": buffer_result.get("channel_id"),
        }

    reason = str(buffer_result.get("error") or "Buffer API request failed")
    post.buffer_response = buffer_result.get("buffer_response") or {"error": reason}
    _mark_failed(db, post, reason)
    db.commit()
    db.refresh(post)
    logger.error(f"Buffer send post_id={post_id} final_status=failed supabase_update=ok error={reason[:120]}")
    return {
        "ok": False,
        "success": False,
        "error": reason,
        "status": post.status,
        "post": post_to_dict(post),
        "buffer_response": post.buffer_response,
    }


def auto_send_approved_post(db: Session, post_id: int) -> dict[str, Any] | None:
    settings = get_settings()
    if not settings.buffer_auto_send_on_approve:
        return None
    if not buffer_service.is_configured():
        logger.warning("Auto-send skipped: BUFFER_API_KEY not configured")
        return {"ok": False, "error": "BUFFER_API_KEY is not configured", "skipped": True}
    logger.info(f"Auto-send to Buffer post_id={post_id}")
    return send_post_to_buffer(db, post_id)


def send_all_approved_posts(db: Session, *, limit: int = 50) -> dict[str, Any]:
    posts = (
        db.query(Post)
        .filter(Post.status == "approved")
        .order_by(Post.created_at.asc())
        .limit(limit)
        .all()
    )
    results: list[dict[str, Any]] = []
    sent = 0
    failed = 0
    for post in posts:
        result = send_post_to_buffer(db, post.id)
        results.append({"post_id": post.id, **result})
        if result.get("ok"):
            sent += 1
        else:
            failed += 1
    return {
        "ok": failed == 0,
        "total": len(posts),
        "sent": sent,
        "failed": failed,
        "results": results,
    }


def _mark_failed(db: Session, post: Post, reason: str) -> None:
    post.status = "failed"
    post.error_message = reason
    post.failed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(post)
    logger.info(f"Buffer send post_id={post.id} final_status=failed supabase_update=ok")
