"""Persist Scweet tweet items into raw_news (Supabase/SQLite via SQLAlchemy)."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from loguru import logger

from app.config import get_settings
from app.integrations.supabase_media import (
    attach_stored_media_to_item,
    upload_tweet_media,
)
from app.services.collection_service import save_raw_news


def _maybe_upload_media(item: dict[str, Any]) -> None:
    settings = get_settings()
    if not settings.supabase_configured:
        return
    raw = item.get("raw_json")
    if not isinstance(raw, dict):
        return
    try:
        stored = upload_tweet_media(raw)
        attach_stored_media_to_item(item, stored)
    except Exception as exc:
        logger.debug(f"Media upload skipped: {exc}")


def persist_scweet_items(
    db: Session,
    items: list[dict[str, Any]],
    *,
    apply_pipeline_filters: bool = False,
) -> dict[str, int]:
    """
    Save normalized Scweet items to raw_news.

    When apply_pipeline_filters is False (watch list / explicit persist), all tweets are stored.
    """
    saved = 0
    skipped = 0
    filtered_out = 0

    for item in items:
        payload = dict(item)
        if apply_pipeline_filters:
            from app.processors.pakistan_filter import filter_pakistan_item, has_security_keyword

            if not has_security_keyword(payload.get("title"), payload.get("summary")):
                filtered_out += 1
                continue
            filtered = filter_pakistan_item(payload)
            if filtered is None:
                filtered_out += 1
                continue
            payload = filtered

        _maybe_upload_media(payload)
        if save_raw_news(db, payload):
            saved += 1
        else:
            skipped += 1

    return {"saved": saved, "duplicates": skipped, "filtered_out": filtered_out}
