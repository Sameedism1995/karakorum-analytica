"""API health and deployment endpoints."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "karakorum-analytica-api"}


def test_root_includes_message():
    response = client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "Karakorum Analytica API is running"
    assert body["status"] == "running"
