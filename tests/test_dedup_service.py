"""Tests for ingest deduplication."""

from app.services.dedup_service import content_hash_for_item, extract_tweet_id


def test_extract_tweet_id_from_url():
    item = {"url": "https://x.com/user/status/1234567890", "raw_json": {}}
    assert extract_tweet_id(item) == "1234567890"


def test_content_hash_stable_for_tweet_id():
    item = {
        "source_name": "X/Scweet",
        "title": "hello",
        "url": "https://x.com/a/status/1",
        "raw_json": {"tweet_id": "99"},
    }
    h1 = content_hash_for_item(item)
    item2 = dict(item)
    item2["title"] = "different title"
    assert content_hash_for_item(item2) == h1
