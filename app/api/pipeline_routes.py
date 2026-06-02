"""Pipeline health checks and E2E test endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import check_database_connection, get_db
from app.integrations.ollama_client import OllamaError
from app.schemas.local_newsroom import E2EPipelineRequest, LocalDraftRequest, LocalDraftResponse
from app.services.buffer_service import get_buffer_health
from app.services.e2e_pipeline_service import run_e2e_local_to_buffer
from app.services.local_llm_service import get_ollama_health, local_llm_service
from app.services.post_approval_service import approve_and_post_now
from app.services.post_service import create_post_from_local_draft
from app.services.buffer_posting_service import post_to_dict

router = APIRouter(prefix="/api", tags=["health", "pipeline"])


class ApproveAndPostTestRequest(BaseModel):
    live: bool = False


def _require_admin_secret(x_admin_secret: str | None) -> None:
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


@router.get("/health/ollama")
def ollama_health() -> dict:
    """Ollama connectivity — never crashes if offline."""
    return get_ollama_health()


@router.get("/health/buffer")
def buffer_health() -> dict:
    """Buffer API and channel discovery — never exposes API key."""
    return get_buffer_health()


@router.get("/health/supabase")
def supabase_health() -> dict:
    db = check_database_connection()
    settings = get_settings()
    return {
        "connected": db.get("ok", False),
        "backend": db.get("backend"),
        "using_supabase": db.get("using_supabase", False),
        "supabase_url_configured": bool(settings.supabase_url.strip()),
        "error": db.get("error"),
    }


@router.post("/llm/draft-local", response_model=LocalDraftResponse)
def draft_local(body: LocalDraftRequest, db: Session = Depends(get_db)) -> LocalDraftResponse:
    """Draft via local Ollama and optionally save to Supabase posts (needs_review)."""
    try:
        return local_llm_service.draft_local(db, body)
    except OllamaError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/posts/{post_id}/approve")
def approve_post(post_id: int, db: Session = Depends(get_db)) -> dict:
    """Validate, approve, and publish immediately to X through Buffer (shareNow)."""
    result = approve_and_post_now(db, post_id)
    if not result.get("ok"):
        return JSONResponse(status_code=400, content=result)
    return result


@router.post("/test/approve-and-post")
def test_approve_and_post(
    body: ApproveAndPostTestRequest | None = None,
    db: Session = Depends(get_db),
    x_admin_secret: str | None = Header(default=None, alias="X-Admin-Secret"),
) -> dict:
    """Create a safe test post and run approve+post flow (dry-run by default)."""
    _require_admin_secret(x_admin_secret)
    live = bool(body.live) if body is not None else False

    test_post = create_post_from_local_draft(
        db,
        headline="Karakorum Analytica approval flow test",
        post_text="Test post from Karakorum Analytica approval-to-X pipeline.",
        source_name="Karakorum Analytica Internal Test",
        source_url="https://karakorum-analytica.internal/test",
        verification_status="verified",
        source_grade="B",
        risk_flags=["pipeline_test"],
        editor_notes=["Admin test endpoint generated this record"],
        publish_recommendation="needs_review",
        status="needs_review",
    )
    if not live:
        return {
            "ok": True,
            "live": False,
            "message": "Dry run complete. Test post created and validated path is ready; no live Buffer call made.",
            "post": post_to_dict(test_post),
        }

    result = approve_and_post_now(db, test_post.id)
    if not result.get("ok"):
        return JSONResponse(status_code=400, content=result)
    return {"ok": True, "live": True, **result}


@router.post("/test/e2e-local-to-buffer")
def e2e_local_to_buffer(
    body: E2EPipelineRequest | None = None,
    db: Session = Depends(get_db),
    x_admin_secret: str | None = Header(default=None, alias="X-Admin-Secret"),
) -> dict:
    """Full pipeline test. Default dry_run=true — does not post to Buffer."""
    _require_admin_secret(x_admin_secret)
    dry_run = True if body is None else body.dry_run
    result = run_e2e_local_to_buffer(db, dry_run=dry_run)
    if not result.get("ok"):
        return JSONResponse(status_code=400, content=result)
    return result
