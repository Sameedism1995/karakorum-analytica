"""Pipeline health endpoint tests."""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


@patch("app.api.pipeline_routes.get_ollama_health")
def test_health_ollama(mock_health):
    mock_health.return_value = {
        "enabled": True,
        "base_url": "http://localhost:11434",
        "model": "qwen3:4b",
        "server_reachable": True,
        "model_available": True,
        "generate_ok": True,
        "error": None,
    }
    response = client.get("/api/health/ollama")
    assert response.status_code == 200
    body = response.json()
    assert body["model"] == "qwen3:4b"
    assert body["server_reachable"] is True


@patch("app.services.buffer_service.get_buffer_health")
def test_health_buffer(mock_health):
    mock_health.return_value = {
        "api_key_configured": True,
        "channel_handle": "@kkanalytica",
        "channel_found": True,
        "channel_id": "ch-123",
        "error": None,
    }
    response = client.get("/api/health/buffer")
    assert response.status_code == 200
    assert response.json()["channel_found"] is True


@patch("app.api.pipeline_routes.run_e2e_local_to_buffer")
def test_e2e_dry_run_default(mock_run):
    mock_run.return_value = {"ok": True, "dry_run": True, "message": "ok", "steps": {}}
    response = client.post("/api/test/e2e-local-to-buffer", json={"dry_run": True})
    assert response.status_code == 200
    assert response.json()["dry_run"] is True
