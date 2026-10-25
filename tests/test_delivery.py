from unittest.mock import Mock, patch

import requests

from app.delivery import send_notification


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
    mock_post.return_value.raise_for_status = Mock()

    send_notification(_payload())

    mock_post.assert_called_once()
    _, kwargs = mock_post.call_args
    assert kwargs["json"]["user_id"] == 123
    assert kwargs["json"]["type"] == "meeting"
    assert kwargs["json"]["title"] == "Созвон"
    assert kwargs["timeout"] > 0


@patch("app.delivery.requests.post")
def test_send_notification_uses_configured_url(mock_post):
    from app.config import settings
    mock_post.return_value = Mock(status_code=200)
    mock_post.return_value.raise_for_status = Mock()

    send_notification(_payload())

    args, _ = mock_post.call_args
    assert args[0] == settings.notification_service_url


@patch("app.delivery.requests.post")
def test_send_notification_http_error_is_logged_not_raised(mock_post):
    mock_post.return_value = Mock(status_code=500)
    mock_post.return_value.raise_for_status.side_effect = requests.HTTPError("500")

    send_notification(_payload())


@patch("app.delivery.requests.post")
def test_send_notification_timeout_is_logged_not_raised(mock_post):
    mock_post.side_effect = requests.Timeout("read timeout")

    send_notification(_payload())


@patch("app.delivery.requests.post")
def test_send_notification_connection_error_is_logged_not_raised(mock_post):
    mock_post.side_effect = requests.ConnectionError("connection refused")

    send_notification(_payload())


@patch("app.delivery.requests.post")
def test_send_notification_logs_error_on_failure(mock_post, caplog):
    mock_post.side_effect = requests.ConnectionError("refused")

    with caplog.at_level("ERROR", logger="app.delivery"):
        send_notification(_payload())

    assert any("Delivery failed user_id=123" in rec.message for rec in caplog.records)