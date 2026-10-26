import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi.testclient import TestClient

import app.scheduler
from app.main import app as fastapi_app


@pytest.fixture(autouse=True)
def _isolated_global_scheduler(monkeypatch):
    test_scheduler = BackgroundScheduler(
        jobstores={"default": MemoryJobStore()},
        timezone="UTC",
    )
    monkeypatch.setattr(app.scheduler, "scheduler", test_scheduler)
    yield test_scheduler
    if test_scheduler.running:
        test_scheduler.shutdown(wait=False)


@pytest.fixture
def fresh_scheduler(_isolated_global_scheduler):
    _isolated_global_scheduler.start()
    return _isolated_global_scheduler


@pytest.fixture
def client():
    with TestClient(fastapi_app) as c:                # ← fastapi_app
        yield c