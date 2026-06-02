"""Tests for Zapier + Buffer publishing validation."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import init_db
from app.models.post import Post
from app.services.buffer_validation_service import validate_post_for_buffer
from app.services.zapier_buffer_service import send_post_to_buffer


@pytest.fixture
def db_session(tmp_path, monkeypatch):
    db_path = tmp_path / "buffer_test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("BUFFER_VALIDATION_STRICT", "false")
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


def _approved_post(**kwargs) -> Post:
    defaults = {
        "status": "approved",
        "post_text": (
            "Initial reports suggest security activity near Quetta. "
            "Official confirmation is pending. Local sources claim an incident."
        ),
        "source_name": "GDELT",
        "verification_status": "unverified",
        "source_grade": "C",
        "graphic_content": False,
    }
    defaults.update(kwargs)
    return Post(**defaults)


def test_validate_blocks_empty_text(db_session):
    post = _approved_post(post_text="")
    db_session.add(post)
    db_session.commit()
    ok, reason = validate_post_for_buffer(post)
    assert not ok
    assert "empty" in reason.lower()


def test_relaxed_mode_allows_plain_unverified_text(db_session, monkeypatch):
    monkeypatch.setenv("BUFFER_VALIDATION_STRICT", "false")
    from app.config import get_settings

    get_settings.cache_clear()
    post = _approved_post(
        post_text="Attack reported in Quetta with casualties.",
        verification_status="unverified",
        source_name="",
    )
    ok, reason = validate_post_for_buffer(post)
    assert ok
    assert post.source_name == "Karakorum Analytica OSINT"


def test_strict_mode_blocks_unverified_without_cautious_phrase(db_session, monkeypatch):
    monkeypatch.setenv("BUFFER_VALIDATION_STRICT", "true")
    from app.config import get_settings

    get_settings.cache_clear()
    post = _approved_post(
        post_text="Attack reported in Quetta with casualties.",
        verification_status="unverified",
    )
    ok, reason = validate_post_for_buffer(post)
    assert not ok
    assert "cautious phrase" in reason.lower()


def test_validate_passes_safe_post(db_session):
    post = _approved_post()
    ok, reason = validate_post_for_buffer(post)
    assert ok
    assert reason == ""


@patch("app.services.zapier_buffer_service.httpx.post")
def test_send_post_to_buffer_success(mock_post, db_session, monkeypatch):
    monkeypatch.setenv("ZAPIER_BUFFER_WEBHOOK_URL", "https://hooks.zapier.com/hooks/catch/test/abc/")
    from app.config import get_settings

    get_settings.cache_clear()

    class FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return {"status": "success"}

    mock_post.return_value = FakeResponse()

    post = _approved_post()
    db_session.add(post)
    db_session.commit()

    result = send_post_to_buffer(db_session, post.id)
    assert result["ok"] is True
    assert result["status"] == "sent_to_buffer"
    db_session.refresh(post)
    assert post.status == "sent_to_buffer"
    assert post.sent_to_buffer_at is not None


@patch("app.services.zapier_buffer_service.httpx.post")
def test_relaxed_mode_sends_plain_text(mock_post, db_session, monkeypatch):
    monkeypatch.setenv("ZAPIER_BUFFER_WEBHOOK_URL", "https://hooks.zapier.com/hooks/catch/test/abc/")
    monkeypatch.setenv("BUFFER_VALIDATION_STRICT", "false")
    from app.config import get_settings

    get_settings.cache_clear()

    class FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return {"status": "success"}

    mock_post.return_value = FakeResponse()

    post = _approved_post(post_text="Plain update from Quetta.", verification_status="unverified")
    db_session.add(post)
    db_session.commit()

    result = send_post_to_buffer(db_session, post.id)
    assert result["ok"] is True
    mock_post.assert_called_once()
