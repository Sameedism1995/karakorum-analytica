"""Download X media and store in Supabase Storage."""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlparse

import httpx
from loguru import logger

from app.config import get_settings

DEFAULT_BUCKET = "karakorum-osint-media"
_VIDEO_EXT = {".mp4", ".m3u8", ".mov", ".webm"}
_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp"}


def default_bucket_name() -> str:
    settings = get_settings()
    return (settings.supabase_bucket_name or "").strip() or DEFAULT_BUCKET


def extract_media_urls_from_tweet(tweet: dict[str, Any]) -> list[str]:
    """Collect image/video URLs from a Scweet tweet dict."""
    urls: list[str] = []
    seen: set[str] = set()

    def add(url: Any) -> None:
        if not url:
            return
        text = str(url).strip()
        if not text.startswith("http") or text in seen:
            return
        seen.add(text)
        urls.append(text)

    media = tweet.get("media")
    if isinstance(media, dict):
        for key in ("image_links", "video_links", "urls"):
            value = media.get(key)
            if isinstance(value, list):
                for entry in value:
                    add(entry)
            elif value:
                add(value)

    for key in ("image_links", "video_links", "photos", "videos"):
        value = tweet.get(key)
        if isinstance(value, list):
            for entry in value:
                add(entry)
        elif value:
            add(value)

    entities = tweet.get("entities") or {}
    if isinstance(entities, dict):
        for media_item in entities.get("media") or []:
            if isinstance(media_item, dict):
                add(media_item.get("media_url_https") or media_item.get("media_url"))

    return urls


def _guess_extension(url: str, content_type: str | None) -> str:
    path = urlparse(url).path.lower()
    for ext in _VIDEO_EXT | _IMAGE_EXT:
        if path.endswith(ext):
            return ext.lstrip(".")
    if content_type:
        if "video" in content_type:
            return "mp4"
        if "png" in content_type:
            return "png"
        if "gif" in content_type:
            return "gif"
        if "webp" in content_type:
            return "webp"
    return "jpg"


def _storage_path(handle: str, tweet_id: str, index: int, ext: str) -> str:
    safe_handle = re.sub(r"[^a-zA-Z0-9_]", "", handle) or "unknown"
    return f"x/{safe_handle}/{tweet_id}/{index}.{ext}"


def ensure_media_bucket() -> bool:
    """Create the public media bucket if missing."""
    from app.integrations.supabase_client import get_supabase_client

    client = get_supabase_client()
    if client is None:
        return False

    bucket = default_bucket_name()
    try:
        buckets = client.storage.list_buckets()
        names = {b.name for b in buckets} if buckets else set()
        if bucket in names:
            return True
        client.storage.create_bucket(bucket, options={"public": True})
        logger.info(f"Created Supabase storage bucket: {bucket}")
        return True
    except Exception as exc:
        logger.warning(f"Could not ensure bucket {bucket}: {exc}")
        return False


def upload_tweet_media(
    tweet: dict[str, Any],
    *,
    handle: str | None = None,
) -> list[dict[str, str]]:
    """
    Download tweet media and upload to Supabase Storage.

    Returns list of {source_url, storage_path, public_url}.
    """
    from app.integrations.supabase_client import get_supabase_client

    client = get_supabase_client()
    if client is None:
        return []

    tweet_id = str(tweet.get("tweet_id") or tweet.get("id") or "unknown")
    user = tweet.get("user") if isinstance(tweet.get("user"), dict) else {}
    screen = handle or user.get("screen_name") or user.get("username") or "unknown"

    media_urls = extract_media_urls_from_tweet(tweet)
    if not media_urls:
        return []

    if not ensure_media_bucket():
        return []

    bucket = default_bucket_name()
    stored: list[dict[str, str]] = []

    with httpx.Client(timeout=45.0, follow_redirects=True) as http:
        for index, source_url in enumerate(media_urls):
            try:
                response = http.get(source_url)
                response.raise_for_status()
                content_type = response.headers.get("content-type", "")
                ext = _guess_extension(source_url, content_type)
                path = _storage_path(str(screen).lstrip("@"), tweet_id, index, ext)
                client.storage.from_(bucket).upload(
                    path,
                    response.content,
                    file_options={
                        "content-type": content_type or "application/octet-stream",
                        "upsert": "true",
                    },
                )
                public = client.storage.from_(bucket).get_public_url(path)
                stored.append(
                    {
                        "source_url": source_url,
                        "storage_path": path,
                        "public_url": public,
                    }
                )
            except Exception as exc:
                logger.debug(f"Media upload skipped for {source_url[:60]}: {exc}")

    return stored


def attach_stored_media_to_item(item: dict[str, Any], stored: list[dict[str, str]]) -> None:
    """Merge storage metadata into item raw_json for API responses."""
    if not stored:
        return
    raw = item.get("raw_json")
    if isinstance(raw, dict):
        payload = raw
    elif isinstance(raw, str) and raw.strip():
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {}
    else:
        payload = {}

    if isinstance(payload, dict):
        payload["stored_media"] = stored
        item["raw_json"] = payload
        item["media_urls"] = json.dumps([entry["public_url"] for entry in stored])
