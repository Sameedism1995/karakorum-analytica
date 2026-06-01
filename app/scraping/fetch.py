"""HTTP fetch layer with proxy rotation for open news pages and feeds."""

from __future__ import annotations

import time
from typing import Any
from urllib.parse import quote

import httpx
from loguru import logger
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import get_settings
from app.scraping.proxy_pool import ProxyPool, parse_proxy_urls
from app.scraping.robots import DEFAULT_UA, allowed_to_fetch

_last_request_at: float = 0.0


def _brand_user_agent() -> str:
    try:
        from fake_useragent import UserAgent

        return UserAgent().chrome
    except Exception:
        return DEFAULT_UA


def _rate_limit(delay_seconds: float) -> None:
    global _last_request_at
    if delay_seconds <= 0:
        return
    elapsed = time.time() - _last_request_at
    if elapsed < delay_seconds:
        time.sleep(delay_seconds - elapsed)


def _scraper_api_url(target_url: str, api_key: str, *, render: bool = False) -> str:
    params = f"api_key={quote(api_key, safe='')}&url={quote(target_url, safe='')}"
    if render:
        params += "&render=true"
    return f"http://api.scraperapi.com?{params}"


class NewsFetcher:
    """Fetch public news URLs with optional proxy rotation and ScraperAPI."""

    def __init__(self) -> None:
        settings = get_settings()
        self._settings = settings
        self._proxy_pool = ProxyPool(parse_proxy_urls(settings.proxy_urls))
        self._user_agent = settings.scraper_user_agent.strip() or _brand_user_agent()
        self._delay = max(settings.scraper_request_delay_seconds, 0.0)
        self._respect_robots = settings.scraper_respect_robots
        self._use_curl_cffi = settings.scraper_use_curl_cffi

    @property
    def proxy_enabled(self) -> bool:
        return self._proxy_pool.enabled

    @property
    def scraper_api_enabled(self) -> bool:
        return bool(self._settings.scraper_api_key.strip())

    def fetch(
        self,
        url: str,
        *,
        timeout: float = 30.0,
        use_scraper_api: bool | None = None,
        check_robots: bool | None = None,
    ) -> httpx.Response:
        if check_robots if check_robots is not None else self._respect_robots:
            if not allowed_to_fetch(url, self._user_agent):
                raise PermissionError(f"robots.txt disallows fetching: {url}")

        use_api = use_scraper_api if use_scraper_api is not None else self.scraper_api_enabled
        if use_api and self.scraper_api_enabled:
            api_url = _scraper_api_url(url, self._settings.scraper_api_key.strip())
            return self._fetch_with_retries(api_url, timeout=timeout, original_url=url)

        return self._fetch_with_retries(url, timeout=timeout)

    def _fetch_with_retries(
        self,
        url: str,
        *,
        timeout: float,
        original_url: str | None = None,
    ) -> httpx.Response:
        attempts = max(self._settings.scraper_max_retries, 1)
        errors: list[str] = []

        for attempt in range(attempts):
            proxy = self._proxy_pool.next_proxy()
            try:
                response = self._do_fetch(url, timeout=timeout, proxy=proxy)
                if response.status_code in {403, 429, 502, 503} and proxy:
                    self._proxy_pool.mark_bad(proxy)
                    errors.append(f"HTTP {response.status_code} via proxy")
                    continue
                if proxy:
                    self._proxy_pool.mark_good(proxy)
                response.raise_for_status()
                return response
            except Exception as exc:
                if proxy:
                    self._proxy_pool.mark_bad(proxy)
                errors.append(str(exc))
                if attempt + 1 >= attempts:
                    break

        target = original_url or url
        raise httpx.HTTPError(
            f"Failed to fetch {target} after {attempts} attempt(s): {'; '.join(errors[-3:])}"
        )

    @retry(
        retry=retry_if_exception_type((httpx.TransportError, httpx.TimeoutException)),
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        reraise=True,
    )
    def _do_fetch(
        self,
        url: str,
        *,
        timeout: float,
        proxy: str | None,
    ) -> httpx.Response:
        global _last_request_at
        _rate_limit(self._delay)
        headers = {
            "User-Agent": self._user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        proxies = self._proxy_pool.as_httpx_proxy(proxy)

        if self._use_curl_cffi:
            return self._fetch_curl_cffi(url, headers=headers, timeout=timeout, proxy=proxy)

        with httpx.Client(timeout=timeout, headers=headers, follow_redirects=True, proxy=proxy) as client:
            response = client.get(url)
            _last_request_at = time.time()
            return response

    def _fetch_curl_cffi(
        self,
        url: str,
        *,
        headers: dict[str, str],
        timeout: float,
        proxy: str | None,
    ) -> httpx.Response:
        from curl_cffi import requests as curl_requests

        global _last_request_at
        kwargs: dict[str, Any] = {
            "headers": headers,
            "timeout": timeout,
            "allow_redirects": True,
            "impersonate": "chrome",
        }
        if proxy:
            kwargs["proxies"] = {"http": proxy, "https": proxy}

        resp = curl_requests.get(url, **kwargs)
        _last_request_at = time.time()
        return httpx.Response(
            status_code=resp.status_code,
            headers=resp.headers,
            content=resp.content,
            request=httpx.Request("GET", url),
        )
