import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

BASE = "/api/v1/calendar"


def _future_time(hours: int = 48) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()


# ── List / Get ────────────────────────────────────────────────────────────────

def test_list_events_empty(client: TestClient, auth_headers: dict):
    resp = client.get(f"{BASE}/", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert "total" in body


def test_list_events_filter_by_status(client: TestClient, auth_headers: dict):
    resp = client.get(f"{BASE}/?status=scheduled", headers=auth_headers)
    assert resp.status_code == 200
    for item in resp.json()["items"]:
        assert item["status"] == "scheduled"


def test_list_events_filter_by_trigger(client: TestClient, auth_headers: dict):
    resp = client.get(f"{BASE}/?trigger=manual", headers=auth_headers)
    assert resp.status_code == 200


def test_list_events_pagination(client: TestClient, auth_headers: dict):
    resp = client.get(f"{BASE}/?page=1&limit=5", headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()["items"]) <= 5


def test_get_nonexistent_event(client: TestClient, auth_headers: dict):
    resp = client.get(f"{BASE}/{uuid.uuid4()}", headers=auth_headers)
    assert resp.status_code == 404


def test_cancel_nonexistent_event(client: TestClient, auth_headers: dict):
    resp = client.delete(f"{BASE}/{uuid.uuid4()}", headers=auth_headers)
    assert resp.status_code == 404


# ── Schedule ──────────────────────────────────────────────────────────────────

def test_schedule_meeting_success(client: TestClient, auth_headers: dict):
    mock_event = MagicMock()
    mock_event.id = uuid.uuid4()
    mock_event.google_event_id = "google_123"
    mock_event.lead_id = None
    mock_event.deal_id = None
    mock_event.title = "Test Meeting"
    mock_event.description = "Test"
    mock_event.attendee_email = "test@example.com"
    mock_event.start_time = datetime.now(timezone.utc) + timedelta(hours=48)
    mock_event.end_time = datetime.now(timezone.utc) + timedelta(hours=48, minutes=30)
    mock_event.meet_link = "https://meet.google.com/abc-defg-hij"
    mock_event.calendar_link = "https://calendar.google.com/event?eid=xyz"
    mock_event.trigger = "manual"
    mock_event.status = "scheduled"
    mock_event.invite_email_sent = True
    mock_event.created_at = datetime.now(timezone.utc)
    mock_event.owner_email = None

    with patch("app.routers.calendar.create_meeting", return_value=mock_event):
        resp = client.post(
            f"{BASE}/schedule",
            json={
                "attendee_email": "test@example.com",
                "title": "Test Meeting",
                "description": "Discussing product inquiry",
                "start_time": _future_time(48),
                "duration_minutes": 30,
            },
            headers=auth_headers,
        )
    assert resp.status_code == 201


def test_schedule_meeting_invalid_duration(client: TestClient, auth_headers: dict):
    resp = client.post(
        f"{BASE}/schedule",
        json={
            "attendee_email": "test@example.com",
            "title": "Test",
            "start_time": _future_time(48),
            "duration_minutes": 5,  # below 15 min minimum
        },
        headers=auth_headers,
    )
    assert resp.status_code == 422


def test_schedule_meeting_missing_fields(client: TestClient, auth_headers: dict):
    resp = client.post(
        f"{BASE}/schedule",
        json={"title": "No email or time"},
        headers=auth_headers,
    )
    assert resp.status_code == 422


# ── Auth guards ───────────────────────────────────────────────────────────────

def test_list_events_no_auth(client: TestClient):
    saved = dict(client.cookies)
    client.cookies.clear()
    try:
        resp = client.get(f"{BASE}/")
        assert resp.status_code == 401
    finally:
        for k, v in saved.items():
            client.cookies.set(k, v)


def test_schedule_no_auth(client: TestClient):
    saved = dict(client.cookies)
    client.cookies.clear()
    try:
        resp = client.post(f"{BASE}/schedule", json={
            "attendee_email": "x@x.com",
            "title": "Test",
            "start_time": _future_time(48),
        })
        assert resp.status_code == 401
    finally:
        for k, v in saved.items():
            client.cookies.set(k, v)


# ── Deal signal unit tests ────────────────────────────────────────────────────

def test_evaluate_deal_signal_positive_stage():
    from app.services.deal_signal_service import evaluate_deal_signal
    from app.models.deal import Deal

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None  # no existing event

    deal = Deal(stage="Proposal", win_probability=40)
    deal.id = uuid.uuid4()
    assert evaluate_deal_signal(db, deal) is True


def test_evaluate_deal_signal_high_probability():
    from app.services.deal_signal_service import evaluate_deal_signal
    from app.models.deal import Deal

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None

    deal = Deal(stage="Prospect", win_probability=75)
    deal.id = uuid.uuid4()
    assert evaluate_deal_signal(db, deal) is True


def test_evaluate_deal_signal_negative():
    from app.services.deal_signal_service import evaluate_deal_signal
    from app.models.deal import Deal

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None

    deal = Deal(stage="Prospect", win_probability=20)
    deal.id = uuid.uuid4()
    assert evaluate_deal_signal(db, deal) is False


def test_evaluate_deal_signal_already_scheduled():
    from app.services.deal_signal_service import evaluate_deal_signal
    from app.models.deal import Deal

    db = MagicMock()
    # Simulate an existing scheduled event
    db.query.return_value.filter.return_value.first.return_value = MagicMock()

    deal = Deal(stage="Proposal", win_probability=80)
    deal.id = uuid.uuid4()
    assert evaluate_deal_signal(db, deal) is False


# ── RAG knowledge gap detection ───────────────────────────────────────────────

def test_is_knowledge_gap_detects_gap():
    from app.agents.tools.rag_chain import _is_knowledge_gap
    assert _is_knowledge_gap("I don't have specific information about that product.") is True
    assert _is_knowledge_gap("Please contact our sales team for more details.") is True
    assert _is_knowledge_gap("I am not sure about the exact specifications.") is True


def test_is_knowledge_gap_no_gap():
    from app.agents.tools.rag_chain import _is_knowledge_gap
    assert _is_knowledge_gap("The Industrial Cellular Router costs ₹45,000.") is False
    assert _is_knowledge_gap("The product includes a 12V power adapter and USB cable.") is False


# ── Operator availability ─────────────────────────────────────────────────────

def test_get_availability_returns_7_days(client: TestClient, auth_headers: dict):
    """Availability endpoint returns all 7 days of the week."""
    resp = client.get(f"{BASE}/availability", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 7
    days = [d["day_of_week"] for d in data]
    assert sorted(days) == list(range(7))


def test_get_availability_fields(client: TestClient, auth_headers: dict):
    """Each day has the required fields."""
    resp = client.get(f"{BASE}/availability", headers=auth_headers)
    assert resp.status_code == 200
    day = resp.json()[0]
    for field in ("day_of_week", "day_name", "is_available", "start_hour",
                  "start_minute", "end_hour", "end_minute"):
        assert field in day, f"Missing field: {field}"


def test_update_availability_day(client: TestClient, auth_headers: dict):
    """PUT /availability/{day} persists changes."""
    payload = {
        "is_available": True,
        "start_hour": 10,
        "start_minute": 0,
        "end_hour": 17,
        "end_minute": 0,
    }
    resp = client.put(f"{BASE}/availability/0", json=payload, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["start_hour"] == 10
    assert data["end_hour"] == 17
    assert data["day_name"] == "Monday"

    # Verify persisted — re-fetch
    fetch = client.get(f"{BASE}/availability", headers=auth_headers)
    monday = next(d for d in fetch.json() if d["day_of_week"] == 0)
    assert monday["start_hour"] == 10
    assert monday["end_hour"] == 17


def test_update_availability_toggle_off(client: TestClient, auth_headers: dict):
    """Setting is_available=False marks a day unavailable."""
    resp = client.put(f"{BASE}/availability/6", json={
        "is_available": False, "start_hour": 9, "start_minute": 0,
        "end_hour": 18, "end_minute": 0,
    }, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["is_available"] is False
    assert resp.json()["day_name"] == "Sunday"


def test_update_availability_invalid_day(client: TestClient, auth_headers: dict):
    """day_of_week out of 0–6 returns 422."""
    resp = client.put(f"{BASE}/availability/7", json={
        "is_available": True, "start_hour": 9, "start_minute": 0,
        "end_hour": 18, "end_minute": 0,
    }, headers=auth_headers)
    assert resp.status_code == 422


def test_availability_no_auth(client: TestClient):
    """Availability endpoints require authentication."""
    saved = dict(client.cookies)
    client.cookies.clear()
    try:
        assert client.get(f"{BASE}/availability").status_code == 401
        assert client.put(f"{BASE}/availability/0", json={
            "is_available": True, "start_hour": 9, "start_minute": 0,
            "end_hour": 18, "end_minute": 0,
        }).status_code == 401
    finally:
        for k, v in saved.items():
            client.cookies.set(k, v)


# ── Scheduling config ─────────────────────────────────────────────────────────

def test_get_scheduling_config(client: TestClient, auth_headers: dict):
    """GET /scheduling-config returns buffer and slot duration."""
    resp = client.get(f"{BASE}/scheduling-config", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    for field in ("buffer_minutes", "slot_duration_minutes", "max_meetings_per_day"):
        assert field in data


def test_update_scheduling_config(client: TestClient, auth_headers: dict):
    """PATCH /scheduling-config persists changes."""
    resp = client.patch(f"{BASE}/scheduling-config",
                        json={"buffer_minutes": 20, "slot_duration_minutes": 45},
                        headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["buffer_minutes"] == 20
    assert data["slot_duration_minutes"] == 45

    # Verify persisted
    fetch = client.get(f"{BASE}/scheduling-config", headers=auth_headers)
    assert fetch.json()["buffer_minutes"] == 20
    assert fetch.json()["slot_duration_minutes"] == 45


def test_update_scheduling_config_partial(client: TestClient, auth_headers: dict):
    """PATCH is partial — unset fields remain unchanged."""
    # Set a known baseline
    client.patch(f"{BASE}/scheduling-config",
                 json={"buffer_minutes": 15, "max_meetings_per_day": 8},
                 headers=auth_headers)
    # Update only max_meetings_per_day
    resp = client.patch(f"{BASE}/scheduling-config",
                        json={"max_meetings_per_day": 5},
                        headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["max_meetings_per_day"] == 5
    assert data["buffer_minutes"] == 15  # unchanged


def test_scheduling_config_no_auth(client: TestClient):
    """Scheduling config requires authentication."""
    saved = dict(client.cookies)
    client.cookies.clear()
    try:
        assert client.get(f"{BASE}/scheduling-config").status_code == 401
        assert client.patch(f"{BASE}/scheduling-config",
                            json={"buffer_minutes": 30}).status_code == 401
    finally:
        for k, v in saved.items():
            client.cookies.set(k, v)
