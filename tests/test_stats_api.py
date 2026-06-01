"""Dashboard stats API tests."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_stats_endpoint_returns_cumulative_totals():
    response = client.get("/stats")
    assert response.status_code == 200
    body = response.json()
    assert "total_raw" in body
    assert "total_incidents" in body
    assert "total_drafts" in body
    assert "sources_active" in body
    assert "last_collection" in body
    assert body["total_raw"] >= 0
