"""Collect Pakistan-security tweets via Scweet (optional, opt-in)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from loguru import logger

from app.config import get_settings
from app.integrations.scweet_client import SOURCE_NAME, build_scweet_client

DEFAULT_QUERY = (
    "(Pakistan OR Balochistan OR Quetta OR Karachi OR Peshawar OR Islamabad) "
    "(attack OR blast OR explosion OR militant OR security OR terrorism OR operation) "
    "lang:en"
)


def _parse_queries(raw: str) -> list[str]:
    if not raw.strip():
        return [DEFAULT_QUERY]
    return [q.strip() for q in raw.replace("\n", ",").split(",") if q.strip()]


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip()
    for fmt in (
        "%Y-%m-%d %H:%M:%S %z",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
    ):
        try:
            dt = datetime.strptime(text.replace("Z", "+0000"), fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def _tweet_to_item(tweet: dict[str, Any]) -> dict[str, Any]:
    user = tweet.get("user") or {}
    if not isinstance(user, dict):
        user = {}
    screen_name = user.get("screen_name") or user.get("username") or "unknown"
    text = (tweet.get("text") or tweet.get("embedded_text") or "").strip()
    tweet_url = tweet.get("tweet_url")
    if not tweet_url and tweet.get("tweet_id"):
        tweet_url = f"https://x.com/{screen_name}/status/{tweet['tweet_id']}"

    likes = tweet.get("likes", 0)
    retweets = tweet.get("retweets", 0)
    comments = tweet.get("comments", 0)
    summary = text
    if likes or retweets or comments:
        summary = f"{text}\n\n— @{screen_name} · {likes} likes · {retweets} RT · {comments} replies"

    title = text[:280] if text else f"Tweet from @{screen_name}"

    return {
        "source_name": SOURCE_NAME,
        "title": title,
        "summary": summary[:2000] if summary else None,
        "url": tweet_url,
        "published_at": _parse_timestamp(tweet.get("timestamp")),
        "country": "Pakistan",
        "province": None,
        "city": None,
        "raw_json": tweet,
    }


def collect_scweet() -> list[dict[str, Any]]:
    """
    Search X via Scweet for configured queries.
    Requires SCWEET_ENABLED=true and credentials in .env.
    """
    settings = get_settings()
    if not settings.scweet_enabled:
        logger.info("Scweet collector disabled (SCWEET_ENABLED=false).")
        return []

    if not settings.scweet_configured:
        logger.warning(
            "Scweet enabled but not configured. Set SCWEET_AUTH_TOKEN or "
            "SCWEET_COOKIES_FILE, or run Scweet once to create data/scweet_state.db."
        )
        return []

    queries = _parse_queries(settings.scweet_search_queries)
    since = (datetime.now(timezone.utc) - timedelta(days=settings.scweet_since_days)).strftime(
        "%Y-%m-%d"
    )
    limit = max(settings.scweet_limit, 1)

    try:
        client = build_scweet_client()
    except ValueError as exc:
        logger.warning(str(exc))
        return []
    except Exception as exc:
        logger.error(f"Scweet init failed: {exc}")
        return []

    items: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    for query in queries:
        try:
            logger.info(f"Scweet search: {query[:80]}… (since={since}, limit={limit})")
            tweets = client.search(
                query,
                since=since,
                limit=limit,
                lang=settings.scweet_lang or None,
                save=False,
            )
            for tweet in tweets or []:
                if not isinstance(tweet, dict):
                    continue
                item = _tweet_to_item(tweet)
                url = item.get("url")
                if url and url in seen_urls:
                    continue
                if url:
                    seen_urls.add(url)
                items.append(item)
            logger.info(f"Scweet query returned {len(tweets or [])} tweet(s)")
        except Exception as exc:
            logger.error(f"Scweet search failed for query '{query[:40]}': {exc}")

    logger.info(f"Scweet collected {len(items)} unique tweet(s)")
    return items
