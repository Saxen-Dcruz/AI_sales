import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.database.core import SessionLocal
from app.models.call import Call, CallDirection, CallStatus, CallOutcome

BASE = "/api/v1/calls"


# ── Helpers ───────────────────────────────────────────────────────────────────

@contextmanager
def _no_auth(client: TestClient):
    saved = dict(client.cookies)
    client.cookies.clear()
    try:
        yield
    finally:
        for k, v in saved.items():
            client.cookies.set(k, v)


def _insert_call(**kwargs) -> uuid.UUID:
    defaults = {
        "direction": CallDirection.INBOUND,
        "status": CallStatus.NEW,
        "phone_number": "+919876543210",
        "started_at": datetime.now(timezone.utc),
        "duration_seconds": 0,
    }
    defaults.update(kwargs)
    with SessionLocal() as db:
        call = Call(**defaults)
        db.add(call)
        db.commit()
        db.refresh(call)
        return call.id


# ── Cleanup ───────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def clean_test_calls():
    def _purge():
        with SessionLocal() as db:
            db.execute(text("DELETE FROM calls WHERE phone_number LIKE '+91987%'"))
            db.commit()
    _purge()
    yield
    _purge()


# ── POST / ────────────────────────────────────────────────────────────────────

def test_log_inbound_call(client, auth_headers):
    resp = client.post(BASE + "/", json={
        "direction": "inbound",
        "phone_number": "+919876543210",
    }, headers=auth_headers)
    assert resp.status_code == 201
    body = resp.json()
    assert body["direction"] == "inbound"
    assert body["status"] == "new"
    assert body["phone_number"] == "+919876543210"
    assert body["handled_by"]  # defaults to current user email


def test_log_outbound_call(client, auth_headers):
    resp = client.post(BASE + "/", json={
        "direction": "outbound",
        "phone_number": "+919876543211",
    }, headers=auth_headers)
    assert resp.status_code == 201
    assert resp.json()["direction"] == "outbound"


def test_log_call_missing_direction(client, auth_headers):
    resp = client.post(BASE + "/", json={"phone_number": "+919876543210"}, headers=auth_headers)
    assert resp.status_code == 422


def test_log_call_no_auth(client):
    with _no_auth(client):
        resp = client.post(BASE + "/", json={"direction": "inbound"})
    assert resp.status_code == 401


# ── GET / ─────────────────────────────────────────────────────────────────────

def test_list_calls_returns_envelope(client, auth_headers):
    resp = client.get(BASE + "/", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    for key in ("items", "total", "page", "limit"):
        assert key in body


def test_list_calls_filter_direction(client, auth_headers):
    resp = client.get(BASE + "/?direction=inbound", headers=auth_headers)
    assert resp.status_code == 200
    for item in resp.json()["items"]:
        assert item["direction"] == "inbound"


def test_list_calls_filter_status(client, auth_headers):
    _insert_call(status=CallStatus.COMPLETED, direction=CallDirection.INBOUND)
    resp = client.get(BASE + "/?status=completed", headers=auth_headers)
    assert resp.status_code == 200
    for item in resp.json()["items"]:
        assert item["status"] == "completed"


def test_list_calls_pagination(client, auth_headers):
    resp = client.get(BASE + "/?limit=1&page=1", headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()["items"]) <= 1


def test_list_calls_limit_over_max(client, auth_headers):
    resp = client.get(BASE + "/?limit=101", headers=auth_headers)
    assert resp.status_code == 422


def test_list_calls_no_auth(client):
    with _no_auth(client):
        resp = client.get(BASE + "/")
    assert resp.status_code == 401


# ── GET /{id} ─────────────────────────────────────────────────────────────────

def test_get_call_found(client, auth_headers):
    cid = _insert_call(phone_number="+919876543212")
    resp = client.get(f"{BASE}/{cid}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == str(cid)
    assert resp.json()["phone_number"] == "+919876543212"


def test_get_call_not_found(client, auth_headers):
    resp = client.get(f"{BASE}/{uuid.uuid4()}", headers=auth_headers)
    assert resp.status_code == 404


def test_get_call_no_auth(client):
    cid = _insert_call()
    with _no_auth(client):
        resp = client.get(f"{BASE}/{cid}")
    assert resp.status_code == 401


# ── PATCH /{id} ───────────────────────────────────────────────────────────────

def test_update_call_status(client, auth_headers):
    cid = _insert_call(status=CallStatus.ACTIVE)
    resp = client.patch(f"{BASE}/{cid}", json={"status": "completed", "duration_seconds": 120}, headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "completed"
    assert body["duration_seconds"] == 120


def test_update_call_outcome(client, auth_headers):
    cid = _insert_call()
    resp = client.patch(f"{BASE}/{cid}", json={"outcome": "interested"}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["outcome"] == "interested"


def test_update_call_not_found(client, auth_headers):
    resp = client.patch(f"{BASE}/{uuid.uuid4()}", json={"status": "completed"}, headers=auth_headers)
    assert resp.status_code == 404


def test_update_call_no_auth(client):
    cid = _insert_call()
    with _no_auth(client):
        resp = client.patch(f"{BASE}/{cid}", json={"status": "completed"})
    assert resp.status_code == 401


# ── POST /{id}/transcript ─────────────────────────────────────────────────────

def test_submit_transcript_success(client, auth_headers):
    cid = _insert_call(status=CallStatus.ACTIVE)
    transcript = "Customer asked about the PIC Development Board pricing and lead time. Sales rep confirmed price and said lead time is 5 days."
    with (
        patch("app.services.call_service.fetch_rag_context", return_value="PIC Development Board price: Rs 11,439"),
        patch("app.services.call_service.detect_product", return_value=(str(uuid.uuid4()), "PIC Development Board")),
        patch("app.services.call_service._generate_call_summary", return_value=("Customer interested in PIC board. Price confirmed. Lead time discussed.", "POSITIVE", None)),
        patch("app.services.call_service.extract_structured_gaps", return_value=[]),
    ):
        resp = client.post(f"{BASE}/{cid}/transcript", json={"transcript": transcript}, headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["transcript"] == transcript
    assert body["status"] == "completed"
    assert body["sentiment"] == "POSITIVE"
    assert body["detected_product_name"] == "PIC Development Board"


def test_submit_transcript_with_gaps(client, auth_headers):
    cid = _insert_call(status=CallStatus.ACTIVE)
    transcript = "Customer asked about warranty and bulk pricing."
    gaps = [
        {"question": "What warranty do you provide?", "topic": "warranty", "product_name": "PIC Board", "product_id": None, "resolved": False, "answer": None, "resolved_by": None},
    ]
    with (
        patch("app.services.call_service.fetch_rag_context", return_value=""),
        patch("app.services.call_service.detect_product", return_value=(None, None)),
        patch("app.services.call_service._generate_call_summary", return_value=("Customer asked about warranty. Our team will confirm this.", "NEUTRAL", None)),
        patch("app.services.call_service.extract_structured_gaps", return_value=gaps),
    ):
        resp = client.post(f"{BASE}/{cid}/transcript", json={"transcript": transcript}, headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()["followup_gaps"]) == 1
    assert resp.json()["followup_gaps"][0]["topic"] == "warranty"


def test_submit_transcript_empty(client, auth_headers):
    cid = _insert_call()
    resp = client.post(f"{BASE}/{cid}/transcript", json={"transcript": "   "}, headers=auth_headers)
    assert resp.status_code == 422


def test_submit_transcript_not_found(client, auth_headers):
    resp = client.post(f"{BASE}/{uuid.uuid4()}/transcript", json={"transcript": "Test"}, headers=auth_headers)
    assert resp.status_code == 404


def test_submit_transcript_no_auth(client):
    cid = _insert_call()
    with _no_auth(client):
        resp = client.post(f"{BASE}/{cid}/transcript", json={"transcript": "Test"})
    assert resp.status_code == 401


# ── GET /gaps ─────────────────────────────────────────────────────────────────

def test_list_call_gaps_empty(client, auth_headers):
    resp = client.get(BASE + "/gaps", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert "total" in body


def test_list_call_gaps_returns_unresolved(client, auth_headers):
    gaps = [
        {"question": "What is the lead time?", "topic": "availability", "product_name": "PIC Board", "product_id": None, "resolved": False, "answer": None, "resolved_by": None},
    ]
    _insert_call(status=CallStatus.COMPLETED, followup_gaps=gaps)
    resp = client.get(BASE + "/gaps", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1


def test_list_call_gaps_no_auth(client):
    with _no_auth(client):
        resp = client.get(BASE + "/gaps")
    assert resp.status_code == 401


# ── POST /{id}/gaps/resolve ───────────────────────────────────────────────────

def test_resolve_call_gap_success(client, auth_headers):
    gaps = [
        {"question": "What is the warranty period?", "topic": "warranty", "product_name": "PIC Board", "product_id": None, "resolved": False, "answer": None, "resolved_by": None},
    ]
    cid = _insert_call(status=CallStatus.COMPLETED, followup_gaps=gaps)
    with patch("app.services.product_knowledge_service.add_entry", return_value=MagicMock()):
        resp = client.post(
            f"{BASE}/{cid}/gaps/resolve",
            json={"gap_index": 0, "answer": "1 year warranty from purchase date."},
            headers=auth_headers,
        )
    assert resp.status_code == 200
    gap = resp.json()["followup_gaps"][0]
    assert gap["resolved"] is True
    assert gap["answer"] == "1 year warranty from purchase date."


def test_resolve_call_gap_out_of_range(client, auth_headers):
    gaps = [{"question": "Q?", "topic": "general", "product_name": None, "product_id": None, "resolved": False, "answer": None, "resolved_by": None}]
    cid = _insert_call(status=CallStatus.COMPLETED, followup_gaps=gaps)
    resp = client.post(f"{BASE}/{cid}/gaps/resolve", json={"gap_index": 5, "answer": "Answer"}, headers=auth_headers)
    assert resp.status_code == 400


def test_resolve_call_gap_already_resolved(client, auth_headers):
    gaps = [{"question": "Q?", "topic": "general", "product_name": None, "product_id": None, "resolved": True, "answer": "Already", "resolved_by": "x@x.com"}]
    cid = _insert_call(status=CallStatus.COMPLETED, followup_gaps=gaps)
    resp = client.post(f"{BASE}/{cid}/gaps/resolve", json={"gap_index": 0, "answer": "New answer"}, headers=auth_headers)
    assert resp.status_code == 400


def test_resolve_call_gap_not_found(client, auth_headers):
    resp = client.post(f"{BASE}/{uuid.uuid4()}/gaps/resolve", json={"gap_index": 0, "answer": "X"}, headers=auth_headers)
    assert resp.status_code == 404


def test_resolve_call_gap_no_auth(client):
    cid = _insert_call()
    with _no_auth(client):
        resp = client.post(f"{BASE}/{cid}/gaps/resolve", json={"gap_index": 0, "answer": "X"})
    assert resp.status_code == 401


# ── call_service unit tests ───────────────────────────────────────────────────

def test_create_call_service():
    from app.services.call_service import create_call
    with SessionLocal() as db:
        call = create_call(db, direction=CallDirection.OUTBOUND, phone_number="+919876543299")
    assert call.direction == CallDirection.OUTBOUND
    assert call.status == CallStatus.NEW
    assert call.started_at is not None


def test_update_call_sets_ended_at_on_complete():
    from app.services.call_service import create_call, update_call
    with SessionLocal() as db:
        call = create_call(db, direction=CallDirection.INBOUND, phone_number="+919876543298")
        assert call.ended_at is None
        updated = update_call(db, call, status=CallStatus.COMPLETED)
    assert updated.status == CallStatus.COMPLETED
    assert updated.ended_at is not None


def test_process_transcript_detects_product_and_gaps():
    from app.services.call_service import create_call, process_transcript
    transcript = "Customer asked about the PIC Development Board lead time and pricing."
    with SessionLocal() as db:
        call = create_call(db, direction=CallDirection.INBOUND, phone_number="+919876543297")
        with (
            patch("app.services.call_service.fetch_rag_context", return_value="Price: Rs 11,439"),
            patch("app.services.call_service.detect_product", return_value=(str(uuid.uuid4()), "PIC Development Board")),
            patch("app.services.call_service._generate_call_summary", return_value=("Customer interested.", "POSITIVE", None)),
            patch("app.services.call_service.extract_structured_gaps", return_value=[]),
        ):
            result = process_transcript(db, call, transcript)
    assert result.transcript == transcript
    assert result.detected_product_name == "PIC Development Board"
    assert result.sentiment == "POSITIVE"
    assert result.status == CallStatus.COMPLETED


# ── GET /analytics ────────────────────────────────────────────────────────────

def test_analytics_returns_shape(client, auth_headers):
    resp = client.get(BASE + "/analytics", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    for key in ("total_calls", "by_direction", "by_status", "by_outcome",
                "by_sentiment", "by_intent", "avg_duration_seconds", "avg_duration_minutes"):
        assert key in body, f"missing key: {key}"


def test_analytics_total_increases_after_call(client, auth_headers):
    resp_before = client.get(BASE + "/analytics", headers=auth_headers)
    total_before = resp_before.json()["total_calls"]
    client.post(BASE + "/", json={"direction": "inbound", "phone_number": "+919876543250"}, headers=auth_headers)
    resp_after = client.get(BASE + "/analytics", headers=auth_headers)
    assert resp_after.json()["total_calls"] == total_before + 1


def test_analytics_direction_breakdown(client, auth_headers):
    client.post(BASE + "/", json={"direction": "inbound",  "phone_number": "+919876543251"}, headers=auth_headers)
    client.post(BASE + "/", json={"direction": "outbound", "phone_number": "+919876543252"}, headers=auth_headers)
    body = client.get(BASE + "/analytics", headers=auth_headers).json()
    assert body["by_direction"].get("inbound", 0) >= 1
    assert body["by_direction"].get("outbound", 0) >= 1


def test_analytics_no_auth(client):
    with _no_auth(client):
        resp = client.get(BASE + "/analytics")
    assert resp.status_code == 401


# ── Phone-based lead matching (#2 / #12) ─────────────────────────────────────

def test_create_call_auto_creates_lead_from_phone(client, auth_headers):
    """New phone number → stub lead auto-created, call.lead_id populated."""
    unique_phone = "+9198765" + str(uuid.uuid4().int)[:5]
    resp = client.post(BASE + "/", json={"direction": "inbound", "phone_number": unique_phone}, headers=auth_headers)
    assert resp.status_code == 201
    assert resp.json()["lead_id"] is not None


def test_create_call_reuses_lead_for_same_phone():
    """Two calls with the same phone number must share the same lead_id."""
    from app.services.call_service import create_call
    phone = "+919876543270"
    with SessionLocal() as db:
        c1 = create_call(db, CallDirection.INBOUND, phone_number=phone)
        c2 = create_call(db, CallDirection.INBOUND, phone_number=phone)
        lead_id_1 = c1.lead_id
        lead_id_2 = c2.lead_id
    assert lead_id_1 == lead_id_2


def test_create_call_no_phone_no_lead():
    """No phone and no lead_id → lead_id remains None."""
    from app.services.call_service import create_call
    with SessionLocal() as db:
        call = create_call(db, CallDirection.INBOUND, phone_number=None, lead_id=None)
    assert call.lead_id is None


def test_create_call_explicit_lead_id_not_overridden():
    """Explicit lead_id must not be overridden by phone matching."""
    from app.services.call_service import create_call
    from app.models.leads import Lead
    with SessionLocal() as db:
        lead = Lead(name="Explicit Lead", email=f"explicit_{uuid.uuid4().hex[:6]}@test.com",
                    status="Uncontacted", interest_level="Warm", engagement_score=10)
        db.add(lead); db.commit(); db.refresh(lead)
        explicit_lead_id = lead.id
        call = create_call(db, CallDirection.INBOUND, phone_number="+919876543271", lead_id=explicit_lead_id)
        assert str(call.lead_id) == str(explicit_lead_id)


# ── Structured extraction (#6) ────────────────────────────────────────────────

def test_transcript_extracts_structured_fields(client, auth_headers):
    """process_transcript sets intent / urgency / product_interest from LLM extraction."""
    cid = _insert_call(status=CallStatus.ACTIVE)
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = '{"intent": "ready_to_buy", "urgency": "immediate", "product_interest": "PIC Board"}'
    mock_client.models.generate_content.return_value = mock_resp

    with (
        patch("app.services.call_service.fetch_rag_context", return_value=""),
        patch("app.services.call_service.detect_product", return_value=(None, "PIC Board")),
        patch("app.services.call_service._generate_call_summary", return_value=("Summary.", "POSITIVE", mock_client)),
        patch("app.services.call_service.extract_structured_gaps", return_value=[]),
        patch("app.services.call_service._send_post_call_email"),
    ):
        resp = client.post(f"{BASE}/{cid}/transcript", json={"transcript": "I want to buy the PIC Board today."}, headers=auth_headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["intent"] == "ready_to_buy"
    assert body["urgency"] == "immediate"
    assert body["product_interest"] == "PIC Board"


def test_transcript_defaults_structured_fields_when_extraction_fails(client, auth_headers):
    """When genai client is None, defaults are applied without crashing."""
    cid = _insert_call(status=CallStatus.ACTIVE)
    with (
        patch("app.services.call_service.fetch_rag_context", return_value=""),
        patch("app.services.call_service.detect_product", return_value=(None, None)),
        patch("app.services.call_service._generate_call_summary", return_value=("Summary.", "NEUTRAL", None)),
        patch("app.services.call_service.extract_structured_gaps", return_value=[]),
    ):
        resp = client.post(f"{BASE}/{cid}/transcript", json={"transcript": "Brief call."}, headers=auth_headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["intent"] == "exploring"
    assert body["urgency"] == "unknown"


def test_transcript_structured_fields_in_response_schema(client, auth_headers):
    """CallOut schema exposes intent, urgency, product_interest."""
    cid = _insert_call(status=CallStatus.ACTIVE)
    with (
        patch("app.services.call_service.fetch_rag_context", return_value=""),
        patch("app.services.call_service.detect_product", return_value=(None, None)),
        patch("app.services.call_service._generate_call_summary", return_value=("S.", "NEUTRAL", None)),
        patch("app.services.call_service.extract_structured_gaps", return_value=[]),
    ):
        resp = client.post(f"{BASE}/{cid}/transcript", json={"transcript": "Test."}, headers=auth_headers)
    assert resp.status_code == 200
    for field in ("intent", "urgency", "product_interest"):
        assert field in resp.json()


# ── Post-call follow-up email (#4) ────────────────────────────────────────────

def test_post_call_email_sent_on_ready_to_buy():
    """Post-call email sent when intent is ready_to_buy and lead has an email."""
    from app.services.call_service import create_call, process_transcript
    from app.models.leads import Lead
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = '{"intent": "ready_to_buy", "urgency": "immediate", "product_interest": "PIC Board"}'
    mock_client.models.generate_content.return_value = mock_resp

    with SessionLocal() as db:
        lead = Lead(name="Buyer", email=f"buyer_{uuid.uuid4().hex[:6]}@test.com",
                    status="Uncontacted", interest_level="Warm", engagement_score=20)
        db.add(lead); db.flush()
        call = create_call(db, CallDirection.INBOUND, lead_id=lead.id)

        with (
            patch("app.services.call_service.fetch_rag_context", return_value=""),
            patch("app.services.call_service.detect_product", return_value=(None, "PIC Board")),
            patch("app.services.call_service._generate_call_summary", return_value=("Summary.", "POSITIVE", mock_client)),
            patch("app.services.call_service.extract_structured_gaps", return_value=[]),
            patch("app.services.call_service._send_post_call_email") as mock_email,
        ):
            process_transcript(db, call, "I want to buy the PIC Board now.")

    mock_email.assert_called_once()


def test_post_call_email_not_sent_on_not_interested():
    """Post-call email must NOT be sent when intent is not_interested."""
    from app.services.call_service import create_call, process_transcript
    from app.models.leads import Lead
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = '{"intent": "not_interested", "urgency": "unknown", "product_interest": null}'
    mock_client.models.generate_content.return_value = mock_resp

    with SessionLocal() as db:
        lead = Lead(name="No Interest", email=f"noint_{uuid.uuid4().hex[:6]}@test.com",
                    status="Uncontacted", interest_level="Cold", engagement_score=5)
        db.add(lead); db.flush()
        call = create_call(db, CallDirection.INBOUND, lead_id=lead.id)

        with (
            patch("app.services.call_service.fetch_rag_context", return_value=""),
            patch("app.services.call_service.detect_product", return_value=(None, None)),
            patch("app.services.call_service._generate_call_summary", return_value=("Summary.", "NEUTRAL", mock_client)),
            patch("app.services.call_service.extract_structured_gaps", return_value=[]),
            patch("app.services.call_service._send_post_call_email") as mock_email,
        ):
            process_transcript(db, call, "Not interested at this time.")

    mock_email.assert_not_called()


def test_post_call_email_not_sent_when_no_lead():
    """Post-call email must NOT crash or send when call has no lead."""
    from app.services.call_service import create_call, process_transcript
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = '{"intent": "ready_to_buy", "urgency": "immediate", "product_interest": null}'
    mock_client.models.generate_content.return_value = mock_resp

    with SessionLocal() as db:
        call = create_call(db, CallDirection.INBOUND, phone_number=None, lead_id=None)
        with (
            patch("app.services.call_service.fetch_rag_context", return_value=""),
            patch("app.services.call_service.detect_product", return_value=(None, None)),
            patch("app.services.call_service._generate_call_summary", return_value=("Summary.", "POSITIVE", mock_client)),
            patch("app.services.call_service.extract_structured_gaps", return_value=[]),
            patch("app.services.call_service._send_post_call_email") as mock_email,
        ):
            result = process_transcript(db, call, "I want to buy.")

    mock_email.assert_not_called()
    assert result.status == CallStatus.COMPLETED
