import logging

from fastapi import APIRouter, status

from app.scheduler import schedule
from app.schemas import NotificationCreate, NotificationCreated

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/notifications",
    response_model=NotificationCreated,
    status_code=status.HTTP_201_CREATED,
    summary="Принять задачу от бэка и запланировать напоминание",
)
def create_notification(data: NotificationCreate) -> NotificationCreated:
    job_id = schedule(data)
    logger.info(
        "Accepted notification: job_id=%s user_id=%s type=%s at=%s",
        job_id, data.user_id, data.type.value, data.date_notify.isoformat(),
    )
    return NotificationCreated(job_id=job_id)