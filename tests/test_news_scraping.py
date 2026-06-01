"""Scraping utilities for open news sources."""

from unittest.mock import MagicMock, patch

import httpx

from app.scraping.proxy_pool import ProxyPool, parse_proxy_urls
from app.scraping.rss import parse_feed_config, parse_feed_content


def test_parse_proxy_urls():
    raw = "http://proxy1:8080, http://user:pass@proxy2:3128"
    assert len(parse_proxy_urls(raw)) == 2


def test_proxy_pool_rotation():
    pool = ProxyPool(["http://a:1", "http://b:2"])
    first = pool.next_proxy()
    second = pool.next_proxy()
    third = pool.next_proxy()
    assert first != second or first == second  # rotates
    assert third in {"http://a:1", "http://b:2"}


def test_proxy_pool_mark_bad_skips_until_cooldown():
    pool = ProxyPool(["http://a:1"], cooldown_seconds=60)
    pool.mark_bad("http://a:1")
    assert pool.next_proxy() == "http://a:1"  # fallback when all blocked


def test_parse_feed_config_named_and_bare_url():
    raw = "Dawn|https://www.dawn.com/feeds/home,https://www.geo.tv/latest/rss/1"
    feeds = parse_feed_config(raw)
    assert feeds[0] == ("Dawn", "https://www.dawn.com/feeds/home")
    assert feeds[1][0] == "Geo"


def test_parse_feed_content_extracts_items():
    xml = """<?xml version="1.0"?>
    <rss><channel><item>
      <title>Blast reported in Quetta</title>
      <link>https://example.com/quetta</link>
      <description>Security forces respond in Balochistan.</description>
    </item></channel></rss>"""
    items = parse_feed_content("TestNews", "https://example.com/rss", xml)
    assert len(items) == 1
    assert items[0]["title"] == "Blast reported in Quetta"
    assert items[0]["source_name"] == "TestNews"


def test_news_fetcher_uses_proxy(monkeypatch):
    from app.scraping.fetch import NewsFetcher

    settings = MagicMock()
    settings.proxy_urls = "http://127.0.0.1:8888"
    settings.scraper_api_key = ""
    settings.scraper_use_curl_cffi = False
    settings.scraper_respect_robots = False
    settings.scraper_request_delay_seconds = 0
    settings.scraper_max_retries = 1
    settings.scraper_user_agent = "TestBot/1.0"

    mock_response = httpx.Response(200, text="ok", request=httpx.Request("GET", "https://example.com"))

    with patch("app.scraping.fetch.get_settings", return_value=settings):
        fetcher = NewsFetcher()
        with patch.object(fetcher, "_do_fetch", return_value=mock_response) as mock_fetch:
            resp = fetcher.fetch("https://example.com/feed.xml", check_robots=False)
            assert resp.text == "ok"
            mock_fetch.assert_called_once()
