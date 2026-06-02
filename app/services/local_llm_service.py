"""Local Ollama newsroom LLM service (draft + audit only — never auto-publish)."""

from __future__ import annotations

import json
from typing import Any

from loguru import logger
from sqlalchemy.orm import Session

from app.config import get_settings
from app.integrations.ollama_client import (
    OllamaError,
    check_ollama,
    generate_json,
    local_llm_mode_active,
    ping_generate,
    probe_ollama,
    is_localhost_ollama_url,
)
from app.models.newsroom_training_example import NewsroomTrainingExample
from app.prompts.newsroom_system import (
    LOCAL_DRAFT_USER_TEMPLATE,
    NEWSROOM_AUDIT_SYSTEM,
    NEWSROOM_AUDIT_USER_TEMPLATE,
    NEWSROOM_DRAFT_SYSTEM,
    NEWSROOM_DRAFT_USER_TEMPLATE,
)
from app.schemas.local_newsroom import (
    LocalDraftRequest,
    LocalDraftResponse,
    NewsroomAuditRequest,
    NewsroomAuditResponse,
    NewsroomDraftRequest,
    NewsroomDraftResponse,
    SaveTrainingExampleRequest,
)
from app.services.newsroom_rag_service import fetch_style_examples, format_style_examples
from app.services.post_service import create_post_from_local_draft


def _ensure_local_enabled() -> None:
    if not local_llm_mode_active():
        raise OllamaError(
            "Local LLM unavailable. On your machine run: ollama serve — then: "
            f"ollama pull {get_settings().local_llm_model}"
        )


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


def _normalize_local_draft(data: dict[str, Any], *, model: str) -> LocalDraftResponse:
    post_text = str(data.get("post_text") or "").strip()[:280]
    headline = str(data.get("headline") or "").strip()[:70]
    if not post_text:
        post_text = "Initial reports suggest activity reported. Official confirmation is pending."
    if not headline:
        headline = "OSINT update — verification pending"

    return LocalDraftResponse(
        post_text=post_text,
        headline=headline,
        verification_status=str(data.get("verification_status") or "unverified"),
        source_grade=str(data.get("source_grade") or "C")[:1].upper(),
        risk_flags=_as_list(data.get("risk_flags")),
        publish_recommendation=str(data.get("publish_recommendation") or "needs_review"),
        editor_notes=_as_list(data.get("editor_notes")),
        provider="ollama",
        model=model,
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

    def draft_local(self, db: Session, request: LocalDraftRequest) -> LocalDraftResponse:
        """Draft via Ollama with strict JSON; optionally save to Supabase posts."""
        _ensure_local_enabled()
        status = _ensure_ollama_ready()
        logger.info(f"Local draft-local start model={status.get('model')} save={request.save}")

        user_prompt = LOCAL_DRAFT_USER_TEMPLATE.format(
            raw_text=request.raw_text or "(none provided)",
            source_name=request.source_name or "unknown",
            source_url=request.source_url or "n/a",
            location=request.location or "Pakistan",
            category=request.category or "conflict/security",
            verification_status=request.verification_status or "unverified",
            source_grade=request.source_grade or "C",
        )

        try:
            data = generate_json(NEWSROOM_DRAFT_SYSTEM, user_prompt)
        except OllamaError:
            raise
        except Exception as exc:
            raise OllamaError(str(exc), reachable=True) from exc

        normalized = _normalize_local_draft(data, model=status["model"])
        post_id = None
        post_status = None

        if request.save:
            post = create_post_from_local_draft(
                db,
                headline=normalized.headline,
                post_text=normalized.post_text,
                source_name=request.source_name or "Karakorum Analytica OSINT",
                source_url=request.source_url,
                verification_status=normalized.verification_status,
                source_grade=normalized.source_grade,
                risk_flags=normalized.risk_flags,
                editor_notes=normalized.editor_notes,
                publish_recommendation=normalized.publish_recommendation,
                status="needs_review",
            )
            post_id = post.id
            post_status = post.status
            logger.info(f"Local draft saved to Supabase post_id={post_id} status={post_status}")

        return LocalDraftResponse(
            **normalized.model_dump(exclude={"provider", "model"}),
            provider="ollama",
            model=status["model"],
            post_id=post_id,
            status=post_status,
        )

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


def get_ollama_health() -> dict[str, Any]:
    """Standard health payload for GET /api/health/ollama — never raises."""
    settings = get_settings()
    enabled = settings.local_llm_enabled or local_llm_mode_active()
    try:
        if not enabled:
            return {
                "enabled": False,
                "base_url": settings.local_llm_base_url,
                "model": settings.local_llm_model,
                "server_reachable": False,
                "model_available": False,
                "generate_ok": False,
                "error": "LOCAL_LLM_ENABLED is false",
                "production_warning": None,
            }

        probe = probe_ollama(timeout=8.0)
        server_reachable = bool(probe.get("reachable"))
        model_available = bool(probe.get("model_ready"))
        generate_ok = False
        generate_error = None

        if server_reachable and model_available:
            gen = ping_generate(timeout=20.0)
            generate_ok = bool(gen.get("ok"))
            generate_error = gen.get("error")

        error = probe.get("error") or generate_error
        production_warning = None
        if settings.is_production and settings.local_llm_enabled and is_localhost_ollama_url(settings.local_llm_base_url):
            production_warning = (
                "LOCAL_LLM_ENABLED on production with localhost URL — Ollama must run on this server. "
                "On Render, localhost is the Render container, not your Mac."
            )
            logger.warning(production_warning)
        if settings.is_production and enabled and not server_reachable:
            logger.warning(
                f"LOCAL_LLM enabled in production but Ollama unreachable at {settings.local_llm_base_url}"
            )

        return {
            "enabled": True,
            "base_url": settings.local_llm_base_url,
            "model": settings.local_llm_model,
            "server_reachable": server_reachable,
            "model_available": model_available,
            "generate_ok": generate_ok,
            "models_available": probe.get("models_available") or [],
            "error": error if not (server_reachable and model_available and generate_ok) else None,
            "production_warning": production_warning,
        }
    except Exception as exc:
        logger.error(f"Ollama health check failed: {exc}")
        return {
            "enabled": enabled,
            "base_url": settings.local_llm_base_url,
            "model": settings.local_llm_model,
            "server_reachable": False,
            "model_available": False,
            "generate_ok": False,
            "error": str(exc),
            "production_warning": None,
        }


def get_local_llm_health() -> dict[str, Any]:
    settings = get_settings()
    status = check_ollama()
    return {
        "local_llm_enabled": settings.local_llm_enabled,
        "local_llm_base_url": settings.local_llm_base_url,
        "local_llm_model": settings.local_llm_model,
        **status,
    }
