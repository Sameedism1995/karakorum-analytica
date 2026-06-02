"""Tests for local Ollama newsroom pipeline."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.database import init_db
from app.integrations.ollama_client import OllamaError
from app.main import app
from app.models.newsroom_training_example import NewsroomTrainingExample
from app.schemas.local_newsroom import NewsroomAuditRequest, NewsroomDraftRequest
from app.services.local_llm_service import local_llm_service
from app.services.newsroom_rag_service import fetch_style_examples, format_style_examples


@pytest.fixture
def db_session(tmp_path, monkeypatch):
    db_path = tmp_path / "test_local_llm.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    get_settings.cache_clear()
    from app import config, database

    config.get_settings.cache_clear()
    database.engine.dispose()
    settings = config.get_settings()
    database.engine = create_engine(
        settings.database_url,
        connect_args={"check_same_thread": False},
    )
    database.SessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=database.engine
    )
    init_db()
    db = database.SessionLocal()
    yield db
    db.close()


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_format_style_examples_empty():
    text = format_style_examples([])
    assert "STYLE ONLY" not in text
    assert "neutral OSINT tone" in text


def test_export_training_jsonl_empty(db_session):
    content = local_llm_service.export_training_jsonl(db_session)
    assert content == ""


def test_export_training_jsonl_includes_approved(db_session):
    row = NewsroomTrainingExample(
        raw_input='{"raw": "test"}',
        final_output='{"post_text": "Monitoring reports."}',
        source_grade="C",
        verification_status="unverified",
        editor_notes="ok",
        approved_by_human=True,
    )
    db_session.add(row)
    db_session.commit()

    content = local_llm_service.export_training_jsonl(db_session)
    lines = [ln for ln in content.strip().split("\n") if ln]
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["input"] == '{"raw": "test"}'
    assert record["metadata"]["source_grade"] == "C"


@patch("app.services.local_llm_service.generate_json")
@patch("app.services.local_llm_service.check_ollama")
def test_draft_newsroom_post_normalizes_response(mock_check, mock_generate, db_session, monkeypatch):
    monkeypatch.setenv("LOCAL_LLM_ENABLED", "true")
    get_settings.cache_clear()
    mock_check.return_value = {
        "enabled": True,
        "reachable": True,
        "model_ready": True,
        "model": "qwen3:4b",
    }
    mock_generate.return_value = {
        "post_text": "Initial reports suggest activity near Quetta. Official confirmation is pending.",
        "headline": "Quetta security update",
        "verification_status": "unverified",
        "source_grade": "C",
        "risk_flags": ["unverified casualty claims"],
        "publish_recommendation": "needs_verification",
        "editor_notes": ["Seek official statement"],
    }

    result = local_llm_service.draft_newsroom_post(
        db_session,
        NewsroomDraftRequest(
            raw_text="Local sources claim an incident near Quetta.",
            location="Quetta, Balochistan",
            incident_type="IED",
        ),
    )
    assert result.mode == "local_llm"
    assert result.provider == "ollama"
    assert "Quetta" in result.post_text
    assert result.source_grade == "C"
    assert result.publish_recommendation == "needs_verification"


@patch("app.services.local_llm_service.check_ollama")
def test_draft_endpoint_returns_503_when_ollama_down(mock_check, monkeypatch):
    monkeypatch.setenv("LOCAL_LLM_ENABLED", "true")
    get_settings.cache_clear()
    mock_check.return_value = {
        "enabled": True,
        "reachable": False,
        "error": "Ollama not running at http://localhost:11434",
    }

    client = TestClient(app)
    response = client.post(
        "/llm/draft-newsroom-post",
        json={"raw_text": "test incident", "location": "Quetta"},
    )
    assert response.status_code == 503
    assert "Ollama" in response.json()["detail"]


def test_export_endpoint_returns_jsonl(db_session, monkeypatch):
    monkeypatch.setenv("LOCAL_LLM_ENABLED", "true")
    get_settings.cache_clear()

    row = NewsroomTrainingExample(
        raw_input="raw",
        final_output="output",
        approved_by_human=True,
    )
    db_session.add(row)
    db_session.commit()

    from app.database import get_db

    def _override_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    try:
        client = TestClient(app)
        response = client.get("/training/export-newsroom-jsonl")
        assert response.status_code == 200
        assert "application/x-ndjson" in response.headers.get("content-type", "")
        assert "raw" in response.text
    finally:
        app.dependency_overrides.clear()


def test_fetch_style_examples_returns_list(db_session):
    examples = fetch_style_examples(
        db_session,
        raw_text="Quetta blast security",
        location="Quetta",
        incident_type="IED",
        limit=5,
    )
    assert isinstance(examples, list)


def test_local_disabled_raises(monkeypatch):
    monkeypatch.setenv("LOCAL_LLM_ENABLED", "false")
    monkeypatch.setenv("LOCAL_LLM_BASE_URL", "http://remote-ollama:11434")
    monkeypatch.setenv("RENDER", "true")
    get_settings.cache_clear()
    with pytest.raises(OllamaError):
        local_llm_service.audit_source(NewsroomAuditRequest(post_text="test"))
