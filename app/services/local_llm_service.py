"""Local Ollama newsroom LLM service (draft + audit only — never auto-publish)."""

from __future__ import annotations

import json
from typing import Any

from app.config import get_settings
from app.integrations.ollama_client import OllamaError, check_ollama, generate_json
from app.models.newsroom_training_example import NewsroomTrainingExample
from app.prompts.newsroom_system import (
    NEWSROOM_AUDIT_SYSTEM,
    NEWSROOM_AUDIT_USER_TEMPLATE,
    NEWSROOM_DRAFT_SYSTEM,
    NEWSROOM_DRAFT_USER_TEMPLATE,
)
from app.schemas.local_newsroom import (
    NewsroomAuditRequest,
    NewsroomAuditResponse,
    NewsroomDraftRequest,
    NewsroomDraftResponse,
    SaveTrainingExampleRequest,
)
from app.services.newsroom_rag_service import fetch_style_examples, format_style_examples


def _ensure_local_enabled() -> None:
    if not get_settings().local_llm_enabled:
        raise OllamaError("Local LLM disabled. Set LOCAL_LLM_ENABLED=true and run Ollama.")


def _ensure_ollama_ready() -> dict[str, Any]:
    status = check_ollama()
    if not status.get("enabled"):
        raise OllamaError(status.get("error") or "Local LLM disabled")
    if not status.get("reachable"):
        raise OllamaError(
            status.get("error") or "Ollama is not running. Start with: ollama serve",
            reachable=False,
        )
    if not status.get("model_ready"):
        raise OllamaError(
            status.get("error") or f"Pull model: ollama pull {get_settings().local_llm_model}",
            reachable=True,
        )
    return status


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v) for v in value if str(v).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _normalize_draft(data: dict[str, Any], *, model: str, rag_count: int) -> NewsroomDraftResponse:
    post_text = str(data.get("post_text") or data.get("short_x_post") or "").strip()[:280]
    headline = str(data.get("headline") or data.get("seo_headline") or "").strip()[:70]
    if not post_text:
        post_text = "Monitoring reports. Official confirmation is pending. Karakorum Analytica."
    if not headline:
        headline = "OSINT update — verification pending"

    return NewsroomDraftResponse(
        post_text=post_text,
        headline=headline,
        verification_status=str(data.get("verification_status") or "unverified"),
        source_grade=str(data.get("source_grade") or "C")[:1].upper(),
        risk_flags=_as_list(data.get("risk_flags")),
        publish_recommendation=str(data.get("publish_recommendation") or "needs_verification"),
        editor_notes=_as_list(data.get("editor_notes")),
        provider="ollama",
        model=model,
        rag_examples_used=rag_count,
        mode="local_llm",
    )


def _normalize_audit(data: dict[str, Any]) -> NewsroomAuditResponse:
    return NewsroomAuditResponse(
        verification_status=str(data.get("verification_status") or "unverified"),
        source_grade=str(data.get("source_grade") or "C")[:1].upper(),
        risk_flags=_as_list(data.get("risk_flags")),
        publish_recommendation=str(data.get("publish_recommendation") or "needs_verification"),
        editor_notes=_as_list(data.get("editor_notes")),
        safer_rewrite=str(data.get("safer_rewrite") or data.get("safer_rewritten_version") or "")[:280],
        provider="ollama",
    )


class LocalLlmService:
    """Ollama-backed newsroom drafting and source audit."""

    def draft_newsroom_post(
        self,
        db: Session,
        request: NewsroomDraftRequest,
    ) -> NewsroomDraftResponse:
        _ensure_local_enabled()
        status = _ensure_ollama_ready()

        examples = fetch_style_examples(
            db,
            raw_text=request.raw_text,
            location=request.location,
            incident_type=request.incident_type,
            source_name=request.source_name,
            limit=5,
        )
        style_block = format_style_examples(examples)
        user_prompt = NEWSROOM_DRAFT_USER_TEMPLATE.format(
            raw_text=request.raw_text or "(none provided)",
            source_url=request.source_url or "n/a",
            source_name=request.source_name or "unknown",
            source_type=request.source_type or "open-source",
            location=request.location or "Pakistan",
            incident_type=request.incident_type or "security incident",
            media_url=request.media_url or "n/a",
            style_examples=style_block,
        )

        try:
            data = generate_json(NEWSROOM_DRAFT_SYSTEM, user_prompt)
        except OllamaError:
            raise
        except Exception as exc:
            raise OllamaError(str(exc), reachable=True) from exc

        return _normalize_draft(data, model=status["model"], rag_count=len(examples))

    def audit_source(self, request: NewsroomAuditRequest) -> NewsroomAuditResponse:
        _ensure_local_enabled()
        _ensure_ollama_ready()

        user_prompt = NEWSROOM_AUDIT_USER_TEMPLATE.format(
            raw_text=request.raw_text or "(none)",
            source_url=request.source_url or "n/a",
            source_name=request.source_name or "unknown",
            source_type=request.source_type or "open-source",
            location=request.location or "Pakistan",
            incident_type=request.incident_type or "security incident",
            post_text=request.post_text,
        )

        try:
            data = generate_json(NEWSROOM_AUDIT_SYSTEM, user_prompt)
        except OllamaError:
            raise
        except Exception as exc:
            raise OllamaError(str(exc), reachable=True) from exc

        return _normalize_audit(data)

    def save_training_example(
        self,
        db: Session,
        request: SaveTrainingExampleRequest,
    ) -> NewsroomTrainingExample:
        row = NewsroomTrainingExample(
            raw_input=request.raw_input,
            final_output=request.final_output,
            source_grade=request.source_grade,
            verification_status=request.verification_status,
            editor_notes=request.editor_notes,
            approved_by_human=request.approved_by_human,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row

    def export_training_jsonl(self, db: Session) -> str:
        rows = (
            db.query(NewsroomTrainingExample)
            .filter(NewsroomTrainingExample.approved_by_human.is_(True))
            .order_by(NewsroomTrainingExample.created_at.asc())
            .all()
        )
        lines: list[str] = []
        for row in rows:
            record = {
                "instruction": NEWSROOM_DRAFT_SYSTEM,
                "input": row.raw_input,
                "output": row.final_output,
                "metadata": {
                    "source_grade": row.source_grade,
                    "verification_status": row.verification_status,
                    "editor_notes": row.editor_notes,
                    "id": row.id,
                },
            }
            lines.append(json.dumps(record, ensure_ascii=False))
        return "\n".join(lines) + ("\n" if lines else "")


local_llm_service = LocalLlmService()


def get_local_llm_health() -> dict[str, Any]:
    settings = get_settings()
    status = check_ollama()
    return {
        "local_llm_enabled": settings.local_llm_enabled,
        "local_llm_base_url": settings.local_llm_base_url,
        "local_llm_model": settings.local_llm_model,
        **status,
    }
