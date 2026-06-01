"""Background collection job state (avoids HTTP timeouts on slow pipelines)."""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any

from loguru import logger

from app.database import SessionLocal
from app.services.collection_service import collect_all
from app.services.draft_service import generate_drafts_for_incidents
from app.services.incident_service import process_incidents
from app.services.stats_service import get_dashboard_stats

_lock = threading.Lock()
_state: dict[str, Any] = {
    "status": "idle",
    "progress": 0,
    "step": "",
    "events": [],
    "started_at": None,
    "finished_at": None,
    "result": None,
    "error": None,
}

STEP_LABELS = {
    "start": "Starting",
    "gdelt": "GDELT",
    "reliefweb": "ReliefWeb",
    "acled": "ACLED",
    "news_web": "News channels",
    "scweet": "X (Scweet)",
    "x_watch": "X watch list",
    "save": "Saving articles",
    "incidents": "Grouping incidents",
    "drafts": "Generating drafts",
    "done": "Complete",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _report(message: str, progress: int, step: str) -> None:
    global _state
    with _lock:
        events = list(_state.get("events") or [])
        events.append({"at": _utc_now(), "message": message, "step": step})
        _state["progress"] = min(max(progress, 0), 100)
        _state["step"] = step
        _state["events"] = events[-40:]


def _run_pipeline() -> None:
    global _state
    db = SessionLocal()
    started_at = _state.get("started_at")
    try:
        _report("Collection pipeline started", 5, "start")

        collection = collect_all(db, on_progress=_report)

        _report("Grouping similar reports into incidents…", 72, "incidents")
        incidents = process_incidents(db)
        _report(
            f"Incidents — created {incidents.get('incidents_created', 0)}, "
            f"updated {incidents.get('incidents_updated', 0)}",
            82,
            "incidents",
        )

        _report("Generating neutral draft posts for review…", 88, "drafts")
        drafts = generate_drafts_for_incidents(db)
        _report(f"Drafts — created {drafts.get('drafts_created', 0)} new posts", 95, "drafts")

        result = {"collection": collection, "incidents": incidents, "drafts": drafts}
        totals = get_dashboard_stats(db)
        _report(
            f"Done — saved {collection.get('saved', 0)} articles, "
            f"{incidents.get('incidents_created', 0)} new incidents, "
            f"{drafts.get('drafts_created', 0)} new drafts "
            f"(totals: {totals['total_raw']} raw, {totals['total_incidents']} incidents, "
            f"{totals['total_drafts']} drafts)",
            100,
            "done",
        )
        with _lock:
            _state = {
                "status": "completed",
                "progress": 100,
                "step": "done",
                "events": _state.get("events") or [],
                "started_at": started_at,
                "finished_at": _utc_now(),
                "result": result,
                "totals": totals,
                "error": None,
            }
        logger.info(f"Background collection finished: {result}")
    except Exception as exc:
        logger.exception(f"Background collection failed: {exc}")
        _report(f"Failed: {exc}", _state.get("progress", 0), _state.get("step", "error"))
        with _lock:
            _state = {
                "status": "failed",
                "progress": _state.get("progress", 0),
                "step": "error",
                "events": _state.get("events") or [],
                "started_at": started_at,
                "finished_at": _utc_now(),
                "result": None,
                "error": str(exc),
            }
    finally:
        db.close()


def start_collection_job() -> dict[str, Any]:
    """Start collection in a background thread if not already running."""
    global _state
    with _lock:
        if _state["status"] == "running":
            return {
                "status": "running",
                "message": "Collection already in progress",
                "started_at": _state.get("started_at"),
                "progress": _state.get("progress", 0),
                "step": _state.get("step", ""),
            }
        started_at = _utc_now()
        _state = {
            "status": "running",
            "progress": 0,
            "step": "start",
            "events": [{"at": started_at, "message": "Queued collection job", "step": "start"}],
            "started_at": started_at,
            "finished_at": None,
            "result": None,
            "error": None,
        }

    thread = threading.Thread(target=_run_pipeline, name="collection-job", daemon=True)
    thread.start()
    return {
        "status": "started",
        "message": "Collection started in background",
        "started_at": started_at,
        "progress": 0,
        "step": "start",
    }


def get_collection_job_status() -> dict[str, Any]:
    with _lock:
        payload = dict(_state)
        payload["step_label"] = STEP_LABELS.get(payload.get("step", ""), payload.get("step", ""))
        return payload
