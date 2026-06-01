"""SpiderFoot OSINT scan orchestration for Karakorum Analytica."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.config import get_settings
from app.integrations import spiderfoot_client


def get_spiderfoot_health() -> dict[str, Any]:
    settings = get_settings()
    sf_dir = Path(settings.spiderfoot_dir)
    installed = (sf_dir / "sf.py").is_file()
    payload: dict[str, Any] = {
        "enabled": settings.spiderfoot_enabled,
        "installed": installed,
        "dir": str(sf_dir),
        "base_url": settings.spiderfoot_base_url,
        "default_usecase": settings.spiderfoot_default_usecase,
        "autostart": settings.spiderfoot_autostart,
        "reachable": False,
        "error": None,
    }
    if not settings.spiderfoot_enabled:
        payload["error"] = "SpiderFoot disabled (SPIDERFOOT_ENABLED=false)"
        return payload
    if not installed:
        payload["error"] = f"SpiderFoot not found at {sf_dir}"
        return payload
    ping = spiderfoot_client.ping()
    payload["reachable"] = bool(ping.get("reachable"))
    if ping.get("data"):
        payload["version"] = ping.get("data")
    if not payload["reachable"]:
        payload["error"] = ping.get("error") or "SpiderFoot web server not reachable"
    return payload


def list_scans() -> dict[str, Any]:
    if not get_settings().spiderfoot_enabled:
        return {"ok": False, "error": "SpiderFoot is disabled"}
    return spiderfoot_client.list_scans()


def get_scan(scan_id: str) -> dict[str, Any]:
    status = spiderfoot_client.get_scan_status(scan_id)
    if not status.get("ok"):
        return status
    summary = spiderfoot_client.get_scan_summary(scan_id, by="type")
    return {
        "ok": True,
        "scan": status.get("scan"),
        "summary": summary.get("summary") or [],
    }


def get_scan_results(
    scan_id: str,
    *,
    event_type: str = "",
    unique: bool = False,
    limit: int = 500,
) -> dict[str, Any]:
    return spiderfoot_client.get_scan_results(
        scan_id,
        event_type=event_type,
        unique=unique,
        limit=limit,
    )


def start_scan(
    *,
    scan_name: str,
    target: str,
    usecase: str | None = None,
    module_list: str = "",
    type_list: str = "",
) -> dict[str, Any]:
    settings = get_settings()
    if not settings.spiderfoot_enabled:
        return {"ok": False, "error": "SpiderFoot is disabled"}
    health = get_spiderfoot_health()
    if not health.get("reachable"):
        return {"ok": False, "error": health.get("error") or "SpiderFoot offline"}
    return spiderfoot_client.start_scan(
        scan_name=scan_name.strip() or f"Scan {target}",
        target=target.strip(),
        usecase=(usecase or settings.spiderfoot_default_usecase).strip(),
        module_list=module_list.strip(),
        type_list=type_list.strip(),
    )


def stop_scan(scan_id: str) -> dict[str, Any]:
    return spiderfoot_client.stop_scan(scan_id)


def delete_scan(scan_id: str) -> dict[str, Any]:
    return spiderfoot_client.delete_scan(scan_id)


def list_modules() -> dict[str, Any]:
    return spiderfoot_client.list_modules()
