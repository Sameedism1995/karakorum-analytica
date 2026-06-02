"""Send approved posts to Buffer via Zapier webhook."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx
from loguru import logger
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.post import Post
from app.services.buffer_validation_service import validate_post_for_buffer


def _webhook_configured() -> bool:
    return bool(get_settings().zapier_buffer_webhook_url.strip())


def build_zapier_payload(post: Post) -> dict[str, Any]:
    scheduled = ""
    if post.scheduled_time:
        scheduled = post.scheduled_time.astimezone(timezone.utc).isoformat()
    return {
        "post_id": post.id,
        "post_text": post.post_text,
        "headline": post.headline or "",
        "source_url": post.source_url or "",
        "source_name": post.source_name or "",
        "verification_status": post.verification_status or "",
        "source_grade": post.source_grade or "",
        "image_url": "",
        "scheduled_time": scheduled,
    }


def send_test_payload() -> dict[str, Any]:
    """Send fixed safe test payload to Zapier."""
    settings = get_settings()
    url = settings.zapier_buffer_webhook_url.strip()
    if not url:
        return {"ok": False, "error": "ZAPIER_BUFFER_WEBHOOK_URL is not configured"}

    payload = {
        "post_id": "test-001",
        "post_text": "Test post from Karakorum Analytica via Zapier and Buffer.",
        "headline": "Test post",
        "source_url": "https://example.com",
        "source_name": "Internal test",
        "verification_status": "approved",
        "source_grade": "A",
        "image_url": "",
        "scheduled_time": "",
    }
    logger.info("Zapier buffer test: webhook configured=yes post_id=test-001")
    return _post_to_zapier(url, payload)


def send_post_to_buffer(db: Session, post_id: int) -> dict[str, Any]:
    settings = get_settings()
    url = settings.zapier_buffer_webhook_url.strip()

    logger.info(f"Buffer send requested post_id={post_id} webhook_configured={bool(url)}")

    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        logger.warning(f"Buffer send post_id={post_id} validation=fail reason=not found")
        return {"ok": False, "error": "Post not found", "status": "failed"}

    ok, reason = validate_post_for_buffer(post)
    logger.info(f"Buffer send post_id={post_id} validation={'pass' if ok else 'fail'} reason={reason or 'ok'}")

    if not ok:
        _mark_failed(db, post, reason)
        return {"ok": False, "error": reason, "status": post.status, "post": post_to_dict(post)}

    if not url:
        reason = "ZAPIER_BUFFER_WEBHOOK_URL is not configured on the server"
        _mark_failed(db, post, reason)
        return {"ok": False, "error": reason, "status": post.status, "post": post_to_dict(post)}

    payload = build_zapier_payload(post)
    zapier_result = _post_to_zapier(url, payload)

    if zapier_result.get("ok"):
        post.status = "sent_to_buffer"
        post.sent_to_buffer_at = datetime.now(timezone.utc)
        post.error_message = None
        post.failed_at = None
        post.zapier_response = zapier_result.get("response") or {}
        db.commit()
        db.refresh(post)
        logger.info(
            f"Buffer send post_id={post_id} zapier_status={zapier_result.get('http_status')} "
            f"final_status=sent_to_buffer supabase_update=ok"
        )
        return {
            "ok": True,
            "message": "Post sent to Buffer via Zapier",
            "status": post.status,
            "post": post_to_dict(post),
            "zapier": {
                "http_status": zapier_result.get("http_status"),
                "response": zapier_result.get("response"),
            },
        }

    reason = str(zapier_result.get("error") or "Zapier webhook failed")
    _mark_failed(db, post, reason)
    post.zapier_response = zapier_result.get("response") or {"error": reason}
    db.commit()
    db.refresh(post)
    logger.error(
        f"Buffer send post_id={post_id} zapier_status={zapier_result.get('http_status')} "
        f"final_status=failed supabase_update=ok error={reason[:120]}"
    )
    return {
        "ok": False,
        "error": reason,
        "status": post.status,
        "post": post_to_dict(post),
        "zapier": {
            "http_status": zapier_result.get("http_status"),
            "response": zapier_result.get("response"),
        },
    }


def _mark_failed(db: Session, post: Post, reason: str) -> None:
    post.status = "failed"
    post.error_message = reason
    post.failed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(post)
    logger.info(f"Buffer send post_id={post.id} final_status=failed supabase_update=ok")


def _post_to_zapier(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        response = httpx.post(url, json=payload, timeout=30.0)
        http_status = response.status_code
        try:
            body: Any = response.json()
        except Exception:
            body = response.text

        if 200 <= http_status < 300:
            logger.info(f"Zapier webhook success http_status={http_status}")
            return {"ok": True, "http_status": http_status, "response": body}

        error = f"Zapier returned HTTP {http_status}"
        logger.warning(f"Zapier webhook failed http_status={http_status}")
        return {"ok": False, "http_status": http_status, "response": body, "error": error}
    except httpx.RequestError as exc:
        logger.error(f"Zapier webhook request error: {exc}")
        return {"ok": False, "http_status": None, "response": {"error": str(exc)}, "error": str(exc)}


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
        "zapier_response": post.zapier_response,
        "sent_to_buffer_at": post.sent_to_buffer_at.isoformat() if post.sent_to_buffer_at else None,
        "failed_at": post.failed_at.isoformat() if post.failed_at else None,
        "created_at": post.created_at.isoformat() if post.created_at else None,
    }
