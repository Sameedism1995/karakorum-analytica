import json
import threading
import time
from datetime import datetime, timezone
from typing import Any

import httpx
from loguru import logger

GDELT_BASE = "https://api.gdeltproject.org/api/v2/doc/doc"
GDELT_MIN_INTERVAL_SECONDS = 10
GDELT_429_BACKOFF_SECONDS = (15, 30, 45)

_last_gdelt_request_at: float = 0.0
_gdelt_lock = threading.Lock()

SECURITY_QUERY = (
    "Pakistan (Balochistan OR Quetta OR Karachi OR Peshawar OR Islamabad OR Lahore) "
    "(attack OR blast OR explosion OR militant OR terrorism OR operation OR security OR police)"
)


def _parse_gdelt_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        if len(value) >= 8 and value[0].isdigit():
            if "T" in value:
                dt = datetime.strptime(value.replace("Z", ""), "%Y%m%dT%H%M%S")
            else:
                dt = datetime.strptime(value[:8], "%Y%m%d")
            return dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    return None


def _wait_for_gdelt_rate_limit() -> None:
    global _last_gdelt_request_at
    elapsed = time.time() - _last_gdelt_request_at
    if elapsed < GDELT_MIN_INTERVAL_SECONDS:
        time.sleep(GDELT_MIN_INTERVAL_SECONDS - elapsed)


def _fetch_gdelt(params: dict[str, Any]) -> dict[str, Any]:
    global _last_gdelt_request_at
    headers = {"User-Agent": "pakistan-osint-news-mvp/1.0 (public research)"}

    for attempt in range(len(GDELT_429_BACKOFF_SECONDS) + 1):
        _wait_for_gdelt_rate_limit()
        with httpx.Client(timeout=45.0, headers=headers) as client:
            response = client.get(GDELT_BASE, params=params)
            _last_gdelt_request_at = time.time()

        if response.status_code == 429:
            if attempt >= len(GDELT_429_BACKOFF_SECONDS):
                break
            wait = GDELT_429_BACKOFF_SECONDS[attempt]
            logger.warning(
                f"GDELT rate limited; waiting {wait}s (attempt {attempt + 1}/{len(GDELT_429_BACKOFF_SECONDS) + 1})"
            )
            time.sleep(wait)
            continue

        if response.status_code >= 400:
            logger.warning(f"GDELT HTTP {response.status_code}: {response.text[:200]}")
            time.sleep(GDELT_MIN_INTERVAL_SECONDS)
            continue

        try:
            return response.json()
        except json.JSONDecodeError:
            logger.warning(f"GDELT returned non-JSON response: {response.text[:200]}")
            time.sleep(GDELT_MIN_INTERVAL_SECONDS)
            continue

    raise httpx.HTTPStatusError(
        "GDELT rate limit exceeded after retries",
        request=response.request,
        response=response,
    )


def collect_gdelt(max_records: int = 25) -> list[dict[str, Any]]:
    """Collect Pakistan-related security news from GDELT Doc API."""
    with _gdelt_lock:
        return _collect_gdelt_locked(max_records)


def _collect_gdelt_locked(max_records: int = 25) -> list[dict[str, Any]]:
    params = {
        "query": SECURITY_QUERY,
        "mode": "ArtList",
        "format": "json",
        "maxrecords": max_records,
        "sort": "DateDesc",
        "timespan": "7d",
    }
    try:
        payload = _fetch_gdelt(params)
    except Exception as exc:
        logger.error(f"GDELT collection failed: {exc}")
        return []

    articles = payload.get("articles", [])
    results: list[dict[str, Any]] = []
    for article in articles:
        title = article.get("title")
        url = article.get("url")
        if not title and not url:
            continue
        results.append(
            {
                "source_name": "GDELT",
                "title": title,
                "summary": f"{article.get('domain', '')} {article.get('sourcecountry', '')} {title or ''}",
                "url": url,
                "published_at": _parse_gdelt_date(article.get("seendate")),
                "country": "Pakistan",
                "province": None,
                "city": None,
                "raw_json": article,
            }
        )
    logger.info(f"GDELT collected {len(results)} items")
    return results
