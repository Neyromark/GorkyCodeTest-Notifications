import logging
from datetime import datetime

from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler

from app.config import settings
from app.delivery import send_notification
from app.schemas import NotificationCreate

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler(
    jobstores={"default": SQLAlchemyJobStore(url=settings.database_url)},
    timezone=settings.timezone,
)


def _job_id(data: NotificationCreate) -> str:
    return f"notify_{data.user_id}_{int(data.date_notify.timestamp())}"


def schedule(data: NotificationCreate) -> str:
    job = scheduler.add_job(
        func=send_notification,
        trigger="date",
        run_date=data.date_notify,
        args=[data.model_dump(mode="json")],
        id=_job_id(data),
        replace_existing=True,
        misfire_grace_time=60,
    )
    logger.info(
        "Scheduled job_id=%s user_id=%s type=%s run_date=%s",
        job.id, data.user_id, data.type.value, data.date_notify.isoformat(),
    )
    return job.id