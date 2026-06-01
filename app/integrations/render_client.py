"""Render API helpers for syncing environment variables."""

from __future__ import annotations

import os
from typing import Any

import httpx

RENDER_API_BASE = "https://api.render.com/v1"


class RenderApiError(RuntimeError):
    """Raised when a Render API request fails."""


def _api_key() -> str:
    key = os.environ.get("RENDER_API_KEY", "").strip()
    if not key:
        raise RenderApiError(
            "RENDER_API_KEY is not set. Create one at "
            "https://dashboard.render.com/u/settings#api-keys"
        )
    return key


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {_api_key()}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def _unwrap_service(item: Any) -> dict[str, Any] | None:
    if isinstance(item, dict):
        if "service" in item and isinstance(item["service"], dict):
            return item["service"]
        if item.get("id") and item.get("name"):
            return item
    return None


def list_services(*, name: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    """Return Render services (optionally filtered by exact name)."""
    params: dict[str, Any] = {"limit": limit}
    if name:
        params["name"] = name

    with httpx.Client(timeout=30.0) as client:
        response = client.get(f"{RENDER_API_BASE}/services", headers=_headers(), params=params)
        if response.status_code >= 400:
            raise RenderApiError(f"List services failed ({response.status_code}): {response.text}")
        payload = response.json()

    services: list[dict[str, Any]] = []
    items = payload if isinstance(payload, list) else payload.get("items") or payload.get("services") or []
    for item in items:
        service = _unwrap_service(item)
        if service:
            services.append(service)
    return services


def resolve_service_ids(service_names: list[str]) -> dict[str, str]:
    """Map service name → service ID."""
    wanted = {name.strip() for name in service_names if name.strip()}
    if not wanted:
        return {}

    found: dict[str, str] = {}
    for name in sorted(wanted):
        matches = list_services(name=name)
        for service in matches:
            svc_name = str(service.get("name") or "")
            svc_id = str(service.get("id") or "")
            if svc_name in wanted and svc_id:
                found[svc_name] = svc_id

    if len(found) < len(wanted):
        missing = sorted(wanted - set(found))
        raise RenderApiError(f"Could not find Render service(s): {', '.join(missing)}")

    return found


def resolve_service_targets(
    *,
    service_names: list[str] | None = None,
    service_ids: list[str] | None = None,
) -> dict[str, str]:
    """
    Map display label → Render service ID.

    Uses explicit service IDs when provided; otherwise resolves by service name.
    """
    ids = [sid.strip() for sid in (service_ids or []) if sid and sid.strip()]
    if ids:
        return {sid: sid for sid in ids}

    names = [name.strip() for name in (service_names or []) if name and name.strip()]
    if not names:
        return {}
    return resolve_service_ids(names)


def update_env_var(service_id: str, key: str, value: str) -> None:
    """Create or update a single environment variable on a Render service."""
    with httpx.Client(timeout=30.0) as client:
        response = client.put(
            f"{RENDER_API_BASE}/services/{service_id}/env-vars/{key}",
            headers=_headers(),
            json={"value": value},
        )
        if response.status_code >= 400:
            raise RenderApiError(
                f"Update {key} on {service_id} failed ({response.status_code}): {response.text}"
            )


def trigger_deploy(service_id: str, *, clear_cache: bool = False) -> dict[str, Any]:
    """Start a new deploy so runtime picks up updated env vars."""
    body: dict[str, Any] = {}
    if clear_cache:
        body["clearCache"] = "clear"

    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            f"{RENDER_API_BASE}/services/{service_id}/deploys",
            headers=_headers(),
            json=body or None,
        )
        if response.status_code >= 400:
            raise RenderApiError(f"Deploy {service_id} failed ({response.status_code}): {response.text}")
        return response.json()
