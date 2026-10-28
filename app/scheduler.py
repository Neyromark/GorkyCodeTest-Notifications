import hashlib
import logging
from datetime import datetime, timedelta, timezone

from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler

from app.config import settings
from app.delivery import DeliveryError, send_notification
from app.schemas import NotificationCreate

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler(
    jobstores={"default": SQLAlchemyJobStore(url=settings.database_url)},
    timezone=settings.timezone,
)


def _job_id(data: NotificationCreate) -> str:
    # Хэш от всего содержимого: повтор того же запроса идемпотентен,
    # а разные напоминания на одно время не затирают друг друга
    digest = hashlib.sha256(data.model_dump_json().encode()).hexdigest()[:16]
    return f"notify_{data.user_id}_{digest}"


def deliver(payload: dict, job_id: str, attempt: int = 1) -> None:
    now = datetime.now(timezone.utc)
    event_date = datetime.fromisoformat(payload["date"])
    if now > event_date + timedelta(seconds=settings.stale_after_seconds):
        logger.warning("Skipping stale job_id=%s: event at %s already passed", job_id, payload["date"])
        return

    try:
        send_notification(payload)
    except DeliveryError:
        if attempt >= settings.max_delivery_attempts:
            logger.exception("Giving up job_id=%s after %d attempts", job_id, attempt)
            return
        delay = settings.retry_base_delay * 2 ** (attempt - 1)
        logger.warning(
            "Delivery failed job_id=%s attempt=%d, retrying in %ss",
            job_id, attempt, delay, exc_info=True,
        )
        scheduler.add_job(
            func=deliver,
            trigger="date",
            run_date=now + timedelta(seconds=delay),
            args=[payload, job_id, attempt + 1],
            id=f"{job_id}_retry{attempt}",
            replace_existing=True,
            misfire_grace_time=None,
        )


def schedule(data: NotificationCreate) -> str:
    job_id = _job_id(data)
    job = scheduler.add_job(
        func=deliver,
        trigger="date",
        run_date=data.date_notify,
        args=[data.model_dump(mode="json"), job_id],
        id=job_id,
        replace_existing=True,
        # Опоздавшие (после простоя сервиса) джобы всё равно выполняются,
        # а слишком поздние отсекает проверка в deliver()
        misfire_grace_time=None,
        coalesce=True,
    )
    logger.info(
        "Scheduled job_id=%s user_id=%s type=%s run_date=%s",
        job.id, data.user_id, data.type.value, data.date_notify.isoformat(),
    )
    return job.id
