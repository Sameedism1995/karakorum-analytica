"""Filter grouped incidents by keyword, date, and location."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any


@dataclass
class IncidentFilterCriteria:
    keyword: str = ""
    date_from: date | None = None
    date_to: date | None = None
    location: str = ""  # province, city, country, or alias (e.g. "Balochistan", "Karachi")


def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, date):
        dt = datetime.combine(value, datetime.min.time())
    else:
        text = str(value).strip()
        if not text:
            return None
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def incident_reference_date(incident: dict[str, Any]) -> datetime | None:
    """Prefer reported event time, then incident creation time."""
    return _parse_datetime(incident.get("event_at")) or _parse_datetime(incident.get("created_at"))


def _keyword_tokens(text: str) -> list[str]:
    return [part.strip().lower() for part in text.replace(",", " ").split() if part.strip()]


def matches_keyword(incident: dict[str, Any], keyword: str) -> bool:
    query = keyword.strip().lower()
    if not query:
        return True

    # All tokens must appear somewhere in the searchable text
    tokens = _keyword_tokens(query)
    if not tokens:
        return True

    haystack = " ".join(
        [
            str(incident.get("main_title") or ""),
            str(incident.get("keywords") or ""),
            str(incident.get("event_type") or ""),
            str(incident.get("matched_sources") or ""),
            str(incident.get("city") or ""),
            str(incident.get("province") or ""),
            str(incident.get("country") or ""),
        ]
    ).lower()

    return all(token in haystack for token in tokens)


def matches_date_range(
    incident: dict[str, Any],
    *,
    date_from: date | None,
    date_to: date | None,
) -> bool:
    if date_from is None and date_to is None:
        return True

    ref = incident_reference_date(incident)
    if ref is None:
        return False

    ref_day = ref.date()
    if date_from and ref_day < date_from:
        return False
    if date_to and ref_day > date_to:
        return False
    return True


def _normalize_location(value: str) -> str:
    return value.strip().lower().replace("-", " ")


def matches_location(incident: dict[str, Any], location: str) -> bool:
    needle = _normalize_location(location)
    if not needle or needle in {"all", "any"}:
        return True

    fields = [
        incident.get("city"),
        incident.get("province"),
        incident.get("country"),
    ]
    for field in fields:
        if not field:
            continue
        normalized = _normalize_location(str(field))
        if needle in normalized or normalized in needle:
            return True

    # Match combined "City, Province" style labels from UI
    combined = ", ".join(str(f) for f in fields if f).lower()
    return needle in combined


def filter_incidents(
    incidents: list[dict[str, Any]],
    criteria: IncidentFilterCriteria,
) -> list[dict[str, Any]]:
    """Apply all active filters; returns incidents in original order."""
    result: list[dict[str, Any]] = []
    for incident in incidents:
        if not matches_keyword(incident, criteria.keyword):
            continue
        if not matches_date_range(
            incident,
            date_from=criteria.date_from,
            date_to=criteria.date_to,
        ):
            continue
        if not matches_location(incident, criteria.location):
            continue
        result.append(incident)
    return result


def collect_location_options(incidents: list[dict[str, Any]]) -> list[str]:
    """Build sorted unique location labels for filter dropdown."""
    labels: set[str] = set()
    for incident in incidents:
        city = incident.get("city")
        province = incident.get("province")
        country = incident.get("country")
        if city and province:
            labels.add(f"{city}, {province}")
        elif city:
            labels.add(str(city))
        elif province:
            labels.add(str(province))
        elif country:
            labels.add(str(country))
    return sorted(labels, key=str.lower)
