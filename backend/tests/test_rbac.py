"""RBAC ownership-scoping tests.

Proves that a regular user gets 404 on entities owned by a different user,
while the same entity is visible to a super-admin.
"""
import uuid
import pytest
from fastapi.testclient import TestClient
from app.database.core import SessionLocal
from app.models.user import User
from app.models.leads import Lead
from app.models.deal import Deal
from app.models.call import Call, CallDirection, CallStatus
from app.models.calendar_event import CalendarEvent, EventStatus, EventTrigger
from app.services.auth_service import hash_password
from datetime import datetime, timezone

AUTH = "/api/v1/auth"


def _make_user(email, superuser=False):
    with SessionLocal() as db:
        u = User(email=email, hashed_password=hash_password("Test@1234"),
                 is_superuser=superuser, is_active=True)
        db.add(u)
        db.commit()
        db.refresh(u)
        return u.id


def _login(client, email):
    client.cookies.clear()
    r = client.post(f"{AUTH}/login", json={"email": email, "password": "Test@1234"})
    client.cookies.clear()
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="module")
def actors(client: TestClient):
    suffix = uuid.uuid4().hex[:6]
    admin_id = _make_user(f"rbac_admin_{suffix}@rdltest.com", superuser=True)
    user_a_id = _make_user(f"rbac_a_{suffix}@rdltest.com")
    user_b_id = _make_user(f"rbac_b_{suffix}@rdltest.com")

    admin_h = _login(client, f"rbac_admin_{suffix}@rdltest.com")
    user_a_h = _login(client, f"rbac_a_{suffix}@rdltest.com")
    user_b_h = _login(client, f"rbac_b_{suffix}@rdltest.com")

    # Create entities owned by user_a via the DB directly
    lead_id = deal_id = call_id = cal_id = None
    with SessionLocal() as db:
        lead = Lead(owner_id=user_a_id, name="RBAC Test Lead",
                    email=f"cust_{suffix}@test.com")
        db.add(lead)
        db.flush()
        lead_id = lead.id

        from app.models.company import Company
        co = Company(name=f"RBAC Co {suffix}", industry="Test")
        db.add(co); db.flush()
        deal = Deal(owner_id=user_a_id, company_id=co.id, deal_name="RBAC Deal",
                    deal_value=1000, stage="New")
        db.add(deal)
        db.flush()
        deal_id = deal.id

        call = Call(owner_id=user_a_id, direction=CallDirection.INBOUND,
                    status=CallStatus.NEW)
        db.add(call)
        db.flush()
        call_id = call.id

        cal = CalendarEvent(
            owner_id=user_a_id, title="RBAC Meeting",
            attendee_email=f"att_{suffix}@test.com",
            start_time=datetime(2030, 1, 1, 10, tzinfo=timezone.utc),
            end_time=datetime(2030, 1, 1, 11, tzinfo=timezone.utc),
            trigger=EventTrigger.MANUAL, status=EventStatus.SCHEDULED,
        )
        db.add(cal)
        db.commit()
        cal_id = cal.id

    yield {
        "admin": admin_h, "user_a": user_a_h, "user_b": user_b_h,
        "lead_id": lead_id, "deal_id": deal_id,
        "call_id": call_id, "cal_id": cal_id,
    }


# ── Leads ─────────────────────────────────────────────────────────────────────

def test_lead_user_b_gets_404(client, actors):
    r = client.get(f"/api/v1/leads/{actors['lead_id']}", headers=actors["user_b"])
    assert r.status_code == 404

def test_lead_user_a_gets_200(client, actors):
    r = client.get(f"/api/v1/leads/{actors['lead_id']}", headers=actors["user_a"])
    assert r.status_code == 200

def test_lead_admin_gets_200(client, actors):
    r = client.get(f"/api/v1/leads/{actors['lead_id']}", headers=actors["admin"])
    assert r.status_code == 200

def test_lead_list_user_b_empty(client, actors):
    r = client.get("/api/v1/leads/", headers=actors["user_b"])
    assert r.status_code == 200
    ids = [i["id"] for i in r.json()["items"]]
    assert str(actors["lead_id"]) not in ids

def test_lead_list_admin_sees_all(client, actors):
    r = client.get("/api/v1/leads/", headers=actors["admin"])
    assert r.status_code == 200
    ids = [i["id"] for i in r.json()["items"]]
    assert str(actors["lead_id"]) in ids


# ── Deals ─────────────────────────────────────────────────────────────────────

def test_deal_user_b_gets_404(client, actors):
    r = client.get(f"/api/v1/deals/{actors['deal_id']}", headers=actors["user_b"])
    assert r.status_code == 404

def test_deal_user_a_gets_200(client, actors):
    r = client.get(f"/api/v1/deals/{actors['deal_id']}", headers=actors["user_a"])
    assert r.status_code == 200

def test_deal_admin_gets_200(client, actors):
    r = client.get(f"/api/v1/deals/{actors['deal_id']}", headers=actors["admin"])
    assert r.status_code == 200


# ── Calls ─────────────────────────────────────────────────────────────────────

def test_call_user_b_gets_404(client, actors):
    r = client.get(f"/api/v1/calls/{actors['call_id']}", headers=actors["user_b"])
    assert r.status_code == 404

def test_call_user_a_gets_200(client, actors):
    r = client.get(f"/api/v1/calls/{actors['call_id']}", headers=actors["user_a"])
    assert r.status_code == 200

def test_call_admin_gets_200(client, actors):
    r = client.get(f"/api/v1/calls/{actors['call_id']}", headers=actors["admin"])
    assert r.status_code == 200


# ── Calendar ──────────────────────────────────────────────────────────────────

def test_calendar_user_b_gets_404(client, actors):
    r = client.get(f"/api/v1/calendar/{actors['cal_id']}", headers=actors["user_b"])
    assert r.status_code == 404

def test_calendar_user_a_gets_200(client, actors):
    r = client.get(f"/api/v1/calendar/{actors['cal_id']}", headers=actors["user_a"])
    assert r.status_code == 200

def test_calendar_admin_gets_200(client, actors):
    r = client.get(f"/api/v1/calendar/{actors['cal_id']}", headers=actors["admin"])
    assert r.status_code == 200


# ── Users router — scoping on the management endpoints ───────────────────────

def test_user_mgmt_list_forbidden_for_regular(client, actors):
    r = client.get("/api/v1/users", headers=actors["user_a"])
    assert r.status_code == 403

def test_user_mgmt_list_allowed_for_admin(client, actors):
    r = client.get("/api/v1/users", headers=actors["admin"])
    assert r.status_code == 200
