from datetime import datetime, timezone

from loguru import logger
from sqlalchemy.orm import Session

from app.models.incident import Incident
from app.models.raw_news import RawNews
from app.processors.confidence_scorer import incident_status_from_score, score_confidence
from app.processors.incident_matcher import group_items_into_incidents
from app.processors.keyword_extractor import keywords_to_string


def _group_event_at(items: list[dict]) -> datetime | None:
    """Latest published_at among grouped raw items (incident event time)."""
    dates: list[datetime] = []
    for item in items:
        published = item.get("published_at")
        if isinstance(published, datetime):
            dt = published
        elif published is not None:
            try:
                dt = datetime.fromisoformat(str(published).replace("Z", "+00:00"))
            except ValueError:
                continue
        else:
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        dates.append(dt)
    return max(dates) if dates else None


def _raw_to_item(record: RawNews) -> dict:
    return {
        "source_name": record.source_name,
        "title": record.title,
        "summary": record.summary,
        "url": record.url,
        "published_at": record.published_at,
        "country": record.country,
        "province": record.province,
        "city": record.city,
    }


def process_incidents(db: Session) -> dict[str, int]:
    """Group raw news into incidents, score confidence, and persist."""
    records = db.query(RawNews).order_by(RawNews.collected_at.desc()).all()
    if not records:
        return {"incidents_created": 0, "incidents_updated": 0}

    items = [_raw_to_item(r) for r in records]
    groups = group_items_into_incidents(items)

    created = 0
    updated = 0

    for group in groups:
        sources = group["sources"]
        confidence = score_confidence(sources)
        status = incident_status_from_score(confidence)
        kw_str = keywords_to_string(group["keywords"])
        event_at = _group_event_at(group["items"])

        existing = (
            db.query(Incident)
            .filter(Incident.main_title == group["main_title"])
            .filter(Incident.province == group.get("province"))
            .first()
        )

        if existing:
            existing.confidence_score = confidence
            existing.matched_sources = ", ".join(sources)
            existing.keywords = kw_str
            existing.status = status
            existing.event_type = group.get("event_type")
            existing.event_at = event_at
            updated += 1
        else:
            incident = Incident(
                main_title=group["main_title"],
                country=group.get("country") or "Pakistan",
                province=group.get("province"),
                city=group.get("city"),
                event_type=group.get("event_type"),
                confidence_score=confidence,
                matched_sources=", ".join(sources),
                keywords=kw_str,
                event_at=event_at,
                status=status,
            )
            db.add(incident)
            created += 1

    db.commit()
    logger.info(f"Incidents processed: created={created}, updated={updated}")
    return {"incidents_created": created, "incidents_updated": updated}


def list_incidents(db: Session, limit: int = 100) -> list[Incident]:
    return db.query(Incident).order_by(Incident.created_at.desc()).limit(limit).all()


def incident_to_dict(incident: Incident) -> dict:
    return {
        "id": incident.id,
        "main_title": incident.main_title,
        "country": incident.country,
        "province": incident.province,
        "city": incident.city,
        "event_type": incident.event_type,
        "confidence_score": incident.confidence_score,
        "matched_sources": incident.matched_sources,
        "keywords": incident.keywords,
        "status": incident.status,
        "event_at": incident.event_at.isoformat() if incident.event_at else None,
        "created_at": incident.created_at.isoformat(),
    }
