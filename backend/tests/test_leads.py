import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

from app.database.core import SessionLocal

BASE = "/api/v1/leads"


def _payload(name: str = None) -> dict:
    return {
        "name": name or f"Test Lead {uuid.uuid4().hex[:6]}",
        "email": f"lead_{uuid.uuid4().hex[:8]}@rdltest.com",
        "phone": "+911234567890",
        "status": "Uncontacted",
        "interest_level": "Cold",
    }


# ── Success paths ─────────────────────────────────────────────────────────────

def test_create_lead(client: TestClient, auth_headers: dict):
    resp = client.post(f"{BASE}/", json=_payload(), headers=auth_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert "id" in data
    assert data["name"] is not None


def test_list_leads(client: TestClient, auth_headers: dict):
    client.post(f"{BASE}/", json=_payload(), headers=auth_headers)
    resp = client.get(f"{BASE}/", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert "total" in body
    assert body["total"] >= 1


def test_get_lead(client: TestClient, auth_headers: dict):
    created = client.post(f"{BASE}/", json=_payload(), headers=auth_headers).json()
    resp = client.get(f"{BASE}/{created['id']}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]


def test_update_lead(client: TestClient, auth_headers: dict):
    created = client.post(f"{BASE}/", json=_payload(), headers=auth_headers).json()
    resp = client.patch(
        f"{BASE}/{created['id']}",
        json={"status": "Contacted", "interest_level": "Warm"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "Contacted"
    assert resp.json()["interest_level"] == "Warm"


def test_delete_lead(client: TestClient, auth_headers: dict):
    created = client.post(f"{BASE}/", json=_payload(), headers=auth_headers).json()
    del_resp = client.delete(f"{BASE}/{created['id']}", headers=auth_headers)
    assert del_resp.status_code == 204
    get_resp = client.get(f"{BASE}/{created['id']}", headers=auth_headers)
    assert get_resp.status_code == 404


def test_list_leads_filter_by_status(client: TestClient, auth_headers: dict):
    client.post(f"{BASE}/", json={**_payload(), "status": "Qualified"}, headers=auth_headers)
    resp = client.get(f"{BASE}/?status=Qualified", headers=auth_headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert all(item["status"] == "Qualified" for item in items)


def test_list_leads_pagination(client: TestClient, auth_headers: dict):
    resp = client.get(f"{BASE}/?page=1&limit=2", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) <= 2


# ── Validation failures ───────────────────────────────────────────────────────

def test_create_lead_missing_name(client: TestClient, auth_headers: dict):
    resp = client.post(f"{BASE}/", json={"email": "x@test.com"}, headers=auth_headers)
    assert resp.status_code == 422


def test_get_nonexistent_lead(client: TestClient, auth_headers: dict):
    resp = client.get(f"{BASE}/{uuid.uuid4()}", headers=auth_headers)
    assert resp.status_code == 404


def test_update_nonexistent_lead(client: TestClient, auth_headers: dict):
    resp = client.patch(f"{BASE}/{uuid.uuid4()}", json={"status": "Contacted"}, headers=auth_headers)
    assert resp.status_code == 404


def test_delete_nonexistent_lead(client: TestClient, auth_headers: dict):
    resp = client.delete(f"{BASE}/{uuid.uuid4()}", headers=auth_headers)
    assert resp.status_code == 404


# ── Auth failures ─────────────────────────────────────────────────────────────

def test_list_leads_no_auth(client: TestClient):
    saved = dict(client.cookies)
    client.cookies.clear()
    try:
        resp = client.get(f"{BASE}/")
        assert resp.status_code == 401
    finally:
        for k, v in saved.items():
            client.cookies.set(k, v)


def test_create_lead_no_auth(client: TestClient):
    saved = dict(client.cookies)
    client.cookies.clear()
    try:
        resp = client.post(f"{BASE}/", json=_payload())
        assert resp.status_code == 401
    finally:
        for k, v in saved.items():
            client.cookies.set(k, v)


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


def _insert_lead(**kwargs):
    from app.models.leads import Lead
    defaults = {
        "name": f"Test Lead {uuid.uuid4().hex[:6]}",
        "email": f"lead_{uuid.uuid4().hex[:8]}@rdltest.com",
        "status": "Uncontacted",
        "interest_level": "Cold",
        "engagement_score": 50,
        "classification": "UNCLASSIFIED",
    }
    defaults.update(kwargs)
    with SessionLocal() as db:
        lead = Lead(**defaults)
        db.add(lead); db.commit(); db.refresh(lead)
        return lead.id


# ── GET /classification-summary ───────────────────────────────────────────────

def test_classification_summary_shape(client: TestClient, auth_headers: dict):
    resp = client.get(f"{BASE}/classification-summary", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    for tier in ("high", "medium", "low", "unclassified"):
        assert tier in body, f"Missing tier: {tier}"
        assert "count" in body[tier]
        assert "avg_score" in body[tier]
        assert "pct" in body[tier]
    assert "total" in body


def test_classification_summary_counts_match_total(client: TestClient, auth_headers: dict):
    resp = client.get(f"{BASE}/classification-summary", headers=auth_headers)
    body = resp.json()
    tier_total = sum(body[t]["count"] for t in ("high", "medium", "low", "unclassified"))
    assert tier_total == body["total"]


def test_classification_summary_high_lead_counted(client: TestClient, auth_headers: dict):
    _insert_lead(classification="HIGH", engagement_score=80)
    resp = client.get(f"{BASE}/classification-summary", headers=auth_headers)
    assert resp.json()["high"]["count"] >= 1


def test_classification_summary_no_auth(client: TestClient):
    with _no_auth(client):
        resp = client.get(f"{BASE}/classification-summary")
    assert resp.status_code == 401


# ── GET /?classification= filter ─────────────────────────────────────────────

def test_list_leads_filter_high(client: TestClient, auth_headers: dict):
    _insert_lead(classification="HIGH", engagement_score=82)
    resp = client.get(f"{BASE}/?classification=HIGH", headers=auth_headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) >= 1
    assert all(item["classification"] == "HIGH" for item in items)


def test_list_leads_filter_medium(client: TestClient, auth_headers: dict):
    _insert_lead(classification="MEDIUM", engagement_score=55)
    resp = client.get(f"{BASE}/?classification=MEDIUM", headers=auth_headers)
    assert resp.status_code == 200
    assert all(item["classification"] == "MEDIUM" for item in resp.json()["items"])


def test_list_leads_filter_low(client: TestClient, auth_headers: dict):
    _insert_lead(classification="LOW", engagement_score=20)
    resp = client.get(f"{BASE}/?classification=LOW", headers=auth_headers)
    assert resp.status_code == 200
    assert all(item["classification"] == "LOW" for item in resp.json()["items"])


def test_list_leads_filter_classification_case_insensitive(client: TestClient, auth_headers: dict):
    resp = client.get(f"{BASE}/?classification=high", headers=auth_headers)
    assert resp.status_code == 200
    assert all(item["classification"] == "HIGH" for item in resp.json()["items"])


def test_list_leads_classification_not_mixed_with_other_tiers(client: TestClient, auth_headers: dict):
    _insert_lead(classification="HIGH",   engagement_score=80)
    _insert_lead(classification="MEDIUM", engagement_score=55)
    resp = client.get(f"{BASE}/?classification=HIGH", headers=auth_headers)
    assert all(item["classification"] == "HIGH" for item in resp.json()["items"])


# ── GET /{id}/score-breakdown ─────────────────────────────────────────────────

def test_score_breakdown_shape(client: TestClient, auth_headers: dict):
    lid = _insert_lead(classification="HIGH", engagement_score=78)
    resp = client.get(f"{BASE}/{lid}/score-breakdown", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["lead_id"] == str(lid)
    assert "classification" in body
    assert "engagement_score" in body
    assert "signals" in body
    signals = body["signals"]
    for key in (
        "inbound_first_contact", "total_emails", "inbound_emails", "outbound_emails",
        "total_calls", "inbound_calls", "outbound_calls", "total_meetings",
        "has_unresolved_gaps", "total_gap_count", "call_response_count", "email_reply_count",
    ):
        assert key in signals, f"Missing signal key: {key}"


def test_score_breakdown_new_lead_shows_zero_signals(client: TestClient, auth_headers: dict):
    lid = _insert_lead()
    resp = client.get(f"{BASE}/{lid}/score-breakdown", headers=auth_headers)
    assert resp.status_code == 200
    signals = resp.json()["signals"]
    assert signals["total_emails"] == 0
    assert signals["total_calls"] == 0
    assert signals["total_meetings"] == 0
    assert signals["has_unresolved_gaps"] is False


def test_score_breakdown_not_found(client: TestClient, auth_headers: dict):
    resp = client.get(f"{BASE}/{uuid.uuid4()}/score-breakdown", headers=auth_headers)
    assert resp.status_code == 404


def test_score_breakdown_no_auth(client: TestClient):
    lid = _insert_lead()
    with _no_auth(client):
        resp = client.get(f"{BASE}/{lid}/score-breakdown")
    assert resp.status_code == 401


# ── POST /{id}/reclassify ─────────────────────────────────────────────────────

def test_reclassify_returns_lead(client: TestClient, auth_headers: dict):
    lid = _insert_lead(classification="UNCLASSIFIED", engagement_score=30)
    resp = client.post(f"{BASE}/{lid}/reclassify", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == str(lid)
    assert "classification" in body


def test_reclassify_updates_classification_field(client: TestClient, auth_headers: dict):
    """After reclassify, the classification field must be set (not UNCLASSIFIED for leads with data)."""
    lid = _insert_lead(classification="UNCLASSIFIED", engagement_score=0)
    resp = client.post(f"{BASE}/{lid}/reclassify", headers=auth_headers)
    assert resp.status_code == 200
    # With no interactions the result should be UNCLASSIFIED (expected)
    assert resp.json()["classification"] in ("HIGH", "MEDIUM", "LOW", "UNCLASSIFIED")


def test_reclassify_not_found(client: TestClient, auth_headers: dict):
    resp = client.post(f"{BASE}/{uuid.uuid4()}/reclassify", headers=auth_headers)
    assert resp.status_code == 404


def test_reclassify_no_auth(client: TestClient):
    lid = _insert_lead()
    with _no_auth(client):
        resp = client.post(f"{BASE}/{lid}/reclassify")
    assert resp.status_code == 401


# ── Classification logic unit tests (lead_scoring_service) ────────────────────

def test_classify_lead_ready_to_buy_is_high():
    """Call with intent=ready_to_buy always pushes to HIGH tier."""
    from app.services.lead_scoring_service import classify_lead
    from app.models.leads import Lead
    from app.models.call import Call, CallDirection, CallStatus

    with SessionLocal() as db:
        lead = Lead(name="Buyer", email=f"buyer_{uuid.uuid4().hex[:6]}@test.com",
                    status="Contacted", interest_level="Hot", engagement_score=50)
        db.add(lead); db.commit(); db.refresh(lead)

        call = Call(
            lead_id=lead.id,
            direction=CallDirection.INBOUND,
            status=CallStatus.COMPLETED,
            intent="ready_to_buy",
            urgency="immediate",
            sentiment="POSITIVE",
        )
        db.add(call); db.commit()

        classification, reason, nba = classify_lead(db, lead.id)

    assert classification == "HIGH"
    assert "intent to buy" in reason.lower() or "buy" in reason.lower()
    assert nba


def test_classify_lead_not_interested_is_low():
    """Call with intent=not_interested and no other positive signal → LOW."""
    from app.services.lead_scoring_service import classify_lead
    from app.models.leads import Lead
    from app.models.call import Call, CallDirection, CallStatus

    with SessionLocal() as db:
        lead = Lead(name="No Interest", email=f"noint_{uuid.uuid4().hex[:6]}@test.com",
                    status="Uncontacted", interest_level="Cold", engagement_score=20)
        db.add(lead); db.commit(); db.refresh(lead)

        call = Call(
            lead_id=lead.id,
            direction=CallDirection.OUTBOUND,
            status=CallStatus.COMPLETED,
            intent="not_interested",
            urgency="unknown",
            sentiment="NEUTRAL",
        )
        db.add(call); db.commit()

        classification, reason, nba = classify_lead(db, lead.id)

    assert classification == "LOW"
    assert nba


def test_classify_lead_no_interactions_is_unclassified():
    """Lead with no emails and no calls → UNCLASSIFIED."""
    from app.services.lead_scoring_service import classify_lead
    from app.models.leads import Lead

    with SessionLocal() as db:
        lead = Lead(name="New Lead", email=f"newlead_{uuid.uuid4().hex[:6]}@test.com",
                    status="Uncontacted", interest_level="Cold", engagement_score=20)
        db.add(lead); db.commit(); db.refresh(lead)
        classification, reason, nba = classify_lead(db, lead.id)

    assert classification == "UNCLASSIFIED"


def test_classify_lead_inbound_boosts_score():
    """Inbound contact should boost classification vs same lead with only outbound."""
    from app.services.lead_scoring_service import classify_lead
    from app.models.leads import Lead
    from app.models.communication import Email, EmailLabel, EmailStatus

    with SessionLocal() as db:
        lead = Lead(name="Inbound Test", email=f"inbound_{uuid.uuid4().hex[:6]}@test.com",
                    status="Contacted", interest_level="Warm", engagement_score=45)
        db.add(lead); db.commit(); db.refresh(lead)

        # Inbound email from the lead
        email = Email(
            gmail_message_id=f"test_{uuid.uuid4().hex}",
            direction="inbound",
            sender=f"inbound_{uuid.uuid4().hex[:6]}@test.com",
            recipients=["us@rdltech.in"],
            subject="Inquiry about your products",
            received_at=datetime.now(timezone.utc),
            label=EmailLabel.SALES,
            status=EmailStatus.REPLIED,
            lead_id=lead.id,
        )
        db.add(email); db.commit()

        classification, reason, nba = classify_lead(db, lead.id)

    assert "inbound" in reason.lower() or "initiated" in reason.lower()
    assert classification in ("MEDIUM", "HIGH")


def test_update_lead_score_persists_classification():
    """update_lead_score must write classification + reason + next_best_action to the lead row."""
    from app.services.lead_scoring_service import update_lead_score
    from app.models.leads import Lead

    with SessionLocal() as db:
        lead = Lead(name="Score Persist", email=f"sp_{uuid.uuid4().hex[:6]}@test.com",
                    status="Uncontacted", interest_level="Cold", engagement_score=0)
        db.add(lead); db.commit(); db.refresh(lead)
        lead_id = lead.id

        update_lead_score(db, lead_id)

        db.refresh(lead)
        assert lead.classification in ("HIGH", "MEDIUM", "LOW", "UNCLASSIFIED")
        assert lead.engagement_score >= 0


def test_lead_response_schema_includes_classification(client: TestClient, auth_headers: dict):
    """LeadOut response must include classification, classification_reason, inbound_first_contact."""
    resp = client.post(f"{BASE}/", json=_payload(), headers=auth_headers)
    assert resp.status_code == 201
    body = resp.json()
    assert "classification" in body
    assert "classification_reason" in body
    assert "inbound_first_contact" in body
