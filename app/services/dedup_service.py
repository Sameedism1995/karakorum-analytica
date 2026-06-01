"""Deduplication keys for ingested items (especially X / Scweet tweets)."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any
from urllib.parse import urlparse, urlunparse

_TWEET_URL_RE = re.compile(
    r"(?:x\.com|twitter\.com)/([^/]+)/status/(\d+)",
    re.I,
)


def _normalize_url(url: str | None) -> str | None:
    if not url or not str(url).strip():
        return None
    text = str(url).strip()
    try:
        parsed = urlparse(text)
        path = parsed.path.rstrip("/")
        return urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), path, "", "", ""))
    except Exception:
        return text.lower().rstrip("/")


def extract_tweet_id(item: dict[str, Any]) -> str | None:
    """Resolve X tweet id from normalized item or raw_json."""
    raw = item.get("raw_json")
    if isinstance(raw, dict):
        tid = raw.get("tweet_id") or raw.get("id")
        if tid:
            return str(tid).strip()
    elif isinstance(raw, str) and raw.strip():
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                tid = data.get("tweet_id") or data.get("id")
                if tid:
                    return str(tid).strip()
        except json.JSONDecodeError:
            pass

    url = item.get("url")
    if url:
        match = _TWEET_URL_RE.search(str(url))
        if match:
            return match.group(2)
    return None


def content_hash_for_item(item: dict[str, Any]) -> str:
    """
    Stable hash for dedup: prefer tweet id, then normalized URL, then title.
    """
    source_name = item.get("source_name") or "unknown"
    tweet_id = extract_tweet_id(item)
    if tweet_id:
        raw = f"{source_name}|tweet_id:{tweet_id}"
        return hashlib.sha256(raw.encode()).hexdigest()

    url = _normalize_url(item.get("url"))
    if url:
        raw = f"{source_name}|url:{url}"
        return hashlib.sha256(raw.encode()).hexdigest()

    title = (item.get("title") or "").lower().strip()
    raw = f"{source_name}|{url or ''}|{title}"
    return hashlib.sha256(raw.encode()).hexdigest()
