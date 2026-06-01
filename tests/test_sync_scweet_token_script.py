"""Tests for standalone sync_scweet_token_to_render.py helpers."""

import json
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import sync_scweet_token_to_render as sync_script  # noqa: E402


def test_extract_auth_token_from_db_direct_column(tmp_path):
    db = tmp_path / "scweet_state.db"
    conn = sqlite3.connect(db)
    conn.execute(
        """
        CREATE TABLE accounts (
            id INTEGER PRIMARY KEY,
            username TEXT,
            auth_token TEXT,
            cookies_json TEXT,
            last_used REAL
        )
        """
    )
    conn.execute(
        "INSERT INTO accounts (username, auth_token, last_used) VALUES (?, ?, ?)",
        ("kkanalytica", "token-from-db", 100.0),
    )
    conn.commit()
    conn.close()

    token, username = sync_script.extract_auth_token_from_db(db)
    assert token == "token-from-db"
    assert username == "kkanalytica"


def test_extract_auth_token_from_cookies_json(tmp_path):
    db = tmp_path / "scweet_state.db"
    conn = sqlite3.connect(db)
    conn.execute(
        """
        CREATE TABLE accounts (
            id INTEGER PRIMARY KEY,
            username TEXT,
            auth_token TEXT,
            cookies_json TEXT,
            last_used REAL
        )
        """
    )
    cookies = json.dumps({"auth_token": "token-from-json", "ct0": "csrf"})
    conn.execute(
        "INSERT INTO accounts (username, auth_token, cookies_json, last_used) VALUES (?, ?, ?, ?)",
        ("kkanalytica", "", cookies, 100.0),
    )
    conn.commit()
    conn.close()

    token, _ = sync_script.extract_auth_token_from_db(db)
    assert token == "token-from-json"


def test_get_render_service_ids_from_env(monkeypatch):
    monkeypatch.setenv("RENDER_SERVICE_ID", "srv-one")
    assert sync_script.get_render_service_ids() == ["srv-one"]

    monkeypatch.setenv("RENDER_SERVICE_ID", "")
    monkeypatch.setenv("RENDER_SERVICE_IDS", "srv-a, srv-b")
    assert sync_script.get_render_service_ids() == ["srv-a", "srv-b"]


def test_missing_db_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        sync_script.extract_auth_token_from_db(tmp_path / "missing.db")
