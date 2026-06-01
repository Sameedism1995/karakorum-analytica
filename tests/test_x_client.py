"""X API connection tests."""

from unittest.mock import MagicMock, patch

from app.config import Settings
from app.integrations.x_client import check_x_connection


def test_x_not_configured():
    settings = Settings(_env_file=None)
    with patch("app.integrations.x_client.get_settings", return_value=settings):
        result = check_x_connection()
    assert result["ok"] is False
    assert result["configured"] is False


def test_x_oauth_configured_property():
    settings = Settings(
        _env_file=None,
        x_api_key="key",
        x_api_secret="secret",
        x_access_token="token",
        x_access_token_secret="token_secret",
    )
    assert settings.x_oauth_configured is True
    assert settings.x_configured is True


def test_x_connection_success_with_oauth():
    settings = Settings(
        _env_file=None,
        x_api_key="key",
        x_api_secret="secret",
        x_access_token="token",
        x_access_token_secret="token_secret",
    )
    mock_user = MagicMock()
    mock_user.username = "karakorum"
    mock_user.name = "Karakorum Analytica"
    mock_user.id = 12345
    mock_user.public_metrics = {"followers_count": 100}

    mock_me = MagicMock()
    mock_me.data = mock_user

    mock_client = MagicMock()
    mock_client.get_me.return_value = mock_me

    with patch("app.integrations.x_client.get_settings", return_value=settings):
        with patch("app.integrations.x_client.get_x_write_client", return_value=mock_client):
            result = check_x_connection()

    assert result["ok"] is True
    assert result["username"] == "karakorum"
    assert result["can_post"] is True
