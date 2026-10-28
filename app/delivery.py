import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from app.config import settings

logger = logging.getLogger(__name__)

MOSCOW_TZ = ZoneInfo("Europe/Moscow")


class DeliveryError(Exception):
    """Временная ошибка доставки — имеет смысл повторить попытку."""


def _format_date(value: str) -> str:
    if not value:
        return ""
    local = datetime.fromisoformat(value).astimezone(MOSCOW_TZ)
    return local.strftime("%d.%m.%Y %H:%M") + " МСК"


def _format_message(payload: dict) -> str:
    title = payload.get("title", "Задача")
    event_date = _format_date(payload.get("date", ""))
    return f"Напоминание: {title}\nВремя: {event_date}"


def send_notification(payload: dict) -> None:
    """Отправляет сообщение в бота. Бросает DeliveryError, если стоит повторить."""
    vk_payload = {
        "user_id": payload["user_id"],
        "message": _format_message(payload)
    }
    headers = {"Content-Type": "application/json"}
    if settings.auth_token:
        headers["Authorization"] = f"Bearer {settings.auth_token}"

    try:
        response = requests.post(
            settings.notification_service_url,
            json=vk_payload,
            headers=headers,
            timeout=settings.request_timeout,
        )
    except requests.RequestException as exc:
        raise DeliveryError(f"request failed: {exc}") from exc

    if response.status_code >= 500 or response.status_code == 429:
        raise DeliveryError(f"bot responded with status {response.status_code}")
    if response.status_code >= 400:
        # Ошибка в самом запросе — повтор не поможет
        logger.error(
            "Delivery rejected user_id=%s status=%s body=%s",
            vk_payload["user_id"], response.status_code, response.text[:200],
        )
        return

    logger.info(
        "Delivered user_id=%s status=%s",
        vk_payload["user_id"], response.status_code
    )
