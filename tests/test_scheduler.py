from datetime import datetime, timedelta, timezone

import pytest

from app.schemas import NotificationCreate
from app.scheduler import schedule, _job_id


def _make_data(**overrides) -> NotificationCreate:
    now = datetime.now(timezone.utc)
    base = {
        "type": "meeting",
        "date_notify": now + timedelta(hours=1),
        "user_id": 123,
        "title": "Созвон",
        "date": now + timedelta(hours=2),
    }
    base.update(overrides)
    return NotificationCreate(**base)


def test_schedule_creates_job(fresh_scheduler):
    data = _make_data()
    job_id = schedule(data)

    job = fresh_scheduler.get_job(job_id)
    assert job is not None
    assert job.id == job_id
    assert job.args[0]["user_id"] == 123
    assert job.args[0]["type"] == "meeting"
    assert job.args[0]["title"] == "Созвон"


def test_schedule_is_idempotent(fresh_scheduler):
    """Повторный вызов с теми же данными не создаёт дубликат."""
    data = _make_data()
    job_id_1 = schedule(data)
    job_id_2 = schedule(data)

    assert job_id_1 == job_id_2
    assert len(fresh_scheduler.get_jobs()) == 1


def test_schedule_different_users_create_different_jobs(fresh_scheduler):
    schedule(_make_data(user_id=1))
    schedule(_make_data(user_id=2))
    assert len(fresh_scheduler.get_jobs()) == 2


def test_job_id_is_deterministic():
    data = _make_data()
    assert _job_id(data) == _job_id(data)
    assert _job_id(data).startswith(f"notify_{data.user_id}_")


def test_job_fires_and_calls_delivery(fresh_scheduler, monkeypatch):
    """Джоба реально запускается и вызывает delivery.send_notification."""
    calls = []

    def fake_send(payload: dict) -> None:
        calls.append(payload)

    # Подменяем функцию, которую держит scheduler (импортирована в scheduler.py)
    import app.scheduler as sched_module
    monkeypatch.setattr(sched_module, "send_notification", fake_send)

    now = datetime.now(timezone.utc)
    data = _make_data(
        date_notify=now + timedelta(milliseconds=200),
        date=now + timedelta(hours=1),
    )
    job_id = schedule(data)

    # Ждём, пока джоба выполнится (date-триггер, ~200мс)
    import time
    deadline = time.time() + 3
    while time.time() < deadline and not calls:
        time.sleep(0.05)

    assert len(calls) == 1
    assert calls[0]["user_id"] == data.user_id
    assert fresh_scheduler.get_job(job_id) is None  # выполнена → удалена