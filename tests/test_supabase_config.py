"""Tests for Supabase / database configuration."""

import pytest

from app.config import Settings


@pytest.fixture(autouse=True)
def _clear_supabase_env(monkeypatch):
    """Isolate tests from local .env Supabase credentials."""
    for key in (
        "SUPABASE_URL",
        "SUPABASE_SERVICE_ROLE_KEY",
        "SUPABASE_DB_URL",
        "SUPABASE_DB_POOLER_URL",
        "SUPABASE_POOLER_REGION",
        "SUPABASE_DB_PASSWORD",
        "DATABASE_URL",
        "RENDER",
    ):
        monkeypatch.delenv(key, raising=False)


def test_effective_database_url_prefers_supabase_db_url():
    settings = Settings(
        _env_file=None,
        supabase_db_url="postgresql://postgres:secret@db.abc123.supabase.co:5432/postgres",
    )
    assert "postgresql+psycopg://" in settings.effective_database_url
    assert "abc123.supabase.co" in settings.effective_database_url


def test_effective_database_url_builds_from_password():
    settings = Settings(
        _env_file=None,
        supabase_url="https://abc123.supabase.co",
        supabase_db_password="p@ss:word",
        supabase_db_url="",
    )
    url = settings.effective_database_url
    assert "postgresql+psycopg://" in url
    assert "db.abc123.supabase.co" in url
    assert "p%40ss%3Aword" in url


def test_using_supabase_when_db_url_points_at_supabase():
    settings = Settings(
        _env_file=None,
        supabase_db_url="postgresql://postgres:secret@db.abc123.supabase.co:5432/postgres",
    )
    assert settings.using_supabase is True
    assert settings.database_backend == "supabase"


def test_effective_database_url_prefers_pooler_on_render(monkeypatch):
    monkeypatch.setenv("RENDER", "true")
    settings = Settings(
        _env_file=None,
        supabase_db_url="postgresql://postgres:secret@db.abc123.supabase.co:5432/postgres",
        supabase_db_pooler_url="postgresql://postgres.abc123:secret@aws-0-ap-south-1.pooler.supabase.com:5432/postgres",
    )
    url = settings.effective_database_url
    assert "pooler.supabase.com" in url
    assert "postgresql+psycopg://" in url


def test_effective_database_url_builds_pooler_from_region(monkeypatch):
    monkeypatch.setenv("RENDER", "true")
    settings = Settings(
        _env_file=None,
        supabase_db_url="postgresql://postgres:secret@db.abc123.supabase.co:5432/postgres",
        supabase_pooler_region="ap-south-1",
    )
    url = settings.effective_database_url
    assert "aws-0-ap-south-1.pooler.supabase.com" in url
    assert "postgres.abc123" in url


def test_sqlite_fallback_when_supabase_not_set():
    settings = Settings(
        _env_file=None,
        database_url="sqlite:///./local.db",
        supabase_db_url="",
    )
    assert settings.effective_database_url == "sqlite:///./local.db"
    assert settings.database_backend == "sqlite"
    assert settings.using_supabase is False
