"""Integration test for pipeline using mocked public API responses."""

from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import init_db
from app.services.collection_service import collect_all
from app.services.draft_service import generate_drafts_for_incidents, list_drafts
from app.services.incident_service import list_incidents, process_incidents


SAMPLE_GDELT = [
    {
        "source_name": "GDELT",
        "title": "Explosion reported in Quetta, Balochistan",
        "summary": "Security forces responded to a blast near a checkpoint in Quetta, Balochistan.",
        "url": "https://example.com/quetta-blast-1",
        "published_at": datetime.now(timezone.utc),
        "country": "Pakistan",
        "province": "Balochistan",
        "city": "Quetta",
        "raw_json": {},
    }
]

SAMPLE_RELIEFWEB = [
    {
        "source_name": "ReliefWeb",
        "title": "Security incident in Quetta area, Balochistan",
        "summary": "Reports of explosion and police operation in Quetta, Balochistan, Pakistan.",
        "url": "https://example.com/reliefweb-quetta-1",
        "published_at": datetime.now(timezone.utc),
        "country": "Pakistan",
        "province": "Balochistan",
        "city": "Quetta",
        "raw_json": {},
    }
]


@pytest.fixture
def db_session(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
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


@patch("app.services.collection_service.collect_gdelt", return_value=SAMPLE_GDELT)
@patch("app.services.collection_service.collect_reliefweb", return_value=SAMPLE_RELIEFWEB)
@patch("app.services.collection_service.collect_acled", return_value=[])
def test_full_pipeline(mock_acled, mock_reliefweb, mock_gdelt, db_session):
    stats = collect_all(db_session)
    assert stats["saved"] >= 2

    incident_stats = process_incidents(db_session)
    assert incident_stats["incidents_created"] + incident_stats["incidents_updated"] >= 1

    incidents = list_incidents(db_session)
    assert len(incidents) >= 1
    assert incidents[0].confidence_score == 66.66

    draft_stats = generate_drafts_for_incidents(db_session)
    assert draft_stats["drafts_created"] >= 1

    drafts = list_drafts(db_session)
    assert "Quetta" in drafts[0].post_text
    assert drafts[0].status == "pending"
