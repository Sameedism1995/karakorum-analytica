"""HTTP client for the Karakorum Analytica FastAPI backend."""

from __future__ import annotations

import os
from typing import Any

import requests

DEFAULT_BASE_URL = "http://127.0.0.1:8000"
REQUEST_TIMEOUT = 30


def resolve_base_url(override: str | None = None) -> str:
    """Resolve API base URL from override, env, or local default."""
    if override and override.strip():
        return override.strip().rstrip("/")
    env_url = os.environ.get("API_BASE_URL", "").strip()
    if env_url:
        return env_url.rstrip("/")
    return DEFAULT_BASE_URL


class ApiError(Exception):
    """Raised when the backend returns a non-success response."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def _base_url(base_url: str) -> str:
    return base_url.rstrip("/")


def check_backend(base_url: str = DEFAULT_BASE_URL) -> dict[str, Any]:
    """Return health payload from GET / or an error dict."""
    try:
        response = requests.get(
            f"{_base_url(base_url)}/",
            timeout=REQUEST_TIMEOUT,
        )
        if response.status_code == 404:
            return {
                "ok": False,
                "data": None,
                "error": "not_found",
                "detail": (
                    f"No API service at {base_url}. Deploy on Render or use embedded mode."
                ),
            }
        response.raise_for_status()
        data = response.json()
        return {"ok": True, "data": data, "error": None}
    except requests.RequestException as exc:
        return {"ok": False, "data": None, "error": str(exc)}


def run_collection(base_url: str = DEFAULT_BASE_URL) -> dict[str, Any]:
    """Trigger POST /collect/run."""
    try:
        response = requests.post(
            f"{_base_url(base_url)}/collect/run",
            timeout=120,
        )
        response.raise_for_status()
        return {"ok": True, "data": response.json(), "error": None}
    except requests.RequestException as exc:
        message = str(exc)
        if isinstance(exc, requests.HTTPError) and exc.response is not None:
            try:
                detail = exc.response.json()
                message = detail.get("detail", message)
            except ValueError:
                message = exc.response.text or message
        return {"ok": False, "data": None, "error": message}


def get_raw_news(
    base_url: str = DEFAULT_BASE_URL,
    limit: int = 500,
) -> list[dict[str, Any]]:
    """Fetch GET /raw-news items."""
    try:
        response = requests.get(
            f"{_base_url(base_url)}/raw-news",
            params={"limit": limit},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return response.json().get("items", [])
    except requests.RequestException:
        return []


def get_incidents(
    base_url: str = DEFAULT_BASE_URL,
    limit: int = 500,
) -> list[dict[str, Any]]:
    """Fetch GET /incidents items."""
    try:
        response = requests.get(
            f"{_base_url(base_url)}/incidents",
            params={"limit": limit},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return response.json().get("items", [])
    except requests.RequestException:
        return []


def get_drafts(
    base_url: str = DEFAULT_BASE_URL,
    limit: int = 500,
) -> list[dict[str, Any]]:
    """Fetch GET /drafts items."""
    try:
        response = requests.get(
            f"{_base_url(base_url)}/drafts",
            params={"limit": limit},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return response.json().get("items", [])
    except requests.RequestException:
        return []


def approve_draft(
    draft_id: int,
    base_url: str = DEFAULT_BASE_URL,
) -> dict[str, Any]:
    """POST /drafts/{id}/approve."""
    try:
        response = requests.post(
            f"{_base_url(base_url)}/drafts/{draft_id}/approve",
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return {"ok": True, "data": response.json(), "error": None}
    except requests.RequestException as exc:
        message = str(exc)
        if isinstance(exc, requests.HTTPError) and exc.response is not None:
            try:
                detail = exc.response.json()
                message = detail.get("detail", message)
            except ValueError:
                message = exc.response.text or message
        return {"ok": False, "data": None, "error": message}


def reject_draft(
    draft_id: int,
    base_url: str = DEFAULT_BASE_URL,
) -> dict[str, Any]:
    """POST /drafts/{id}/reject."""
    try:
        response = requests.post(
            f"{_base_url(base_url)}/drafts/{draft_id}/reject",
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return {"ok": True, "data": response.json(), "error": None}
    except requests.RequestException as exc:
        message = str(exc)
        if isinstance(exc, requests.HTTPError) and exc.response is not None:
            try:
                detail = exc.response.json()
                message = detail.get("detail", message)
            except ValueError:
                message = exc.response.text or message
        return {"ok": False, "data": None, "error": message}


def post_draft(
    draft_id: int,
    base_url: str = DEFAULT_BASE_URL,
) -> dict[str, Any]:
    """POST /drafts/{id}/post — only when X posting is explicitly enabled."""
    try:
        response = requests.post(
            f"{_base_url(base_url)}/drafts/{draft_id}/post",
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return {"ok": True, "data": response.json(), "error": None}
    except requests.RequestException as exc:
        message = str(exc)
        if isinstance(exc, requests.HTTPError) and exc.response is not None:
            try:
                detail = exc.response.json()
                message = detail.get("detail", message)
            except ValueError:
                message = exc.response.text or message
        return {"ok": False, "data": None, "error": message}
