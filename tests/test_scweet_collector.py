"""Scweet collector tests."""

from unittest.mock import MagicMock, patch

from app.collectors.scweet_collector import (
    DEFAULT_QUERY,
    _parse_queries,
    _tweet_to_item,
    collect_scweet,
)
from app.config import Settings


def test_parse_queries_default_when_empty():
    assert _parse_queries("") == [DEFAULT_QUERY]


def test_parse_queries_custom():
    raw = "query one, query two"
    assert _parse_queries(raw) == ["query one", "query two"]


def test_tweet_to_item_maps_fields():
    tweet = {
        "tweet_id": "123",
        "text": "Explosion reported in Quetta, Balochistan",
        "timestamp": "2026-06-01 12:00:00 +0000",
        "tweet_url": "https://x.com/news/status/123",
        "user": {"screen_name": "news", "name": "News Desk"},
        "likes": 10,
        "retweets": 2,
        "comments": 1,
    }
    item = _tweet_to_item(tweet)
    assert item["source_name"] == "X/Scweet"
    assert "Quetta" in item["title"]
    assert item["url"] == "https://x.com/news/status/123"
    assert item["published_at"] is not None


def test_collect_scweet_disabled():
    settings = Settings(_env_file=None, scweet_enabled=False)
    with patch("app.collectors.scweet_collector.get_settings", return_value=settings):
        assert collect_scweet() == []


def test_collect_scweet_runs_search(monkeypatch):
    settings = Settings(
        _env_file=None,
        scweet_enabled=True,
        scweet_auth_token="token123",
        scweet_search_queries="Pakistan security",
        scweet_limit=5,
        scweet_since_days=3,
    )
    mock_client = MagicMock()
    mock_client.search.return_value = [
        {
            "tweet_id": "1",
            "text": "Attack in Peshawar Pakistan",
            "tweet_url": "https://x.com/a/status/1",
            "user": {"screen_name": "a"},
            "timestamp": "2026-06-01 10:00:00 +0000",
        }
    ]

    with patch("app.collectors.scweet_collector.get_settings", return_value=settings):
        with patch("app.collectors.scweet_collector.build_scweet_client", return_value=mock_client):
            items = collect_scweet()

    assert len(items) == 1
    assert items[0]["source_name"] == "X/Scweet"
    mock_client.search.assert_called_once()
