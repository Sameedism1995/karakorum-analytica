"""Schemas for local Ollama newsroom drafting."""

from __future__ import annotations

from pydantic import BaseModel, Field


class NewsroomDraftRequest(BaseModel):
    raw_text: str = ""
    source_url: str = ""
    source_name: str = ""
    source_type: str = ""
    location: str = ""
    incident_type: str = ""
    media_url: str = ""


class NewsroomDraftResponse(BaseModel):
    post_text: str
    headline: str
    verification_status: str
    source_grade: str
    risk_flags: list[str] = Field(default_factory=list)
    publish_recommendation: str
    editor_notes: list[str] = Field(default_factory=list)
    provider: str = "ollama"
    model: str = ""
    rag_examples_used: int = 0
    mode: str = "local_llm"


class NewsroomAuditRequest(BaseModel):
    raw_text: str = ""
    post_text: str
    source_url: str = ""
    source_name: str = ""
    source_type: str = ""
    location: str = ""
    incident_type: str = ""


class NewsroomAuditResponse(BaseModel):
    verification_status: str
    source_grade: str
    risk_flags: list[str] = Field(default_factory=list)
    publish_recommendation: str
    editor_notes: list[str] = Field(default_factory=list)
    safer_rewrite: str = ""
    provider: str = "ollama"


class SaveTrainingExampleRequest(BaseModel):
    raw_input: str
    final_output: str
    source_grade: str = "C"
    verification_status: str = "unverified"
    editor_notes: str = ""
    approved_by_human: bool = True


class LocalDraftRequest(BaseModel):
    raw_text: str
    source_name: str = ""
    source_url: str = ""
    location: str = "Pakistan"
    category: str = "conflict/security"
    verification_status: str = "unverified"
    source_grade: str = "C"
    save: bool = True


class LocalDraftResponse(BaseModel):
    headline: str
    post_text: str
    verification_status: str
    source_grade: str
    risk_flags: list[str] = Field(default_factory=list)
    editor_notes: list[str] = Field(default_factory=list)
    publish_recommendation: str = "needs_review"
    provider: str = "ollama"
    model: str = ""
    post_id: int | None = None
    status: str | None = None


class E2EPipelineRequest(BaseModel):
    dry_run: bool = True
