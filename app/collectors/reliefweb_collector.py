from datetime import datetime, timezone
from typing import Any

import httpx
from loguru import logger

from app.config import get_settings

RELIEFWEB_BASE = "https://api.reliefweb.int/v2/reports"

SECURITY_TERMS = (
    "security OR conflict OR violence OR attack OR terrorism OR militant OR "
    "explosion OR protest OR border OR kidnapping OR operation"
)


def collect_reliefweb(limit: int = 50) -> list[dict[str, Any]]:
    """Collect Pakistan reports from ReliefWeb and filter for security-related content."""
    settings = get_settings()
    if not settings.reliefweb_appname:
        logger.warning(
            "ReliefWeb appname missing; skipping ReliefWeb collection. "
            "Request an approved appname at https://apidoc.reliefweb.int/parameters#appname "
            "and set RELIEFWEB_APPNAME in .env."
        )
        return []

    params = {
        "appname": settings.reliefweb_appname,
        "limit": limit,
        "query[value]": SECURITY_TERMS,
        "filter[field]": "country",
        "filter[value]": "Pakistan",
    }
    payload_body = {
        "fields": {"include": ["title", "url", "date", "body", "country", "source"]},
    }
    headers = {"User-Agent": "KarakorumAnalytica/1.0", "Content-Type": "application/json"}

    try:
        with httpx.Client(timeout=30.0, headers=headers) as client:
            response = client.post(
                RELIEFWEB_BASE,
                params=params,
                json=payload_body,
            )
            response.raise_for_status()
            payload = response.json()
    except Exception as exc:
        logger.error(f"ReliefWeb collection failed: {exc}")
        return []

    results: list[dict[str, Any]] = []
    for item in payload.get("data", []):
        fields = item.get("fields", {})
        title = fields.get("title")
        url_field = fields.get("url")
        url = None
        if isinstance(url_field, str):
            url = url_field
        elif isinstance(url_field, list) and url_field:
            first = url_field[0]
            url = first if isinstance(first, str) else first.get("url")

        body = fields.get("body", "")
        summary = body[:500] if isinstance(body, str) else str(body)[:500]

        published_at = None
        date_field = fields.get("date", {})
        if isinstance(date_field, dict) and date_field.get("created"):
            try:
                published_at = datetime.fromisoformat(
                    date_field["created"].replace("Z", "+00:00")
                )
            except ValueError:
                published_at = None

        if not title and not url:
            continue

        results.append(
            {
                "source_name": "ReliefWeb",
                "title": title,
                "summary": summary,
                "url": url,
                "published_at": published_at,
                "country": "Pakistan",
                "province": None,
                "city": None,
                "raw_json": item,
            }
        )

    logger.info(f"ReliefWeb collected {len(results)} items")
    return results
