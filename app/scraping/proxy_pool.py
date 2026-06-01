"""Round-robin proxy pool with temporary cooldown on failures."""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator
from urllib.parse import urlparse


class ProxyPool:
    """Rotate through configured HTTP(S) proxies."""

    def __init__(
        self,
        proxy_urls: list[str],
        *,
        cooldown_seconds: float = 120.0,
    ) -> None:
        cleaned = [u.strip() for u in proxy_urls if u and u.strip()]
        self._proxies = cleaned
        self._cooldown_seconds = cooldown_seconds
        self._index = 0
        self._lock = threading.Lock()
        self._blocked_until: dict[str, float] = {}

    @property
    def enabled(self) -> bool:
        return bool(self._proxies)

    def _available(self) -> list[str]:
        now = time.time()
        return [p for p in self._proxies if self._blocked_until.get(p, 0) <= now]

    def next_proxy(self) -> str | None:
        if not self._proxies:
            return None
        with self._lock:
            available = self._available()
            if not available:
                # All cooling down — use least recently blocked
                available = self._proxies
            proxy = available[self._index % len(available)]
            self._index += 1
            return proxy

    def mark_bad(self, proxy: str | None) -> None:
        if not proxy:
            return
        with self._lock:
            self._blocked_until[proxy] = time.time() + self._cooldown_seconds

    def mark_good(self, proxy: str | None) -> None:
        if not proxy:
            return
        with self._lock:
            self._blocked_until.pop(proxy, None)

    def as_httpx_proxy(self, proxy_url: str | None) -> dict[str, str] | None:
        if not proxy_url:
            return None
        return {"http://": proxy_url, "https://": proxy_url}

    def iter_all(self) -> Iterator[str]:
        yield from self._proxies


def parse_proxy_urls(raw: str) -> list[str]:
    """Parse comma- or newline-separated proxy URLs."""
    if not raw.strip():
        return []
    parts: list[str] = []
    for chunk in raw.replace("\n", ",").split(","):
        value = chunk.strip()
        if not value:
            continue
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https", "socks5", "socks5h"}:
            continue
        parts.append(value)
    return parts
