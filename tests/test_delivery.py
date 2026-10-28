from unittest.mock import Mock, patch

import pytest
import requests

from app.delivery import DeliveryError, send_notification


def _payload() -> dict:
    return {
        "type": "meeting",
        "date_notify": "2099-01-01T09:45:00Z",
        "user_id": 123,
        "title": "Созвон",
        "date": "2099-01-01T10:00:00Z",
    }


@patch("app.delivery.requests.post")
def test_send_notification_success(mock_post):
    mock_post.return_value = Mock(status_code=200)

    send_notification(_payload())

    mock_post.assert_called_once()
    _, kwargs = mock_post.call_args
    assert kwargs["json"]["user_id"] == 123
    assert kwargs["json"]["message"] == "Напоминание: Созвон\nВремя: 01.01.2099 13:00 МСК"
    assert kwargs["timeout"] > 0


@patch("app.delivery.requests.post")
def test_send_notification_uses_configured_url(mock_post):
    from app.config import settings
    mock_post.return_value = Mock(status_code=200)

    send_notification(_payload())

    args, _ = mock_post.call_args
    assert args[0] == settings.notification_service_url


@patch("app.delivery.requests.post")
def test_no_authorization_header_without_token(mock_post, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "auth_token", "")
    mock_post.return_value = Mock(status_code=200)

    send_notification(_payload())

    _, kwargs = mock_post.call_args
    assert "Authorization" not in kwargs["headers"]


@patch("app.delivery.requests.post")
def test_bearer_authorization_header_with_token(mock_post, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "auth_token", "secret")
    mock_post.return_value = Mock(status_code=200)

    send_notification(_payload())

    _, kwargs = mock_post.call_args
    assert kwargs["headers"]["Authorization"] == "Bearer secret"


@pytest.mark.parametrize("status_code", [500, 503, 429])
@patch("app.delivery.requests.post")
def test_server_error_raises_delivery_error(mock_post, status_code):
    mock_post.return_value = Mock(status_code=status_code)

    with pytest.raises(DeliveryError):
        send_notification(_payload())


@patch("app.delivery.requests.post")
def test_client_error_is_logged_not_raised(mock_post, caplog):
    mock_post.return_value = Mock(status_code=400, text="bad user_id")

    with caplog.at_level("ERROR", logger="app.delivery"):
        send_notification(_payload())

    assert any("Delivery rejected user_id=123" in rec.message for rec in caplog.records)


@pytest.mark.parametrize("exc", [
    requests.Timeout("read timeout"),
    requests.ConnectionError("connection refused"),
])
@patch("app.delivery.requests.post")
def test_network_error_raises_delivery_error(mock_post, exc):
    mock_post.side_effect = exc

    with pytest.raises(DeliveryError):
        send_notification(_payload())
