"""Background collection job tests."""

from fastapi.testclient import TestClient

from app.main import app
from app.services import collection_job

client = TestClient(app)


def _reset_job_state() -> None:
    collection_job._state = {
        "status": "idle",
        "progress": 0,
        "step": "",
        "events": [],
        "started_at": None,
        "finished_at": None,
        "result": None,
        "error": None,
    }


def test_collect_run_returns_immediately():
    _reset_job_state()
    response = client.post("/collect/run")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] in {"started", "running"}


def test_collect_status_endpoint():
    _reset_job_state()
    response = client.get("/collect/status")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "idle"
    assert "progress" in body
    assert "events" in body
    assert "step_label" in body


def test_collect_status_includes_progress_fields_when_running():
    _reset_job_state()
    collection_job._state["status"] = "running"
    collection_job._state["progress"] = 42
    collection_job._state["step"] = "gdelt"
    collection_job._state["events"] = [
        {"at": "2026-01-01T00:00:00+00:00", "message": "Fetching GDELT", "step": "gdelt"},
    ]

    response = client.get("/collect/status")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "running"
    assert body["progress"] == 42
    assert body["step"] == "gdelt"
    assert body["step_label"] == "GDELT"
    assert len(body["events"]) == 1
