"""Direct Buffer API integration for Karakorum Analytica."""

from __future__ import annotations

from typing import Any

from loguru import logger

from app.config import get_settings
from app.integrations.buffer_client import (
    BufferApiError,
    channel_matches_handle,
    fetch_channels,
    find_channel_by_handle,
    is_buffer_configured,
    post_now_text_post,
    queue_text_post,
)


class BufferService:
    """List channels and queue text posts to Buffer for @kkanalytica."""

    def is_configured(self) -> bool:
        return is_buffer_configured()

    def list_channels(self) -> dict[str, Any]:
        if not self.is_configured():
            return {"ok": False, "error": "BUFFER_API_KEY is not configured", "channels": []}
        try:
            channels = fetch_channels()
            return {"ok": True, "channels": channels, "count": len(channels)}
        except BufferApiError as exc:
            logger.error(f"Buffer list channels failed: {exc}")
            return {"ok": False, "error": str(exc), "channels": []}

    def resolve_channel_id(self) -> tuple[str | None, dict[str, Any]]:
        settings = get_settings()
        configured_id = settings.buffer_channel_id.strip()
        if configured_id:
            logger.info(f"Using configured Buffer channel ID {configured_id[:8]}…")
            return configured_id, {"source": "env", "channel_id": configured_id}

        handle = settings.buffer_channel_handle or "@kkanalytica"
        try:
            channels = fetch_channels()
        except BufferApiError as exc:
            return None, {"error": str(exc)}

        match = find_channel_by_handle(handle, channels)
        if match and match.get("id"):
            channel_id = str(match["id"])
            logger.info(
                f"Auto-detected Buffer channel id={channel_id} handle={handle} "
                f"service={match.get('service')}"
            )
            return channel_id, {"source": "auto", "matched_channel": match, "channel_id": channel_id}

        return None, {
            "error": f"No Buffer channel matched handle {handle}",
            "handle": handle,
            "channels": channels,
        }

    def discover_channels_payload(self) -> dict[str, Any]:
        """Return channels plus matched @kkanalytica channel for GET /api/buffer/channels."""
        settings = get_settings()
        handle = settings.buffer_channel_handle or "@kkanalytica"
        list_result = self.list_channels()
        if not list_result.get("ok"):
            return list_result

        channels = list_result.get("channels") or []
        configured_id = settings.buffer_channel_id.strip()
        matched = None
        if configured_id:
            matched = next((ch for ch in channels if str(ch.get("id")) == configured_id), None)
            if matched:
                matched = {**matched, "match_reason": "BUFFER_CHANNEL_ID env"}
        if not matched:
            found = find_channel_by_handle(handle, channels)
            if found:
                matched = {**found, "match_reason": f"handle {handle}"}

        channel_id, resolution = self.resolve_channel_id()
        return {
            "ok": True,
            "configured": self.is_configured(),
            "handle": handle,
            "matched_channel": matched,
            "channel_id": channel_id,
            "resolution": resolution,
            "channels": [
                {
                    "id": ch.get("id"),
                    "name": ch.get("name"),
                    "displayName": ch.get("displayName"),
                    "service": ch.get("service"),
                    "descriptor": ch.get("descriptor"),
                    "matches_handle": channel_matches_handle(ch, handle),
                }
                for ch in channels
            ],
        }

    def _publish(
        self,
        text: str,
        *,
        channel_id: str | None,
        publish_fn,
        log_label: str,
    ) -> dict[str, Any]:
        if not self.is_configured():
            return {"ok": False, "error": "BUFFER_API_KEY is not configured"}

        resolved_id = channel_id
        resolution: dict[str, Any] = {}
        if not resolved_id:
            resolved_id, resolution = self.resolve_channel_id()
        if not resolved_id:
            return {"ok": False, "error": resolution.get("error") or "Buffer channel not found", "resolution": resolution}

        try:
            result = publish_fn(text=text, channel_id=resolved_id)
            return {
                "ok": True,
                "channel_id": resolved_id,
                "buffer_response": result.get("response"),
                "post": result.get("post"),
                "mode": result.get("mode"),
                "resolution": resolution,
            }
        except BufferApiError as exc:
            logger.error(f"Buffer {log_label} failed channel_id={resolved_id}: {exc}")
            return {
                "ok": False,
                "error": str(exc),
                "channel_id": resolved_id,
                "buffer_response": exc.response,
                "http_status": exc.http_status,
            }

    def queue_post_to_buffer(self, text: str, *, channel_id: str | None = None) -> dict[str, Any]:
        """Add text post to Buffer queue (addToQueue) — optional admin path."""
        return self._publish(text, channel_id=channel_id, publish_fn=queue_text_post, log_label="queue")

    def post_now_to_buffer(self, text: str, *, channel_id: str | None = None) -> dict[str, Any]:
        """Publish text immediately to connected X account (shareNow)."""
        return self._publish(text, channel_id=channel_id, publish_fn=post_now_text_post, log_label="publish-now")

    def queue_text_post(self, text: str, *, channel_id: str | None = None) -> dict[str, Any]:
        """Backward-compatible alias for queue_post_to_buffer."""
        return self.queue_post_to_buffer(text, channel_id=channel_id)


buffer_service = BufferService()


def _safe_channel_summary(channels: list[dict[str, Any]], handle: str) -> list[dict[str, Any]]:
    return [
        {
            "id": ch.get("id"),
            "name": ch.get("name"),
            "displayName": ch.get("displayName"),
            "service": ch.get("service"),
            "descriptor": ch.get("descriptor"),
            "matches_handle": channel_matches_handle(ch, handle),
        }
        for ch in channels
    ]


def get_buffer_health() -> dict[str, Any]:
    """Standard health payload for GET /api/health/buffer — never exposes API key."""
    settings = get_settings()
    handle = settings.buffer_channel_handle or "@kkanalytica"
    configured = buffer_service.is_configured()
    if not configured:
        return {
            "api_key_configured": False,
            "channel_handle": handle,
            "channel_found": False,
            "channel_id": None,
            "available_channels": [],
            "error": "BUFFER_API_KEY is not configured",
        }

    list_result = buffer_service.list_channels()
    channels = list_result.get("channels") or []
    safe_channels = _safe_channel_summary(channels, handle)

    channel_id, resolution = buffer_service.resolve_channel_id()
    channel_found = bool(channel_id)
    error = None
    if not list_result.get("ok"):
        error = list_result.get("error") or "Failed to list Buffer channels"
    elif not channel_found:
        error = resolution.get("error") or "Buffer channel not found"

    if channel_found:
        logger.info(f"Buffer health ok channel_id={channel_id[:8]}… handle={handle}")
    else:
        logger.warning(f"Buffer health channel not found: {error}")

    return {
        "api_key_configured": True,
        "channel_handle": handle,
        "channel_found": channel_found,
        "channel_id": channel_id,
        "available_channels": safe_channels,
        "error": error,
    }
