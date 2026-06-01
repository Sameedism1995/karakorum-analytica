"""Tests for local Scweet token resolution."""

import json
import sqlite3
from pathlib import Path

import pytest

from app.config import get_settings
from app.integrations import scweet_token_source


def test_resolve_from_environment(monkeypatch):
    monkeypatch.setenv("SCWEET_AUTH_TOKEN", "env-token-abc")
    get_settings.cache_clear()
    token, source = scweet_token_source.resolve_local_auth_token()
    assert token == "env-token-abc"
    assert source == "environment"


def test_resolve_from_session_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("SCWEET_AUTH_TOKEN", "")
    cache = tmp_path / "scweet_session.json"
    cache.write_text(
        json.dumps({"auth_token": "cache-token-xyz", "expires_at": "2099-01-01T00:00:00+00:00"}),
        encoding="utf-8",
    )
    monkeypatch.setenv("SCWEET_SESSION_CACHE_PATH", str(cache))
    get_settings.cache_clear()
    token, source = scweet_token_source.resolve_local_auth_token()
    assert token == "cache-token-xyz"
    assert source == "session_cache"


def test_resolve_from_scweet_state_db(tmp_path, monkeypatch):
    monkeypatch.setenv("SCWEET_AUTH_TOKEN", "")
    db_path = tmp_path / "scweet_state.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE accounts (
            id INTEGER PRIMARY KEY,
            username TEXT NOT NULL,
            auth_token TEXT,
            cookies_json TEXT,
            last_used REAL
        )
        """
    )
    conn.execute(
        "INSERT INTO accounts (username, auth_token, cookies_json, last_used) VALUES (?, ?, ?, ?)",
        ("kkanalytica", "db-token-123", None, 9999.0),
    )
    conn.commit()
    conn.close()

    monkeypatch.setenv("SCWEET_SESSION_CACHE_PATH", str(tmp_path / "missing.json"))
    monkeypatch.setenv("SCWEET_DB_PATH", str(db_path))
    get_settings.cache_clear()
    token, source = scweet_token_source.resolve_local_auth_token()
    assert token == "db-token-123"
    assert source == "scweet_state.db"


def test_resolve_from_cookies_json_in_db(tmp_path, monkeypatch):
    monkeypatch.setenv("SCWEET_AUTH_TOKEN", "")
    db_path = tmp_path / "scweet_state.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE accounts (
            id INTEGER PRIMARY KEY,
            username TEXT NOT NULL,
            auth_token TEXT,
            cookies_json TEXT,
            last_used REAL
        )
        """
    )
    cookies = json.dumps({"auth_token": "cookie-token-456", "ct0": "csrf"})
    conn.execute(
        "INSERT INTO accounts (username, auth_token, cookies_json, last_used) VALUES (?, ?, ?, ?)",
        ("kkanalytica", "", cookies, 9999.0),
    )
    conn.commit()
    conn.close()

    monkeypatch.setenv("SCWEET_SESSION_CACHE_PATH", str(tmp_path / "missing.json"))
    monkeypatch.setenv("SCWEET_DB_PATH", str(db_path))
    get_settings.cache_clear()
    token, source = scweet_token_source.resolve_local_auth_token()
    assert token == "cookie-token-456"
    assert source == "scweet_state.db"
