"""Local LLM newsroom routes — draft/audit only; human approval required to publish."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.integrations.ollama_client import OllamaError
from app.schemas.local_newsroom import (
    NewsroomAuditRequest,
    NewsroomAuditResponse,
    NewsroomDraftRequest,
    NewsroomDraftResponse,
    SaveTrainingExampleRequest,
)
from app.services.local_llm_service import local_llm_service

router = APIRouter(tags=["llm"])


def _ollama_http_error(exc: OllamaError) -> HTTPException:
    return HTTPException(status_code=503, detail=str(exc))


@router.post("/llm/draft-newsroom-post", response_model=NewsroomDraftResponse)
def draft_newsroom_post(
    body: NewsroomDraftRequest,
    db: Session = Depends(get_db),
) -> NewsroomDraftResponse:
    """Draft a newsroom post via local Ollama. Does not publish."""
    try:
        return local_llm_service.draft_newsroom_post(db, body)
    except OllamaError as exc:
        raise _ollama_http_error(exc) from exc


@router.post("/llm/audit-source", response_model=NewsroomAuditResponse)
def audit_source(body: NewsroomAuditRequest) -> NewsroomAuditResponse:
    """Audit source material and draft text via local Ollama."""
    try:
        return local_llm_service.audit_source(body)
    except OllamaError as exc:
        raise _ollama_http_error(exc) from exc


@router.post("/training/save-newsroom-example")
def save_training_example(
    body: SaveTrainingExampleRequest,
    db: Session = Depends(get_db),
) -> dict:
    if not body.approved_by_human:
        raise HTTPException(status_code=400, detail="Only human-approved examples may be saved")
    row = local_llm_service.save_training_example(db, body)
    return {"ok": True, "id": row.id}


@router.get("/training/export-newsroom-jsonl")
def export_newsroom_jsonl(db: Session = Depends(get_db)) -> PlainTextResponse:
    """Export approved training examples as JSONL for LoRA/QLoRA fine-tuning."""
    content = local_llm_service.export_training_jsonl(db)
    return PlainTextResponse(
        content=content,
        media_type="application/x-ndjson",
        headers={"Content-Disposition": 'attachment; filename="newsroom_training.jsonl"'},
    )
