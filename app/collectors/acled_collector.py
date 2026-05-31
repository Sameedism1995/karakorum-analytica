from datetime import datetime, timezone
from typing import Any

import httpx
from loguru import logger

from app.config import get_settings

ACLED_BASE = "https://acleddata.com/api/acled/read"


def collect_acled(limit: int = 50) -> list[dict[str, Any]]:
    """Collect Pakistan events from ACLED. Skips gracefully if credentials are missing."""
    settings = get_settings()
    if not settings.acled_configured:
        logger.warning("ACLED credentials missing; skipping ACLED collection.")
        return []

    params = {
        "key": settings.acled_api_key,
        "email": settings.acled_email,
        "country": "Pakistan",
        "limit": limit,
    }
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(ACLED_BASE, params=params)
            response.raise_for_status()
            payload = response.json()
    except Exception as exc:
        logger.error(f"ACLED collection failed: {exc}")
        return []

    results: list[dict[str, Any]] = []
    for event in payload.get("data", []):
        title = event.get("event_type") or event.get("sub_event_type") or "ACLED event"
        notes = event.get("notes") or ""
        location = event.get("location") or ""
        admin1 = event.get("admin1") or ""
        summary = f"{notes} Location: {location}, {admin1}".strip()

        published_at = None
        event_date = event.get("event_date")
        if event_date:
            try:
                published_at = datetime.strptime(event_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except ValueError:
                published_at = None

        results.append(
            {
                "source_name": "ACLED",
                "title": f"{title} - {location}",
                "summary": summary,
                "url": f"https://acleddata.com/data/?event_id={event.get('event_id', '')}",
                "published_at": published_at,
                "country": "Pakistan",
                "province": admin1 or None,
                "city": location or None,
                "raw_json": event,
            }
        )

    logger.info(f"ACLED collected {len(results)} items")
    return results
