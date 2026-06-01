"""Aggregate dashboard statistics from the database."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.draft_post import DraftPost  # noqa: F401
from app.models.incident import Incident
from app.models.posted_item import PostedItem  # noqa: F401
from app.models.raw_news import RawNews


def get_dashboard_stats(db: Session) -> dict:
    """Return cumulative totals and breakdowns (not limited to recent page size)."""
    total_raw = db.query(func.count(RawNews.id)).scalar() or 0
    total_incidents = db.query(func.count(Incident.id)).scalar() or 0
    total_drafts = db.query(func.count(DraftPost.id)).scalar() or 0

    sources_active = (
        db.query(func.count(func.distinct(RawNews.source_name))).scalar() or 0
    )

    status_rows = (
        db.query(Incident.status, func.count(Incident.id))
        .group_by(Incident.status)
        .all()
    )
    status_counts = {status: count for status, count in status_rows}

    last_collection = "—"
    latest_collected = db.query(func.max(RawNews.collected_at)).scalar()
    if latest_collected:
        if isinstance(latest_collected, datetime):
            dt = latest_collected
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = latest_collected
        last_collection = dt.strftime("%Y-%m-%d %H:%M UTC")

    return {
        "total_raw": total_raw,
        "total_incidents": total_incidents,
        "total_drafts": total_drafts,
        "sources_active": sources_active,
        "ready_for_review": status_counts.get("ready_for_review", 0),
        "needs_review": status_counts.get("needs_review", 0),
        "save_only": status_counts.get("save_only", 0),
        "last_collection": last_collection,
    }
