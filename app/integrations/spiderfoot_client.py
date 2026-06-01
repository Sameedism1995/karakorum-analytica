"""HTTP client for SpiderFoot CherryPy web API (sf.py -l)."""

from __future__ import annotations

from typing import Any

import requests

from app.config import get_settings

JSON_HEADERS = {"Accept": "application/json"}
REQUEST_TIMEOUT = 120


def _base_url() -> str:
    return get_settings().spiderfoot_base_url.rstrip("/")


def _request(
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    data: dict[str, Any] | None = None,
    timeout: int | None = None,
) -> dict[str, Any]:
    url = f"{_base_url()}{path}"
    try:
        response = requests.request(
            method,
            url,
            params=params,
            data=data,
            headers=JSON_HEADERS,
            timeout=timeout or REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        if not response.content:
            return {"ok": True, "data": None}
        try:
            payload = response.json()
        except ValueError:
            payload = response.text
        return {"ok": True, "data": payload}
    except requests.RequestException as exc:
        message = str(exc)
        if isinstance(exc, requests.HTTPError) and exc.response is not None:
            try:
                message = exc.response.text or message
            except Exception:
                pass
        return {"ok": False, "error": message}


def ping() -> dict[str, Any]:
    result = _request("GET", "/ping", timeout=15)
    if not result.get("ok"):
        return {"ok": False, "reachable": False, "error": result.get("error")}
    return {"ok": True, "reachable": True, "data": result.get("data")}


def list_scans() -> dict[str, Any]:
    result = _request("GET", "/scanlist")
    if not result.get("ok"):
        return result
    rows = result.get("data") or []
    scans = []
    for row in rows:
        if not isinstance(row, list) or len(row) < 8:
            continue
        scans.append(
            {
                "id": row[0],
                "name": row[1],
                "target": row[2],
                "created": row[3],
                "started": row[4],
                "finished": row[5],
                "status": row[6],
                "elements": row[7],
                "risk": row[8] if len(row) > 8 else {},
            }
        )
    return {"ok": True, "count": len(scans), "scans": scans}


def get_scan_status(scan_id: str) -> dict[str, Any]:
    result = _request("GET", "/scanstatus", params={"id": scan_id})
    if not result.get("ok"):
        return result
    row = result.get("data") or []
    if not row:
        return {"ok": False, "error": "Scan not found"}
    return {
        "ok": True,
        "scan": {
            "id": row[0],
            "name": row[1],
            "created": row[2],
            "started": row[3],
            "finished": row[4],
            "status": row[5],
            "risk": row[6] if len(row) > 6 else {},
        },
    }


def get_scan_summary(scan_id: str, *, by: str = "type") -> dict[str, Any]:
    result = _request("GET", "/scansummary", params={"id": scan_id, "by": by})
    if not result.get("ok"):
        return result
    rows = result.get("data") or []
    summary = []
    for row in rows:
        if isinstance(row, list) and len(row) >= 2:
            summary.append({"key": row[0], "count": row[1]})
    return {"ok": True, "summary": summary}


def get_scan_results(
    scan_id: str,
    *,
    event_type: str = "",
    unique: bool = False,
    limit: int = 500,
) -> dict[str, Any]:
    path = "/scaneventresultsunique" if unique else "/scaneventresults"
    params: dict[str, Any] = {"id": scan_id, "filterfp": "0"}
    if event_type:
        params["eventType"] = event_type
    result = _request("GET", path, params=params, timeout=180)
    if not result.get("ok"):
        return result
    rows = result.get("data") or []
    items = []
    for row in rows[:limit]:
        if not isinstance(row, list):
            continue
        items.append(
            {
                "generated": row[0] if len(row) > 0 else None,
                "data": row[1] if len(row) > 1 else None,
                "source_data": row[2] if len(row) > 2 else None,
                "module": row[3] if len(row) > 3 else None,
                "type": row[4] if len(row) > 4 else None,
                "confidence": row[5] if len(row) > 5 else None,
                "visibility": row[6] if len(row) > 6 else None,
                "risk": row[7] if len(row) > 7 else None,
                "hash": row[8] if len(row) > 8 else None,
                "source_event_hash": row[9] if len(row) > 9 else None,
                "parent": row[10] if len(row) > 10 else None,
            }
        )
    return {"ok": True, "count": len(items), "items": items}


def start_scan(
    *,
    scan_name: str,
    target: str,
    usecase: str = "passive",
    module_list: str = "",
    type_list: str = "",
) -> dict[str, Any]:
    result = _request(
        "POST",
        "/startscan",
        data={
            "scanname": scan_name,
            "scantarget": target,
            "modulelist": module_list,
            "typelist": type_list,
            "usecase": usecase,
        },
        timeout=60,
    )
    if not result.get("ok"):
        return result
    payload = result.get("data")
    if isinstance(payload, list) and len(payload) >= 2:
        if payload[0] == "SUCCESS":
            return {"ok": True, "scan_id": payload[1], "message": payload[0]}
        return {"ok": False, "error": payload[1] if len(payload) > 1 else str(payload)}
    return {"ok": False, "error": "Unexpected response from SpiderFoot"}


def stop_scan(scan_id: str) -> dict[str, Any]:
    return _request("GET", "/stopscan", params={"id": scan_id})


def delete_scan(scan_id: str) -> dict[str, Any]:
    return _request("GET", "/scandelete", params={"id": scan_id})


def list_modules() -> dict[str, Any]:
    result = _request("GET", "/modules", timeout=60)
    if not result.get("ok"):
        return result
    return {"ok": True, "modules": result.get("data") or []}
