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
