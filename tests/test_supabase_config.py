"""Tests for Supabase / database configuration."""

from app.config import Settings


def test_effective_database_url_prefers_supabase_db_url():
    settings = Settings(
        supabase_db_url="postgresql://postgres:secret@db.abc123.supabase.co:5432/postgres"
    )
    assert "postgresql+psycopg://" in settings.effective_database_url
    assert "abc123.supabase.co" in settings.effective_database_url


def test_effective_database_url_builds_from_password():
    settings = Settings(
        supabase_url="https://abc123.supabase.co",
        supabase_db_password="p@ss:word",
    )
    url = settings.effective_database_url
    assert "postgresql+psycopg://" in url
    assert "db.abc123.supabase.co" in url
    assert "p%40ss%3Aword" in url


def test_sqlite_fallback_when_supabase_not_set():
    settings = Settings(database_url="sqlite:///./local.db")
    assert settings.effective_database_url == "sqlite:///./local.db"
    assert settings.database_backend == "sqlite"
    assert settings.using_supabase is False
