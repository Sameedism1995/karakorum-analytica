"""LLM-assisted draft post generation for incidents."""

from __future__ import annotations

from loguru import logger
from sqlalchemy.orm import Session

from app.config import get_settings
from app.integrations.llm_client import LLMClient
from app.integrations.ollama_client import OllamaError, local_llm_mode_active
from app.models.incident import Incident
from app.processors.post_generator import generate_draft_post
from app.schemas.llm_dashboard import AuditPostRequest, GeneratePostRequest
from app.schemas.local_newsroom import NewsroomAuditRequest, NewsroomDraftRequest
from app.services.llm_newsroom_service import audit_post, generate_post
from app.services.local_llm_service import get_local_llm_health, local_llm_service


def get_llm_health() -> dict:
    settings = get_settings()
    client = LLMClient()
    local = get_local_llm_health()

    if local_llm_mode_active():
        mode = "local_ollama" if local.get("reachable") and local.get("model_ready") else "local_ollama_unavailable"
        return {
            "provider": "ollama",
            "model": settings.local_llm_model,
            "openai_configured": bool(settings.openai_api_key.strip()) and settings.llm_provider == "openai",
            "local_llm_enabled": True,
            "local_llm_auto_detect": local.get("auto_detect", False),
            "local_llm": local,
            "mode": mode,
        }

    return {
        "provider": settings.llm_provider,
        "model": settings.llm_model,
        "openai_configured": client.is_configured,
        "local_llm_enabled": False,
        "local_llm_auto_detect": False,
        "local_llm": local,
        "mode": "openai" if client.is_configured else "template",
    }


def _grade_from_confidence(score: float) -> str:
    if score >= 66:
        return "B"
    if score >= 33:
        return "C"
    return "D"


def incident_to_raw_text(incident: Incident) -> str:
    parts = [
        incident.main_title or "",
        f"Location: {', '.join(p for p in [incident.city, incident.province, incident.country] if p)}",
        f"Event type: {incident.event_type or 'security incident'}",
        f"Keywords: {incident.keywords or ''}",
        f"Matched sources: {incident.matched_sources or ''}",
        f"Confidence: {incident.confidence_score:.1f}%",
    ]
    return "\n".join(p for p in parts if p.strip())


def generate_post_text_for_incident(
    db: Session | None,
    incident: Incident,
    *,
    tone: str = "neutral",
) -> tuple[str, dict]:
    """Return X post text and LLM metadata (mode, website, hashtags, etc.)."""
    settings = get_settings()
    keywords = [k.strip() for k in (incident.keywords or "").split(",") if k.strip()]
    main_kw = keywords[0] if keywords else "security incident"
    raw_text = incident_to_raw_text(incident)
    source_count = len([s for s in (incident.matched_sources or "").split(", ") if s])
    location = ", ".join(p for p in [incident.city, incident.province] if p)

    if local_llm_mode_active() and db is not None:
        try:
            draft = local_llm_service.draft_newsroom_post(
                db,
                NewsroomDraftRequest(
                    raw_text=raw_text,
                    source_name=incident.matched_sources or "open-source",
                    source_type=incident.matched_sources or "open-source reports",
                    location=location or "Pakistan",
                    incident_type=incident.event_type or "security incident",
                ),
            )
            meta = {
                "mode": draft.mode,
                "website_post": draft.post_text,
                "seo_headline": draft.headline,
                "meta_description": draft.headline,
                "hashtags": [],
                "verification_warning": f"Verification: {draft.verification_status}",
                "editorial_notes": draft.editor_notes,
                "source_grade": draft.source_grade,
                "risk_flags": draft.risk_flags,
                "publish_recommendation": draft.publish_recommendation,
                "provider": draft.provider,
            }
            return draft.post_text[:280], meta
        except OllamaError as exc:
            logger.warning(f"Local LLM draft failed, falling back to template: {exc}")

    response = generate_post(
        GeneratePostRequest(
            raw_incident_text=raw_text,
            main_keyword=main_kw,
            seo_keywords=incident.keywords or "",
            region=incident.province or "",
            country=incident.country or "Pakistan",
            city_district=incident.city or "",
            incident_category=incident.event_type or "Security",
            source_type=incident.matched_sources or "open-source reports",
            source_reliability_grade=_grade_from_confidence(incident.confidence_score),
            tone=tone,  # type: ignore[arg-type]
            platform="x",
        )
    )

    text = (response.short_x_post or "").strip()
    if not text:
        text = generate_draft_post(
            main_title=incident.main_title or "",
            province=incident.province,
            city=incident.city,
            keywords=keywords,
            confidence_score=incident.confidence_score,
            source_count=source_count,
        )

    meta = {
        "mode": response.mode,
        "website_post": response.website_post,
        "seo_headline": response.seo_headline,
        "meta_description": response.meta_description,
        "hashtags": response.suggested_hashtags,
        "verification_warning": response.verification_warning,
        "editorial_notes": response.editorial_notes,
    }
    return text[:280], meta


def audit_draft_text(
    post_text: str,
    *,
    source_info: str = "",
    raw_report: str = "",
    db: Session | None = None,
    location: str = "",
    incident_type: str = "",
) -> dict:
    settings = get_settings()
    if local_llm_mode_active():
        audit = local_llm_service.audit_source(
            NewsroomAuditRequest(
                raw_text=raw_report,
                post_text=post_text,
                source_name=source_info,
                source_type=source_info,
                location=location,
                incident_type=incident_type,
            )
        )
        return audit.model_dump()

    result = audit_post(
        AuditPostRequest(
            draft_post=post_text,
            source_information=source_info,
            raw_report_text=raw_report,
        )
    )
    return result.model_dump()
