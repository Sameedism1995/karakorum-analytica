"""Tests for SQL → Supabase REST read fallback."""

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.exc import OperationalError

from app.services.db_read_fallback import sql_or_rest


def test_sql_or_rest_uses_sql_when_healthy():
    result = sql_or_rest(lambda: {"total_raw": 3}, lambda: {"total_raw": 99})
    assert result["total_raw"] == 3


def test_sql_or_rest_falls_back_on_sqlalchemy_error():
    def failing_sql():
        raise OperationalError("stmt", {}, Exception("connection failed"))

    result = sql_or_rest(failing_sql, lambda: {"total_raw": 6, "_via": "supabase_rest"})
    assert result["total_raw"] == 6


def test_sql_or_rest_reraises_when_both_fail():
    def failing_sql():
        raise OperationalError("stmt", {}, Exception("connection failed"))

    with pytest.raises(OperationalError):
        sql_or_rest(failing_sql, lambda: None)


def test_parse_root_health_rest_only():
    from dashboard.api_client import _parse_root_health

    data = {
        "status": "running",
        "database": {"using_supabase": True, "connected": False, "error": "ipv6"},
        "supabase": {"configured": True, "api_ok": True},
    }
    parsed = _parse_root_health(data)
    assert parsed["ok"] is True
    assert parsed["degraded"] is True


def test_parse_root_health_fully_down():
    from dashboard.api_client import _parse_root_health

    data = {
        "status": "running",
        "database": {"using_supabase": True, "connected": False},
        "supabase": {"configured": True, "api_ok": False},
    }
    parsed = _parse_root_health(data)
    assert parsed["ok"] is False
