
def _valid_payload(**overrides) -> dict:
    base = {
        "type": "meeting",
        "date_notify": "2099-01-01T09:45:00Z",
        "user_id": 123,
        "title": "Созвон по проекту",
        "date": "2099-01-01T10:00:00Z",
    }
    base.update(overrides)
    return base


def test_create_notification_success(client):
    response = client.post("/notifications", json=_valid_payload())
    assert response.status_code == 201
    job_id = response.json()["job_id"]
    assert job_id.startswith("notify_123_")


def test_create_notification_is_idempotent(client):
    payload = _valid_payload()
    first = client.post("/notifications", json=payload).json()["job_id"]
    second = client.post("/notifications", json=payload).json()["job_id"]
    assert first == second


def test_rejects_date_notify_in_past(client):
    response = client.post("/notifications", json=_valid_payload(
        date_notify="2000-01-01T00:00:00Z",
        date="2000-01-01T00:00:01Z",
    ))
    assert response.status_code == 422
    assert "date_notify must be in the future" in str(response.json())


def test_rejects_date_notify_after_event(client):
    response = client.post("/notifications", json=_valid_payload(
        date_notify="2099-01-01T10:30:00Z",
        date="2099-01-01T10:00:00Z",
    ))
    assert response.status_code == 422
    assert "cannot be later than date" in str(response.json())


def test_rejects_unknown_type(client):
    response = client.post("/notifications", json=_valid_payload(type="reminder"))
    assert response.status_code == 422


def test_rejects_missing_user_id(client):
    payload = _valid_payload()
    payload.pop("user_id")
    response = client.post("/notifications", json=payload)
    assert response.status_code == 422