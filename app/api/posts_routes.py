"""Buffer/X publishing via direct Buffer API — human-approved posts only."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.services.buffer_posting_service import (
    post_to_dict,
    send_all_approved_posts,
    send_post_to_buffer,
    send_test_post,
)
from app.services.buffer_service import buffer_service
from app.services.post_service import get_post

router = APIRouter(prefix="/api", tags=["buffer", "posts"])


def _require_test_access(x_admin_secret: str | None) -> None:
    settings = get_settings()
    if not settings.is_production:
        return
    secret = settings.effective_admin_test_secret
    if not secret:
        raise HTTPException(
            status_code=403,
            detail="Test endpoint disabled in production without ADMIN_TEST_SECRET or BUFFER_TEST_SECRET",
        )
    if (x_admin_secret or "").strip() != secret:
        raise HTTPException(status_code=403, detail="Invalid or missing X-Admin-Secret header")


@router.get("/buffer/channels")
def list_buffer_channels() -> dict:
    """List Buffer channels and matched @kkanalytica profile (never exposes API key)."""
    return buffer_service.discover_channels_payload()


@router.post("/posts/{post_id}/send-to-buffer")
def send_to_buffer(post_id: int, db: Session = Depends(get_db)):
    """Validate and queue an approved post in Buffer for @kkanalytica."""
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


@router.post("/test/buffer")
def test_buffer(
    x_admin_secret: str | None = Header(default=None, alias="X-Admin-Secret"),
) -> dict:
    """Queue a safe test post in Buffer (dev or admin-secret protected)."""
    _require_test_access(x_admin_secret)
    result = send_test_post()
    if not result.get("ok"):
        raise HTTPException(status_code=503, detail=result.get("error") or "Buffer test failed")
    return result


@router.get("/posts/{post_id}")
def get_post_endpoint(post_id: int, db: Session = Depends(get_db)) -> dict:
    post = get_post(db, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return {"ok": True, "post": post_to_dict(post)}
