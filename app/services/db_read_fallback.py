"""SQL read helpers with Supabase REST fallback for IPv4-only hosts (e.g. Render)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from loguru import logger
from sqlalchemy.exc import SQLAlchemyError

T = TypeVar("T")


def sql_or_rest(sql_fn: Callable[[], T], rest_fn: Callable[[], T | None]) -> T:
    """Run a SQL-backed read; fall back to Supabase REST when Postgres is down."""
    try:
        return sql_fn()
    except SQLAlchemyError as exc:
        logger.warning(f"SQL read failed, trying Supabase REST: {exc}")
        fallback = rest_fn()
        if fallback is not None:
            return fallback
        raise
