"""Buffer/X publishing via Zapier — human-approved posts only."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.services.post_service import get_post
from app.services.zapier_buffer_service import (
    send_all_approved_posts,
    send_post_to_buffer,
    send_test_payload,
)

router = APIRouter(prefix="/api", tags=["posts"])


def _require_test_access(x_admin_secret: str | None) -> None:
    settings = get_settings()
    if not settings.is_production:
        return
    secret = settings.buffer_test_secret.strip()
    if not secret:
        raise HTTPException(
            status_code=403,
            detail="Test endpoint disabled in production without BUFFER_TEST_SECRET",
        )
    if (x_admin_secret or "").strip() != secret:
        raise HTTPException(status_code=403, detail="Invalid or missing X-Admin-Secret header")


@router.post("/posts/{post_id}/send-to-buffer")
def send_to_buffer(post_id: int, db: Session = Depends(get_db)):
    """Validate and send an approved post to Buffer via Zapier. Never auto-publishes drafts."""
    result = send_post_to_buffer(db, post_id)
    if not result.get("ok"):
        return JSONResponse(status_code=400, content=result)
    return result


@router.post("/posts/send-approved-batch")
def send_approved_batch(
    limit: int = 50,
    db: Session = Depends(get_db),
    x_admin_secret: str | None = Header(default=None, alias="X-Admin-Secret"),
):
    """Send all approved posts to Buffer (admin secret required in production)."""
    _require_test_access(x_admin_secret)
    result = send_all_approved_posts(db, limit=limit)
    if not result.get("ok") and result.get("total", 0) > 0:
        return JSONResponse(status_code=400, content=result)
    return result


@router.post("/test/zapier-buffer")
def test_zapier_buffer(
    x_admin_secret: str | None = Header(default=None, alias="X-Admin-Secret"),
) -> dict:
    """Send a fixed safe test payload to Zapier (dev or admin-secret protected)."""
    _require_test_access(x_admin_secret)
    result = send_test_payload()
    if not result.get("ok"):
        raise HTTPException(status_code=503, detail=result.get("error") or "Zapier test failed")
    return result


@router.get("/posts/{post_id}")
def get_post_endpoint(post_id: int, db: Session = Depends(get_db)) -> dict:
    from app.services.zapier_buffer_service import post_to_dict

    post = get_post(db, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return {"ok": True, "post": post_to_dict(post)}
