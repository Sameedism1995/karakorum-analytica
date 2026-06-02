"""HTTP client for the Karakorum Analytica FastAPI backend."""

from __future__ import annotations

import os
from typing import Any

import requests

DEFAULT_BASE_URL = "http://127.0.0.1:8000"
REQUEST_TIMEOUT = 30


def _use_embedded_for_local_llm() -> bool:
    """Route LLM calls to in-process Ollama when the remote API cannot reach localhost."""
    if os.environ.get("RENDER"):
        return False
    try:
        from app.integrations.ollama_client import local_llm_mode_active

        return local_llm_mode_active()
    except Exception:
        return False


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


def _base_url(base_url: str | None = None) -> str:
    return resolve_base_url(base_url)


def _parse_root_health(data: dict[str, Any]) -> dict[str, Any]:
    """Treat API as reachable when Postgres or Supabase REST can serve reads."""
    db = data.get("database") or {}
    supabase = data.get("supabase") or {}
    db_connected = bool(db.get("connected"))
    rest_ok = bool(supabase.get("api_ok"))
    using_supabase = bool(db.get("using_supabase"))

    if data.get("status") == "running":
        if db_connected:
            ok = True
        elif using_supabase and rest_ok:
            ok = True
        elif not using_supabase:
            ok = True
        else:
            ok = False
    else:
        ok = False

    degraded = ok and using_supabase and not db_connected and rest_ok
    error = None
    if not ok:
        error = db.get("error") or supabase.get("api_error") or "Backend unavailable"

    return {"ok": ok, "degraded": degraded, "error": error}


def check_backend(
    base_url: str | None = None,
    *,
    timeout: int | None = None,
) -> dict[str, Any]:
    """Return health payload from GET / (preferred) or GET /health."""
    url = _base_url(base_url)
    request_timeout = timeout if timeout is not None else REQUEST_TIMEOUT
    try:
        root_response = requests.get(f"{url}/", timeout=request_timeout)
        if root_response.status_code == 200:
            data = root_response.json()
            parsed = _parse_root_health(data)
            return {
                "ok": parsed["ok"],
                "degraded": parsed["degraded"],
                "data": data,
                "error": parsed["error"],
            }

        health_response = requests.get(f"{url}/health", timeout=request_timeout)
        if health_response.status_code == 404:
            return {
                "ok": False,
                "degraded": False,
                "data": None,
                "error": "not_found",
                "detail": (
                    f"No API service at {url}. Deploy on Render or use embedded mode."
                ),
            }
        health_response.raise_for_status()
        data = health_response.json()
        ok = data.get("status") == "ok"
        return {"ok": ok, "degraded": False, "data": data, "error": None if ok else "unhealthy"}
    except requests.RequestException as exc:
        return {"ok": False, "degraded": False, "data": None, "error": str(exc)}


def get_database_health(base_url: str | None = None) -> dict[str, Any]:
    """Fetch GET /health/database (Postgres + Supabase REST row counts)."""
    try:
        response = requests.get(
            f"{_base_url(base_url)}/health/database",
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return {"ok": True, "data": response.json(), "error": None}
    except requests.RequestException as exc:
        return {"ok": False, "data": None, "error": str(exc)}


def run_collection(base_url: str | None = None) -> dict[str, Any]:
    """Trigger POST /collect/run (returns when job is queued, not when finished)."""
    try:
        response = requests.post(
            f"{_base_url(base_url)}/collect/run",
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
        status = data.get("status", "")
        if status in {"started", "running"}:
            return {"ok": True, "data": data, "error": None, "async": True}
        return {"ok": True, "data": data, "error": None, "async": False}
    except requests.RequestException as exc:
        message = str(exc)
        if isinstance(exc, requests.HTTPError) and exc.response is not None:
            try:
                detail = exc.response.json()
                message = detail.get("detail", message)
            except ValueError:
                message = exc.response.text or message
        return {"ok": False, "data": None, "error": message}


def get_collection_status(base_url: str | None = None) -> dict[str, Any]:
    """Fetch GET /collect/status."""
    try:
        response = requests.get(
            f"{_base_url(base_url)}/collect/status",
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return {"ok": True, "data": response.json(), "error": None}
    except requests.RequestException as exc:
        return {"ok": False, "data": None, "error": str(exc)}


def get_stats(base_url: str | None = None) -> dict[str, Any]:
    """Fetch GET /stats (cumulative DB totals)."""
    try:
        response = requests.get(
            f"{_base_url(base_url)}/stats",
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return {"ok": True, "data": response.json(), "error": None}
    except requests.RequestException as exc:
        return {"ok": False, "data": None, "error": str(exc)}


def get_raw_news(
    base_url: str | None = None,
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
    base_url: str | None = None,
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
    base_url: str | None = None,
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
    base_url: str | None = None,
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
    base_url: str | None = None,
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
    base_url: str | None = None,
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


def get_scweet_status(base_url: str | None = None) -> dict[str, Any]:
    """Fetch GET /health/scweet."""
    try:
        response = requests.get(
            f"{_base_url(base_url)}/health/scweet",
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return {"ok": True, "data": response.json(), "error": None}
    except requests.RequestException as exc:
        return {"ok": False, "data": None, "error": str(exc)}


def refresh_scweet_session(
    base_url: str | None = None,
    *,
    force: bool = False,
) -> dict[str, Any]:
    """POST /scweet/session/refresh."""
    try:
        response = requests.post(
            f"{_base_url(base_url)}/scweet/session/refresh",
            params={"force": force},
            timeout=120,
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        message = str(exc)
        if isinstance(exc, requests.HTTPError) and exc.response is not None:
            try:
                detail = exc.response.json()
                message = detail.get("error") or detail.get("detail") or message
            except ValueError:
                message = exc.response.text or message
        return {"ok": False, "error": message}


def run_scweet_test_search(
    base_url: str | None = None,
    *,
    query: str = "",
    limit: int = 5,
) -> dict[str, Any]:
    """POST /scweet/search/test."""
    try:
        response = requests.post(
            f"{_base_url(base_url)}/scweet/search/test",
            params={"query": query, "limit": limit},
            timeout=180,
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        message = str(exc)
        if isinstance(exc, requests.HTTPError) and exc.response is not None:
            try:
                detail = exc.response.json()
                message = detail.get("error") or detail.get("detail") or message
            except ValueError:
                message = exc.response.text or message
        return {"ok": False, "error": message, "items": []}


def get_scweet_accounts(base_url: str | None = None, *, runs_limit: int = 10) -> dict[str, Any]:
    """GET /scweet/accounts."""
    try:
        response = requests.get(
            f"{_base_url(base_url)}/scweet/accounts",
            params={"runs_limit": runs_limit},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        return {"ok": False, "error": str(exc), "accounts": [], "runs": []}


def get_x_watch_list(base_url: str | None = None) -> dict[str, Any]:
    """GET /scweet/watch — watched X profiles."""
    try:
        response = requests.get(
            f"{_base_url(base_url)}/scweet/watch",
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        return {"ok": False, "error": str(exc), "items": []}


def add_x_watch_account(base_url: str | None = None, *, handle: str) -> dict[str, Any]:
    """POST /scweet/watch."""
    try:
        response = requests.post(
            f"{_base_url(base_url)}/scweet/watch",
            json={"handle": handle},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        message = str(exc)
        if isinstance(exc, requests.HTTPError) and exc.response is not None:
            try:
                detail = exc.response.json()
                message = detail.get("error") or detail.get("detail") or message
            except ValueError:
                message = exc.response.text or message
        return {"ok": False, "error": message}


def remove_x_watch_account(base_url: str | None = None, *, handle: str) -> dict[str, Any]:
    """DELETE /scweet/watch/{handle}."""
    handle = handle.lstrip("@")
    try:
        response = requests.delete(
            f"{_base_url(base_url)}/scweet/watch/{handle}",
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        message = str(exc)
        if isinstance(exc, requests.HTTPError) and exc.response is not None:
            try:
                detail = exc.response.json()
                message = detail.get("error") or detail.get("detail") or message
            except ValueError:
                message = exc.response.text or message
        return {"ok": False, "error": message}


def fetch_x_watch_account(
    base_url: str | None = None,
    *,
    handle: str,
    limit: int = 50,
) -> dict[str, Any]:
    """POST /scweet/watch/{handle}/fetch."""
    handle = handle.lstrip("@")
    try:
        response = requests.post(
            f"{_base_url(base_url)}/scweet/watch/{handle}/fetch",
            params={"limit": limit},
            timeout=180,
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        message = str(exc)
        if isinstance(exc, requests.HTTPError) and exc.response is not None:
            try:
                detail = exc.response.json()
                message = detail.get("error") or detail.get("detail") or message
            except ValueError:
                message = exc.response.text or message
        return {"ok": False, "error": message}


def fetch_all_x_watch_accounts(base_url: str | None = None) -> dict[str, Any]:
    """POST /scweet/watch/fetch-all."""
    try:
        response = requests.post(
            f"{_base_url(base_url)}/scweet/watch/fetch-all",
            timeout=600,
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        return {"ok": False, "error": str(exc)}


def run_scweet_operation(
    base_url: str | None = None,
    *,
    operation: str,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """POST /scweet/run."""
    try:
        response = requests.post(
            f"{_base_url(base_url)}/scweet/run",
            json={"operation": operation, "params": params or {}},
            timeout=180,
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        message = str(exc)
        if isinstance(exc, requests.HTTPError) and exc.response is not None:
            try:
                detail = exc.response.json()
                message = detail.get("error") or detail.get("detail") or message
            except ValueError:
                message = exc.response.text or message
        return {"ok": False, "error": message}


def _spiderfoot_json(
    method: str,
    path: str,
    base_url: str | None = None,
    *,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
    timeout: int = REQUEST_TIMEOUT,
) -> dict[str, Any]:
    try:
        response = requests.request(
            method,
            f"{_base_url(base_url)}{path}",
            params=params,
            json=json_body,
            timeout=timeout,
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        message = str(exc)
        if isinstance(exc, requests.HTTPError) and exc.response is not None:
            try:
                detail = exc.response.json()
                message = detail.get("detail") or detail.get("error") or message
            except ValueError:
                message = exc.response.text or message
        return {"ok": False, "error": message}


def get_spiderfoot_status(base_url: str | None = None) -> dict[str, Any]:
    """GET /health/spiderfoot."""
    try:
        response = requests.get(
            f"{_base_url(base_url)}/health/spiderfoot",
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return {"ok": True, "data": response.json()}
    except requests.RequestException as exc:
        return {"ok": False, "error": str(exc)}


def list_spiderfoot_scans(base_url: str | None = None) -> dict[str, Any]:
    return _spiderfoot_json("GET", "/spiderfoot/scans", base_url)


def get_spiderfoot_scan(base_url: str | None = None, scan_id: str = "") -> dict[str, Any]:
    return _spiderfoot_json("GET", f"/spiderfoot/scans/{scan_id}", base_url)


def get_spiderfoot_scan_results(
    base_url: str | None = None,
    scan_id: str = "",
    *,
    event_type: str = "",
    unique: bool = False,
    limit: int = 500,
) -> dict[str, Any]:
    return _spiderfoot_json(
        "GET",
        f"/spiderfoot/scans/{scan_id}/results",
        base_url,
        params={"event_type": event_type, "unique": unique, "limit": limit},
        timeout=180,
    )


def start_spiderfoot_scan(
    base_url: str | None = None,
    *,
    scan_name: str = "",
    target: str = "",
    usecase: str = "passive",
    module_list: str = "",
    type_list: str = "",
) -> dict[str, Any]:
    return _spiderfoot_json(
        "POST",
        "/spiderfoot/scans",
        base_url,
        json_body={
            "scan_name": scan_name,
            "target": target,
            "usecase": usecase,
            "module_list": module_list,
            "type_list": type_list,
        },
        timeout=120,
    )


def stop_spiderfoot_scan(base_url: str | None = None, scan_id: str = "") -> dict[str, Any]:
    return _spiderfoot_json("POST", f"/spiderfoot/scans/{scan_id}/stop", base_url)


def delete_spiderfoot_scan(base_url: str | None = None, scan_id: str = "") -> dict[str, Any]:
    try:
        response = requests.delete(
            f"{_base_url(base_url)}/spiderfoot/scans/{scan_id}",
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        message = str(exc)
        if isinstance(exc, requests.HTTPError) and exc.response is not None:
            try:
                detail = exc.response.json()
                message = detail.get("detail") or message
            except ValueError:
                message = exc.response.text or message
        return {"ok": False, "error": message}


def list_spiderfoot_modules(base_url: str | None = None) -> dict[str, Any]:
    return _spiderfoot_json("GET", "/spiderfoot/modules", base_url, timeout=120)


def get_llm_health(base_url: str | None = None) -> dict[str, Any]:
    if _use_embedded_for_local_llm():
        from dashboard import embedded_backend

        return embedded_backend.get_llm_health("")
    try:
        response = requests.get(f"{_base_url(base_url)}/health/llm", timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        return {"ok": False, "error": str(exc)}

    # When dashboard runs on your Mac (not Render), merge local Ollama probe into API health.
    if not os.environ.get("RENDER"):
        try:
            from app.integrations.ollama_client import local_llm_mode_active, probe_ollama
            from app.config import get_settings

            if local_llm_mode_active():
                probe = probe_ollama(timeout=3.0)
                settings = get_settings()
                llm = payload.get("llm") or {}
                llm["local_llm_enabled"] = True
                llm["local_llm"] = {
                    "enabled": True,
                    "reachable": probe.get("reachable", False),
                    "model_ready": probe.get("model_ready", False),
                    "model": settings.local_llm_model,
                    "base_url": settings.local_llm_base_url,
                    "error": probe.get("error"),
                }
                if probe.get("reachable") and probe.get("model_ready"):
                    llm["provider"] = "ollama"
                    llm["model"] = settings.local_llm_model
                    llm["mode"] = "local_ollama"
                else:
                    llm["mode"] = "local_ollama_unavailable"
                payload["llm"] = llm
        except Exception:
            pass

    return {"ok": True, "data": payload}


def update_draft(base_url: str | None, draft_id: int, post_text: str) -> dict[str, Any]:
    try:
        response = requests.patch(
            f"{_base_url(base_url)}/drafts/{draft_id}",
            json={"post_text": post_text},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        message = str(exc)
        if isinstance(exc, requests.HTTPError) and exc.response is not None:
            try:
                message = exc.response.json().get("detail", message)
            except ValueError:
                message = exc.response.text or message
        return {"ok": False, "error": message}


def regenerate_draft(
    base_url: str | None,
    draft_id: int,
    *,
    tone: str = "neutral",
) -> dict[str, Any]:
    try:
        response = requests.post(
            f"{_base_url(base_url)}/drafts/{draft_id}/regenerate",
            json={"tone": tone},
            timeout=120,
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        message = str(exc)
        if isinstance(exc, requests.HTTPError) and exc.response is not None:
            try:
                message = exc.response.json().get("detail", message)
            except ValueError:
                message = exc.response.text or message
        return {"ok": False, "error": message}


def audit_draft(base_url: str | None, draft_id: int) -> dict[str, Any]:
    try:
        response = requests.post(
            f"{_base_url(base_url)}/drafts/{draft_id}/audit",
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        return {"ok": False, "error": str(exc)}


def llm_generate_post(base_url: str | None, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        response = requests.post(
            f"{_base_url(base_url)}/dashboard/generate-post",
            json=payload,
            timeout=120,
        )
        response.raise_for_status()
        return {"ok": True, "data": response.json()}
    except requests.RequestException as exc:
        return {"ok": False, "error": str(exc)}


def llm_audit_post(
    base_url: str | None,
    *,
    draft_post: str,
    raw_report: str = "",
    source_information: str = "",
) -> dict[str, Any]:
    try:
        response = requests.post(
            f"{_base_url(base_url)}/dashboard/audit-post",
            json={
                "draft_post": draft_post,
                "raw_report_text": raw_report,
                "source_information": source_information,
            },
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return {"ok": True, "data": response.json()}
    except requests.RequestException as exc:
        return {"ok": False, "error": str(exc)}


def draft_newsroom_post_local(base_url: str | None, payload: dict[str, Any]) -> dict[str, Any]:
    if _use_embedded_for_local_llm():
        from dashboard import embedded_backend

        return embedded_backend.draft_newsroom_post_local("", payload)
    try:
        response = requests.post(
            f"{_base_url(base_url)}/llm/draft-newsroom-post",
            json=payload,
            timeout=180,
        )
        response.raise_for_status()
        return {"ok": True, "data": response.json()}
    except requests.RequestException as exc:
        message = str(exc)
        if isinstance(exc, requests.HTTPError) and exc.response is not None:
            try:
                detail = exc.response.json()
                message = detail.get("detail") or message
            except ValueError:
                message = exc.response.text or message
        return {"ok": False, "error": message}


def audit_source_local(base_url: str | None, payload: dict[str, Any]) -> dict[str, Any]:
    if _use_embedded_for_local_llm():
        from dashboard import embedded_backend

        return embedded_backend.audit_source_local("", payload)
    try:
        response = requests.post(
            f"{_base_url(base_url)}/llm/audit-source",
            json=payload,
            timeout=120,
        )
        response.raise_for_status()
        return {"ok": True, "data": response.json()}
    except requests.RequestException as exc:
        message = str(exc)
        if isinstance(exc, requests.HTTPError) and exc.response is not None:
            try:
                message = exc.response.json().get("detail", message)
            except ValueError:
                message = exc.response.text or message
        return {"ok": False, "error": message}


def save_training_example(base_url: str | None, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        response = requests.post(
            f"{_base_url(base_url)}/training/save-newsroom-example",
            json=payload,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        return {"ok": False, "error": str(exc)}


def export_training_jsonl(base_url: str | None) -> dict[str, Any]:
    try:
        response = requests.get(
            f"{_base_url(base_url)}/training/export-newsroom-jsonl",
            timeout=120,
        )
        response.raise_for_status()
        return {"ok": True, "content": response.text}
    except requests.RequestException as exc:
        return {"ok": False, "error": str(exc)}


def test_buffer(base_url: str | None, *, admin_secret: str = "") -> dict[str, Any]:
    headers: dict[str, str] = {}
    secret = admin_secret or os.environ.get("BUFFER_TEST_SECRET", "").strip()
    if secret:
        headers["X-Admin-Secret"] = secret
    try:
        response = requests.post(
            f"{_base_url(base_url)}/api/test/buffer",
            headers=headers,
            timeout=60,
        )
        response.raise_for_status()
        return {"ok": True, "data": response.json()}
    except requests.RequestException as exc:
        message = str(exc)
        if isinstance(exc, requests.HTTPError) and exc.response is not None:
            try:
                message = exc.response.json().get("detail", message)
            except ValueError:
                message = exc.response.text or message
        return {"ok": False, "error": message}


def get_buffer_channels(base_url: str | None = None) -> dict[str, Any]:
    try:
        response = requests.get(f"{_base_url(base_url)}/api/buffer/channels", timeout=60)
        response.raise_for_status()
        return {"ok": True, "data": response.json()}
    except requests.RequestException as exc:
        return {"ok": False, "error": str(exc)}


def send_approved_batch(base_url: str | None, *, limit: int = 50) -> dict[str, Any]:
    import os

    headers: dict[str, str] = {}
    secret = os.environ.get("BUFFER_TEST_SECRET", "").strip()
    if secret:
        headers["X-Admin-Secret"] = secret
    try:
        response = requests.post(
            f"{_base_url(base_url)}/api/posts/send-approved-batch",
            params={"limit": limit},
            headers=headers,
            timeout=300,
        )
        try:
            body = response.json()
        except ValueError:
            body = {"error": response.text}
        if response.ok:
            return {"ok": True, **body} if isinstance(body, dict) else {"ok": True, "data": body}
        return {"ok": False, **body} if isinstance(body, dict) else {"ok": False, "error": str(body)}
    except requests.RequestException as exc:
        return {"ok": False, "error": str(exc)}


def send_post_to_buffer(base_url: str | None, post_id: int) -> dict[str, Any]:
    try:
        response = requests.post(
            f"{_base_url(base_url)}/api/posts/{post_id}/send-to-buffer",
            timeout=60,
        )
        try:
            body = response.json()
        except ValueError:
            body = {"error": response.text}
        if response.ok:
            return {"ok": True, **body} if isinstance(body, dict) else {"ok": True, "data": body}
        message = body.get("error") if isinstance(body, dict) else str(body)
        if isinstance(body, dict) and not message:
            message = body.get("detail") or str(body)
        return {"ok": False, "error": message, **(body if isinstance(body, dict) else {})}
    except requests.RequestException as exc:
        return {"ok": False, "error": str(exc)}


def get_ollama_health(base_url: str | None = None) -> dict[str, Any]:
    if _use_embedded_for_local_llm():
        from dashboard import embedded_backend

        return embedded_backend.get_ollama_health("")
    try:
        response = requests.get(f"{_base_url(base_url)}/api/health/ollama", timeout=30)
        response.raise_for_status()
        return {"ok": True, "data": response.json()}
    except requests.RequestException as exc:
        return {"ok": False, "error": str(exc)}


def get_buffer_health(base_url: str | None = None) -> dict[str, Any]:
    try:
        response = requests.get(f"{_base_url(base_url)}/api/health/buffer", timeout=60)
        response.raise_for_status()
        return {"ok": True, "data": response.json()}
    except requests.RequestException as exc:
        return {"ok": False, "error": str(exc)}


def get_supabase_health(base_url: str | None = None) -> dict[str, Any]:
    try:
        response = requests.get(f"{_base_url(base_url)}/api/health/supabase", timeout=30)
        response.raise_for_status()
        return {"ok": True, "data": response.json()}
    except requests.RequestException as exc:
        return {"ok": False, "error": str(exc)}


def draft_local_post(base_url: str | None, payload: dict[str, Any]) -> dict[str, Any]:
    if _use_embedded_for_local_llm():
        from dashboard import embedded_backend

        return embedded_backend.draft_local_post("", payload)
    try:
        response = requests.post(
            f"{_base_url(base_url)}/api/llm/draft-local",
            json=payload,
            timeout=180,
        )
        response.raise_for_status()
        return {"ok": True, "data": response.json()}
    except requests.RequestException as exc:
        message = str(exc)
        if isinstance(exc, requests.HTTPError) and exc.response is not None:
            try:
                message = exc.response.json().get("detail", message)
            except ValueError:
                message = exc.response.text or message
        return {"ok": False, "error": message}


def approve_post(base_url: str | None, post_id: int) -> dict[str, Any]:
    try:
        response = requests.post(f"{_base_url(base_url)}/api/posts/{post_id}/approve", timeout=30)
        response.raise_for_status()
        return {"ok": True, **response.json()}
    except requests.RequestException as exc:
        message = str(exc)
        if isinstance(exc, requests.HTTPError) and exc.response is not None:
            try:
                message = exc.response.json().get("detail", message)
            except ValueError:
                message = exc.response.text or message
        return {"ok": False, "error": message}


def run_e2e_pipeline(
    base_url: str | None,
    *,
    dry_run: bool = True,
    admin_secret: str = "",
) -> dict[str, Any]:
    headers: dict[str, str] = {}
    secret = admin_secret or os.environ.get("ADMIN_TEST_SECRET") or os.environ.get("BUFFER_TEST_SECRET", "")
    if secret:
        headers["X-Admin-Secret"] = secret.strip()
    try:
        response = requests.post(
            f"{_base_url(base_url)}/api/test/e2e-local-to-buffer",
            json={"dry_run": dry_run},
            headers=headers,
            timeout=300,
        )
        try:
            body = response.json()
        except ValueError:
            body = {"error": response.text}
        if response.ok:
            return {"ok": True, **body} if isinstance(body, dict) else {"ok": True, "data": body}
        return {"ok": False, **body} if isinstance(body, dict) else {"ok": False, "error": str(body)}
    except requests.RequestException as exc:
        return {"ok": False, "error": str(exc)}

