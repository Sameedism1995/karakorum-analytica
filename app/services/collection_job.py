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

_lock = threading.Lock()
_state: dict[str, Any] = {
    "status": "idle",
    "started_at": None,
    "finished_at": None,
    "result": None,
    "error": None,
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_pipeline() -> None:
    global _state
    db = SessionLocal()
    started_at = _state.get("started_at")
    try:
        collection = collect_all(db)
        incidents = process_incidents(db)
        drafts = generate_drafts_for_incidents(db)
        result = {"collection": collection, "incidents": incidents, "drafts": drafts}
        with _lock:
            _state = {
                "status": "completed",
                "started_at": started_at,
                "finished_at": _utc_now(),
                "result": result,
                "error": None,
            }
        logger.info(f"Background collection finished: {result}")
    except Exception as exc:
        logger.exception(f"Background collection failed: {exc}")
        with _lock:
            _state = {
                "status": "failed",
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
            }
        started_at = _utc_now()
        _state = {
            "status": "running",
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
    }


def get_collection_job_status() -> dict[str, Any]:
    with _lock:
        return dict(_state)
