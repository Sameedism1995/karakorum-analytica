"""Tests for incident filtering logic."""

from datetime import date, datetime, timezone

from app.services.incident_filter import (
    IncidentFilterCriteria,
    filter_incidents,
    matches_keyword,
    matches_location,
)


def _sample_incidents() -> list[dict]:
    return [
        {
            "id": 1,
            "main_title": "Blast in Quetta market",
            "keywords": "blast, quetta, market",
            "city": "Quetta",
            "province": "Balochistan",
            "country": "Pakistan",
            "event_at": "2026-05-20T10:00:00+00:00",
            "created_at": "2026-05-21T08:00:00+00:00",
        },
        {
            "id": 2,
            "main_title": "Protest in Karachi",
            "keywords": "protest, karachi",
            "city": "Karachi",
            "province": "Sindh",
            "country": "Pakistan",
            "event_at": "2026-05-25T14:00:00+00:00",
            "created_at": "2026-05-25T16:00:00+00:00",
        },
    ]


def test_keyword_filter_requires_all_tokens():
    incidents = _sample_incidents()
    criteria = IncidentFilterCriteria(keyword="blast quetta")
    assert len(filter_incidents(incidents, criteria)) == 1
    assert filter_incidents(incidents, IncidentFilterCriteria(keyword="karachi"))[0]["id"] == 2


def test_date_filter_uses_event_at():
    incidents = _sample_incidents()
    criteria = IncidentFilterCriteria(
        date_from=date(2026, 5, 24),
        date_to=date(2026, 5, 26),
    )
    result = filter_incidents(incidents, criteria)
    assert len(result) == 1
    assert result[0]["id"] == 2


def test_location_filter_city_province_label():
    incidents = _sample_incidents()
    assert matches_location(incidents[0], "Quetta, Balochistan")
    assert matches_location(incidents[1], "Karachi")
    assert not matches_location(incidents[0], "Islamabad")


def test_keyword_in_keywords_field():
    assert matches_keyword(
        {"main_title": "Security update", "keywords": "militant, border"},
        "militant",
    )
