"""Buffer GraphQL API client — API key stays server-side only."""

from __future__ import annotations

from typing import Any

import httpx
from loguru import logger

from app.config import get_settings

BUFFER_GRAPHQL_URL = "https://api.buffer.com"

ACCOUNT_QUERY = """
query Account {
  account {
    id
    email
    organizations {
      id
      name
    }
  }
}
"""

CHANNELS_QUERY = """
query GetChannels($input: ChannelsInput!) {
  channels(input: $input) {
    id
    name
    displayName
    service
    descriptor
    avatar
    isQueuePaused
  }
}
"""

CREATE_POST_MUTATION = """
mutation CreatePost($input: CreatePostInput!) {
  createPost(input: $input) {
    ... on PostActionSuccess {
      post {
        id
        text
        status
      }
    }
    ... on MutationError {
      message
    }
  }
}
"""


class BufferApiError(Exception):
    """Raised when Buffer API returns an error."""

    def __init__(self, message: str, *, response: dict | None = None, http_status: int | None = None) -> None:
        super().__init__(message)
        self.response = response or {}
        self.http_status = http_status


def _api_key() -> str:
    return get_settings().buffer_api_key.strip()


def is_buffer_configured() -> bool:
    return bool(_api_key())


def graphql_request(query: str, *, variables: dict | None = None, timeout: float = 30.0) -> dict[str, Any]:
    key = _api_key()
    if not key:
        raise BufferApiError("BUFFER_API_KEY is not configured")

    payload: dict[str, Any] = {"query": query}
    if variables:
        payload["variables"] = variables

    try:
        response = httpx.post(
            BUFFER_GRAPHQL_URL,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=timeout,
        )
    except httpx.RequestError as exc:
        raise BufferApiError(f"Buffer API request failed: {exc}") from exc

    try:
        body = response.json()
    except Exception as exc:
        raise BufferApiError(
            f"Buffer API returned non-JSON response (HTTP {response.status_code})",
            http_status=response.status_code,
        ) from exc

    if response.status_code >= 400:
        raise BufferApiError(
            f"Buffer API HTTP {response.status_code}",
            response=body,
            http_status=response.status_code,
        )

    if body.get("errors"):
        messages = "; ".join(
            str(err.get("message") or err) for err in body["errors"] if err is not None
        )
        raise BufferApiError(messages or "Buffer GraphQL error", response=body, http_status=response.status_code)

    return body


def fetch_account() -> dict[str, Any]:
    body = graphql_request(ACCOUNT_QUERY)
    return (body.get("data") or {}).get("account") or {}


def fetch_organization_id() -> str:
    account = fetch_account()
    orgs = account.get("organizations") or []
    if not orgs:
        raise BufferApiError("No Buffer organizations found for this API key")
    org_id = str(orgs[0].get("id") or "").strip()
    if not org_id:
        raise BufferApiError("Buffer organization ID missing from account response")
    return org_id


def fetch_channels(*, organization_id: str | None = None) -> list[dict[str, Any]]:
    org_id = organization_id or fetch_organization_id()
    body = graphql_request(CHANNELS_QUERY, variables={"input": {"organizationId": org_id}})
    channels = (body.get("data") or {}).get("channels") or []
    return [ch for ch in channels if isinstance(ch, dict)]


def normalize_handle(value: str) -> str:
    return (value or "").strip().lstrip("@").lower()


def channel_matches_handle(channel: dict[str, Any], handle: str) -> bool:
    target = normalize_handle(handle)
    if not target:
        return False
    candidates = [
        channel.get("name"),
        channel.get("displayName"),
        channel.get("descriptor"),
        channel.get("service"),
    ]
    for raw in candidates:
        if not raw:
            continue
        normalized = normalize_handle(str(raw))
        if normalized == target or target in normalized or normalized.endswith(target):
            return True
    return False


def find_channel_by_handle(handle: str, channels: list[dict[str, Any]] | None = None) -> dict[str, Any] | None:
    rows = channels if channels is not None else fetch_channels()
    twitter_first = [ch for ch in rows if str(ch.get("service", "")).lower() in {"twitter", "x"}]
    search = twitter_first + [ch for ch in rows if ch not in twitter_first]
    for channel in search:
        if channel_matches_handle(channel, handle):
            return channel
    return None


def create_text_post(*, text: str, channel_id: str, mode: str = "addToQueue") -> dict[str, Any]:
    """Create a Buffer post. mode: addToQueue (queue) or shareNow (publish immediately)."""
    body = graphql_request(
        CREATE_POST_MUTATION,
        variables={
            "input": {
                "text": text,
                "channelId": channel_id,
                "schedulingType": "automatic",
                "mode": mode,
            }
        },
    )
    result = (body.get("data") or {}).get("createPost") or {}
    if result.get("message"):
        raise BufferApiError(str(result["message"]), response=body)
    post = result.get("post")
    if not post:
        raise BufferApiError("Buffer createPost returned no post", response=body)
    logger.info(f"Buffer createPost mode={mode} success post_id={post.get('id')}")
    return {"ok": True, "response": body, "post": post, "mode": mode}


def queue_text_post(*, text: str, channel_id: str) -> dict[str, Any]:
    return create_text_post(text=text, channel_id=channel_id, mode="addToQueue")


def post_now_text_post(*, text: str, channel_id: str) -> dict[str, Any]:
    return create_text_post(text=text, channel_id=channel_id, mode="shareNow")
