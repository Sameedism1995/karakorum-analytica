"""Collect headlines from configured open news RSS feeds."""

from __future__ import annotations

from typing import Any

from loguru import logger

from app.config import get_settings
from app.scraping.fetch import NewsFetcher
from app.scraping.rss import fetch_feed, parse_feed_config


def collect_news_channels() -> list[dict[str, Any]]:
    """
    Fetch public RSS feeds listed in NEWS_CHANNEL_FEEDS.
    Uses proxy rotation / ScraperAPI when configured in .env.
    """
    settings = get_settings()
    feeds = parse_feed_config(settings.news_channel_feeds)
    if not feeds:
        logger.info(
            "No news channel feeds configured. Set NEWS_CHANNEL_FEEDS in .env "
            "(e.g. Dawn|https://www.dawn.com/feeds/home)."
        )
        return []

    fetcher = NewsFetcher()
    all_items: list[dict[str, Any]] = []
    errors = 0

    for source_name, feed_url in feeds:
        try:
            items = fetch_feed(source_name, feed_url, fetcher=fetcher)
            all_items.extend(items)
        except PermissionError as exc:
            logger.warning(str(exc))
            errors += 1
        except Exception as exc:
            logger.error(f"News feed failed ({source_name}): {exc}")
            errors += 1

    logger.info(
        f"News channels collected {len(all_items)} items from {len(feeds)} feed(s)"
        + (f", {errors} feed error(s)" if errors else "")
    )
    return all_items
