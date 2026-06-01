import json
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from loguru import logger
from sqlalchemy.orm import Session

from app.collectors.acled_collector import collect_acled
from app.collectors.gdelt_collector import collect_gdelt
from app.collectors.news_channels_collector import collect_news_channels
from app.collectors.reliefweb_collector import collect_reliefweb
from app.collectors.scweet_collector import collect_scweet
from app.models.raw_news import RawNews
from app.processors.pakistan_filter import filter_pakistan_item, has_security_keyword
from app.services.dedup_service import content_hash_for_item, extract_tweet_id

ProgressCallback = Callable[[str, int, str], None]


def _serialize_raw(raw: Any) -> str:
    return json.dumps(raw, default=str)


def save_raw_news(db: Session, item: dict) -> RawNews | None:
    """Save normalized item if not duplicate (tweet id, URL, or content_hash)."""
    url = item.get("url")
    title = item.get("title")
    source_name = item["source_name"]
    content_hash = content_hash_for_item(item)

    if db.query(RawNews).filter(RawNews.content_hash == content_hash).first():
        return None

    tweet_id = extract_tweet_id(item)
    if tweet_id:
        existing = (
            db.query(RawNews)
            .filter(RawNews.source_name == source_name, RawNews.raw_json.contains(f'"tweet_id": "{tweet_id}"'))
            .first()
        )
        if not existing:
            existing = (
                db.query(RawNews)
                .filter(RawNews.source_name == source_name, RawNews.raw_json.contains(f'"tweet_id": {tweet_id}'))
                .first()
            )
        if existing:
            return None

    if url and db.query(RawNews).filter(RawNews.url == url).first():
        return None

    media_urls_json = item.get("media_urls")
    if media_urls_json is None and isinstance(item.get("raw_json"), dict):
        stored = (item.get("raw_json") or {}).get("stored_media") or []
        if stored:
            import json as _json

            media_urls_json = _json.dumps([m.get("public_url") for m in stored if m.get("public_url")])

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
        media_urls=media_urls_json if isinstance(media_urls_json, str) else None,
        content_hash=content_hash,
        status="collected",
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def collect_all(
    db: Session,
    on_progress: ProgressCallback | None = None,
) -> dict[str, int]:
    """Run all collectors, filter, and save raw news."""

    def report(message: str, progress: int, step: str) -> None:
        if on_progress:
            on_progress(message, progress, step)

    all_items: list[dict] = []

    report("Fetching GDELT security news…", 10, "gdelt")
    gdelt_items = collect_gdelt()
    all_items.extend(gdelt_items)
    report(f"GDELT returned {len(gdelt_items)} articles", 22, "gdelt")

    report("Fetching ReliefWeb reports…", 28, "reliefweb")
    reliefweb_items = collect_reliefweb()
    all_items.extend(reliefweb_items)
    report(f"ReliefWeb returned {len(reliefweb_items)} reports", 38, "reliefweb")

    report("Fetching ACLED events…", 42, "acled")
    acled_items = collect_acled()
    all_items.extend(acled_items)
    report(f"ACLED returned {len(acled_items)} events", 50, "acled")

    report("Fetching open news channel RSS feeds…", 52, "news_web")
    news_items = collect_news_channels()
    all_items.extend(news_items)
    report(f"News channels returned {len(news_items)} headlines", 58, "news_web")

    report("Searching X via Scweet…", 59, "scweet")
    scweet_items = collect_scweet()
    all_items.extend(scweet_items)
    report(f"Scweet returned {len(scweet_items)} tweets", 61, "scweet")

    report("Fetching watched X profiles…", 62, "x_watch")
    from app.services.x_watch_service import collect_all_watch_accounts

    watch_stats = collect_all_watch_accounts(db, on_progress=on_progress)
    report(
        f"Watch list: saved {watch_stats.get('saved', 0)} tweet(s) from "
        f"{watch_stats.get('handles', 0)} account(s)",
        64,
        "x_watch",
    )

    report(f"Filtering and saving {len(all_items)} items…", 65, "save")
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

    report(
        f"Saved {saved} new articles ({skipped} duplicates, {filtered_out} filtered out)",
        68,
        "save",
    )
    logger.info(
        f"Collection complete: saved={saved}, duplicates={skipped}, filtered_out={filtered_out}"
    )
    return {
        "saved": saved,
        "duplicates": skipped,
        "filtered_out": filtered_out,
        "fetched": len(all_items),
        "x_watch": watch_stats,
    }


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
