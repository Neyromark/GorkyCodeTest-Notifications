from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator


class NotificationType(str, Enum):
    TASK = "task"
    MEETING = "meeting"


class NotificationCreate(BaseModel):
    type: NotificationType
    date_notify: datetime
    user_id: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=500)
    date: datetime

    @field_validator("date_notify", "date")
    @classmethod
    def ensure_tz_aware(cls, v: datetime) -> datetime:
        # Приводим к UTC, чтобы одно и то же время давало один и тот же job_id
        return v.astimezone(timezone.utc) if v.tzinfo else v.replace(tzinfo=timezone.utc)

    @model_validator(mode="after")
    def check_rules(self) -> "NotificationCreate":
        if self.date_notify <= datetime.now(timezone.utc):
            raise ValueError("date_notify must be in the future")
        if self.date_notify > self.date:
            raise ValueError("date_notify cannot be later than date")
        return self


class NotificationCreated(BaseModel):
    job_id: str


class ErrorResponse(BaseModel):
    detail: str