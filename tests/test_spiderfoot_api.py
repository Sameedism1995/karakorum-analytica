"""SpiderFoot health endpoint tests."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_spiderfoot_health_endpoint():
    with patch(
        "app.api.routes.get_spiderfoot_health",
        return_value={"enabled": True, "installed": True, "reachable": False, "error": "offline"},
    ):
        response = client.get("/health/spiderfoot")
    assert response.status_code == 200
    body = response.json()
    assert "spiderfoot" in body
    assert body["spiderfoot"]["enabled"] is True
