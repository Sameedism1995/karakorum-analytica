"""Tests for direct Buffer API posting."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import init_db
from app.models.post import Post
from app.services.buffer_posting_service import send_post_to_buffer
from app.services.buffer_validation_service import validate_post_for_buffer


@pytest.fixture
def db_session(tmp_path, monkeypatch):
    db_path = tmp_path / "buffer_test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("BUFFER_API_KEY", "test-key")
    from app.config import get_settings

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


def _approved_defaults() -> dict:
    return {
        "status": "approved",
        "post_text": (
            "Initial reports suggest security activity near Quetta. "
            "Official confirmation is pending. Local sources claim an incident."
        ),
        "headline": "Security activity near Quetta",
        "source_name": "GDELT",
        "source_url": None,
        "verification_status": "unverified",
        "source_grade": "C",
        "graphic_content": False,
    }


def _approved_post(**kwargs) -> Post:
    return Post(**{**_approved_defaults(), **kwargs})


def test_validate_blocks_empty_text():
    post = SimpleNamespace(**{**_approved_defaults(), "post_text": ""})
    ok, reason = validate_post_for_buffer(post)
    assert not ok
    assert "empty" in reason.lower()


def test_validate_allows_unverified_without_cautious_phrase():
    defaults = _approved_defaults()
    defaults["post_text"] = "Security activity reported near Quetta."
    post = SimpleNamespace(**defaults)
    ok, reason = validate_post_for_buffer(post)
    assert ok, reason


@patch("app.services.buffer_posting_service.buffer_service")
def test_send_post_to_buffer_success(mock_buffer, db_session):
    mock_buffer.is_configured.return_value = True
    mock_buffer.resolve_channel_id.return_value = ("channel-123", {"source": "env"})
    mock_buffer.queue_text_post.return_value = {
        "ok": True,
        "channel_id": "channel-123",
        "buffer_response": {"data": {"createPost": {"post": {"id": "buf-1"}}}},
        "post": {"id": "buf-1"},
    }

    post = _approved_post()
    db_session.add(post)
    db_session.commit()

    result = send_post_to_buffer(db_session, post.id)
    assert result["ok"] is True
    assert result["status"] == "sent_to_buffer"
    db_session.refresh(post)
    assert post.status == "sent_to_buffer"
    mock_buffer.queue_text_post.assert_called_once()


@patch("app.services.buffer_posting_service.buffer_service")
def test_send_validation_failure_does_not_call_buffer(mock_buffer, db_session):
    mock_buffer.is_configured.return_value = True

    post = _approved_post(post_text="", verification_status="unverified")
    db_session.add(post)
    db_session.commit()

    result = send_post_to_buffer(db_session, post.id)
    assert result["ok"] is False
    mock_buffer.queue_text_post.assert_not_called()
    db_session.refresh(post)
    assert post.status == "failed"
