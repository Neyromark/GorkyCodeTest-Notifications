import logging
import requests
from app.config import settings

logger = logging.getLogger(__name__)


def _format_message(payload: dict) -> str:
    title = payload.get("title", "Задача")
    event_date = payload.get("date", "")
    return f"Напоминание: {title}\nВремя: {event_date}"


def send_notification(payload: dict) -> None:
    vk_payload = {
        "user_id": payload["user_id"],
        "message": _format_message(payload)
    }
    headers = {"Content-Type": "application/json"}
    if settings.auth_token:
        headers["Authorization"] = f"Bearer {settings.auth_token}"
    else:
        headers["Authorization"] = "пока без JWT токена"

    try:
        response = requests.post(
            settings.notification_service_url,
            json=vk_payload,
            headers=headers,
            timeout=settings.request_timeout,
        )
        response.raise_for_status()
        logger.info(
            "Delivered user_id=%s status=%s",
            vk_payload["user_id"], response.status_code
        )
    except requests.RequestException:
        logger.exception("Delivery failed user_id=%s", payload["user_id"])