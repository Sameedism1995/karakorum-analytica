"""Background collection job tests."""

from fastapi.testclient import TestClient

from app.main import app
from app.services import collection_job

client = TestClient(app)


def test_collect_run_returns_immediately():
    collection_job._state = {
        "status": "idle",
        "started_at": None,
        "finished_at": None,
        "result": None,
        "error": None,
    }
    response = client.post("/collect/run")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] in {"started", "running"}


def test_collect_status_endpoint():
    response = client.get("/collect/status")
    assert response.status_code == 200
    assert "status" in response.json()
