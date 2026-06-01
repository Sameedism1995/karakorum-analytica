"""Parse RSS/Atom feeds from open news channels."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import feedparser
from loguru import logger

from app.scraping.fetch import NewsFetcher


def _parse_published(entry: dict[str, Any]) -> datetime | None:
    for key in ("published_parsed", "updated_parsed"):
        parsed = entry.get(key)
        if parsed:
            try:
                return datetime(*parsed[:6], tzinfo=timezone.utc)
            except (TypeError, ValueError):
                continue
    return None


def _entry_summary(entry: dict[str, Any]) -> str | None:
    for key in ("summary", "description", "content"):
        value = entry.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()[:1000]
        if isinstance(value, list) and value:
            first = value[0]
            if isinstance(first, dict) and first.get("value"):
                return str(first["value"]).strip()[:1000]
    return None


def parse_feed_content(source_name: str, feed_url: str, raw_xml: str) -> list[dict[str, Any]]:
    parsed = feedparser.parse(raw_xml)
    items: list[dict[str, Any]] = []

    for entry in parsed.entries:
        title = (entry.get("title") or "").strip()
        link = (entry.get("link") or "").strip()
        if not title and not link:
            continue
        items.append(
            {
                "source_name": source_name,
                "title": title or None,
                "summary": _entry_summary(entry),
                "url": link or None,
                "published_at": _parse_published(entry),
                "country": "Pakistan",
                "province": None,
                "city": None,
                "raw_json": dict(entry),
            }
        )

    logger.info(f"Parsed {len(items)} items from {source_name} ({feed_url})")
    return items


def fetch_feed(source_name: str, feed_url: str, fetcher: NewsFetcher | None = None) -> list[dict[str, Any]]:
    fetcher = fetcher or NewsFetcher()
    response = fetcher.fetch(feed_url, check_robots=True)
    return parse_feed_content(source_name, feed_url, response.text)


def parse_feed_config(raw: str) -> list[tuple[str, str]]:
    """
    Parse NEWS_CHANNEL_FEEDS entries:
      Dawn|https://www.dawn.com/feeds/home
      https://example.com/rss   (hostname used as source name)
    """
    feeds: list[tuple[str, str]] = []
    for line in raw.replace("\n", ",").split(","):
        chunk = line.strip()
        if not chunk:
            continue
        if "|" in chunk:
            name, url = chunk.split("|", 1)
            feeds.append((name.strip(), url.strip()))
        else:
            host = urlparse(chunk).netloc.replace("www.", "").split(".")[0]
            feeds.append((host.title(), chunk))
    return feeds
