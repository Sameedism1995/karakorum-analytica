import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from loguru import logger
from sqlalchemy.orm import Session

from app.collectors.acled_collector import collect_acled
from app.collectors.gdelt_collector import collect_gdelt
from app.collectors.reliefweb_collector import collect_reliefweb
from app.models.raw_news import RawNews
from app.processors.pakistan_filter import filter_pakistan_item, has_security_keyword


def _content_hash(title: str | None, url: str | None, source_name: str) -> str:
    raw = f"{source_name}|{url or ''}|{title or ''}".lower().strip()
    return hashlib.sha256(raw.encode()).hexdigest()


def _serialize_raw(raw: Any) -> str:
    return json.dumps(raw, default=str)


def save_raw_news(db: Session, item: dict) -> RawNews | None:
    """Save normalized item if not duplicate (URL or content_hash)."""
    url = item.get("url")
    title = item.get("title")
    source_name = item["source_name"]
    content_hash = _content_hash(title, url, source_name)

    if db.query(RawNews).filter(RawNews.content_hash == content_hash).first():
        return None
    if url and db.query(RawNews).filter(RawNews.url == url).first():
        return None

    record = RawNews(
        source_name=source_name,
        title=title,
        summary=item.get("summary"),
        url=url,
        published_at=item.get("published_at"),
        collected_at=datetime.now(timezone.utc),
        country=item.get("country"),
        province=item.get("province"),
        city=item.get("city"),
        raw_json=_serialize_raw(item.get("raw_json")),
        content_hash=content_hash,
        status="collected",
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def collect_all(db: Session) -> dict[str, int]:
    """Run all collectors, filter, and save raw news."""
    all_items: list[dict] = []
    all_items.extend(collect_gdelt())
    all_items.extend(collect_reliefweb())
    all_items.extend(collect_acled())

    saved = 0
    skipped = 0
    filtered_out = 0

    for item in all_items:
        if not has_security_keyword(item.get("title"), item.get("summary")):
            filtered_out += 1
            continue

        filtered = filter_pakistan_item(item)
        if filtered is None:
            filtered_out += 1
            continue

        result = save_raw_news(db, filtered)
        if result:
            saved += 1
        else:
            skipped += 1

    logger.info(
        f"Collection complete: saved={saved}, duplicates={skipped}, filtered_out={filtered_out}"
    )
    return {"saved": saved, "duplicates": skipped, "filtered_out": filtered_out, "fetched": len(all_items)}


def get_recent_raw_news(db: Session, limit: int = 100) -> list[RawNews]:
    return db.query(RawNews).order_by(RawNews.collected_at.desc()).limit(limit).all()


def raw_news_to_dict(record: RawNews) -> dict:
    return {
        "id": record.id,
        "source_name": record.source_name,
        "title": record.title,
        "summary": record.summary,
        "url": record.url,
        "published_at": record.published_at.isoformat() if record.published_at else None,
        "collected_at": record.collected_at.isoformat(),
        "country": record.country,
        "province": record.province,
        "city": record.city,
        "content_hash": record.content_hash,
        "status": record.status,
    }
