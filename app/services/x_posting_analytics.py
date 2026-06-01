"""Posting schedule analytics for watched X accounts (from raw_news history)."""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.integrations.scweet_client import SOURCE_NAME
from app.models.raw_news import RawNews

# Pakistan local time for analyst-friendly schedules
DEFAULT_TZ = ZoneInfo("Asia/Karachi")
_URL_HANDLE_RE = re.compile(r"(?:x\.com|twitter\.com)/([A-Za-z0-9_]{1,15})/", re.I)


def _aware_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _handle_from_url(url: str | None) -> str | None:
    if not url:
        return None
    match = _URL_HANDLE_RE.search(url)
    return match.group(1).lower() if match else None


def _handle_from_raw_json(raw: str | None) -> str | None:
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    user = data.get("user")
    if isinstance(user, dict):
        name = user.get("screen_name") or user.get("username")
        if name:
            return str(name).lstrip("@").lower()
    return None


def _tweet_belongs_to_handle(record: RawNews, handle: str) -> bool:
    handle = handle.lower()
    from_url = _handle_from_url(record.url)
    if from_url == handle:
        return True
    from_json = _handle_from_raw_json(record.raw_json)
    return from_json == handle


def _circular_mean_hour(hours: list[float]) -> float | None:
    if not hours:
        return None
    sin_sum = sum(math.sin(2 * math.pi * h / 24) for h in hours)
    cos_sum = sum(math.cos(2 * math.pi * h / 24) for h in hours)
    if sin_sum == 0 and cos_sum == 0:
        return None
    angle = math.atan2(sin_sum / len(hours), cos_sum / len(hours))
    mean = angle * 24 / (2 * math.pi)
    if mean < 0:
        mean += 24
    return mean


def _format_hour_local(hour_float: float, tz: ZoneInfo = DEFAULT_TZ) -> str:
    hour = int(hour_float) % 24
    minute = int(round((hour_float - int(hour_float)) * 60)) % 60
    label = datetime(2000, 1, 1, hour, minute, tzinfo=timezone.utc).strftime("%H:%M")
    tz_abbr = datetime.now(tz).strftime("%Z")
    return f"{label} {tz_abbr}"


def compute_posting_stats(
    db: Session,
    handle: str,
    *,
    lookback_days: int = 30,
    tz: ZoneInfo = DEFAULT_TZ,
) -> dict[str, Any]:
    """
    Derive posting cadence from stored X/Scweet tweets for one handle.

    Returns averages useful for scheduling automated fetches.
    """
    handle = handle.lower()
    cutoff = datetime.now(timezone.utc) - timedelta(days=max(lookback_days, 1))

    rows = (
        db.query(RawNews)
        .filter(
            RawNews.source_name == SOURCE_NAME,
            RawNews.published_at.isnot(None),
            RawNews.published_at >= cutoff,
        )
        .order_by(RawNews.published_at.asc())
        .all()
    )

    timestamps: list[datetime] = []
    for row in rows:
        if not _tweet_belongs_to_handle(row, handle):
            continue
        if row.published_at:
            timestamps.append(_aware_utc(row.published_at))

    if len(timestamps) < 2:
        return {
            "sample_size": len(timestamps),
            "lookback_days": lookback_days,
            "ready": False,
            "summary": "Need more stored tweets (fetch profile twice)",
            "avg_posts_per_day": None,
            "avg_post_time_local": None,
            "peak_post_times_local": [],
            "active_hours_local": [],
        }

    first = timestamps[0]
    last = timestamps[-1]
    span_seconds = max((last - first).total_seconds(), 3600)
    span_days = span_seconds / 86400
    avg_posts_per_day = round(len(timestamps) / span_days, 2)

    local_hours: list[float] = []
    hour_counts: Counter[int] = Counter()
    for ts in timestamps:
        local = ts.astimezone(tz)
        hour_frac = local.hour + local.minute / 60.0
        local_hours.append(hour_frac)
        hour_counts[local.hour] += 1

    mean_hour = _circular_mean_hour(local_hours)
    avg_post_time_local = _format_hour_local(mean_hour, tz) if mean_hour is not None else None

    peak_hours = [h for h, _ in hour_counts.most_common(3)]
    peak_post_times_local = [_format_hour_local(float(h), tz) for h in peak_hours]

    # Hours covering ~70% of posts (for cron windows)
    total = len(timestamps)
    active_hours: list[int] = []
    running = 0
    for hour, count in hour_counts.most_common():
        active_hours.append(hour)
        running += count
        if running >= total * 0.7:
            break
    active_hours_local = sorted(
        [_format_hour_local(float(h), tz) for h in active_hours],
        key=lambda label: int(label.split(":")[0]),
    )

    if avg_posts_per_day >= 1:
        cadence = f"~{avg_posts_per_day:.1f} posts/day"
    else:
        cadence = f"~{round(avg_posts_per_day * 7, 1)} posts/week"

    summary = cadence
    if avg_post_time_local:
        summary += f" · avg time {avg_post_time_local}"
    if peak_post_times_local:
        summary += f" · peaks {', '.join(peak_post_times_local[:2])}"

    return {
        "sample_size": len(timestamps),
        "lookback_days": lookback_days,
        "observed_days": round(span_days, 1),
        "ready": True,
        "summary": summary,
        "avg_posts_per_day": avg_posts_per_day,
        "avg_post_time_local": avg_post_time_local,
        "peak_post_times_local": peak_post_times_local,
        "active_hours_local": active_hours_local,
        "first_post_at": first.isoformat(),
        "last_post_at": last.isoformat(),
    }


def compute_posting_stats_map(
    db: Session,
    handles: list[str],
    **kwargs: Any,
) -> dict[str, dict[str, Any]]:
    return {handle: compute_posting_stats(db, handle, **kwargs) for handle in handles}
