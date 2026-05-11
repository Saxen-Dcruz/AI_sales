import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
import app.services.deal_signal_service  # noqa: F401 — needed so patch target is importable

BASE_DEALS = "/api/v1/deals"
BASE_COMPANIES = "/api/v1/companies"


def _company_payload() -> dict:
    return {"name": f"Deal Co {uuid.uuid4().hex[:6]}", "industry": "Technology"}


def _deal_payload(company_id: str, name: str = None) -> dict:
    return {
        "deal_name": name or f"Test Deal {uuid.uuid4().hex[:6]}",
        "company_id": company_id,
        "deal_value": 150000.00,
        "stage": "Prospect",
        "win_probability": 20,
    }


@pytest.fixture(scope="module")
def company_id(client: TestClient, auth_headers: dict) -> str:
    """Create one company per module — all deal tests share it."""
    resp = client.post(f"{BASE_COMPANIES}/", json=_company_payload(), headers=auth_headers)
    assert resp.status_code == 201
    return resp.json()["id"]


# ── Success paths ─────────────────────────────────────────────────────────────

def test_create_deal(client: TestClient, auth_headers: dict, company_id: str):
    resp = client.post(f"{BASE_DEALS}/", json=_deal_payload(company_id), headers=auth_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert "id" in data
    assert data["stage"] == "Prospect"


def test_list_deals(client: TestClient, auth_headers: dict, company_id: str):
    client.post(f"{BASE_DEALS}/", json=_deal_payload(company_id), headers=auth_headers)
    resp = client.get(f"{BASE_DEALS}/", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert "total" in body
    assert body["total"] >= 1


def test_get_deal(client: TestClient, auth_headers: dict, company_id: str):
    created = client.post(f"{BASE_DEALS}/", json=_deal_payload(company_id), headers=auth_headers).json()
    resp = client.get(f"{BASE_DEALS}/{created['id']}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]


def test_update_deal(client: TestClient, auth_headers: dict, company_id: str):
    created = client.post(f"{BASE_DEALS}/", json=_deal_payload(company_id), headers=auth_headers).json()
    resp = client.patch(
        f"{BASE_DEALS}/{created['id']}",
        json={"stage": "Proposal", "win_probability": 60},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["stage"] == "Proposal"
    assert float(resp.json()["win_probability"]) == 60.0


def test_delete_deal(client: TestClient, auth_headers: dict, company_id: str):
    created = client.post(f"{BASE_DEALS}/", json=_deal_payload(company_id), headers=auth_headers).json()
    del_resp = client.delete(f"{BASE_DEALS}/{created['id']}", headers=auth_headers)
    assert del_resp.status_code == 204
    get_resp = client.get(f"{BASE_DEALS}/{created['id']}", headers=auth_headers)
    assert get_resp.status_code == 404


def test_list_deals_filter_by_stage(client: TestClient, auth_headers: dict, company_id: str):
    client.post(f"{BASE_DEALS}/", json={**_deal_payload(company_id), "stage": "Closed Won"}, headers=auth_headers)
    resp = client.get(f"{BASE_DEALS}/?stage=Closed+Won", headers=auth_headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert all(item["stage"] == "Closed Won" for item in items)


def test_list_deals_filter_by_company(client: TestClient, auth_headers: dict, company_id: str):
    resp = client.get(f"{BASE_DEALS}/?company_id={company_id}", headers=auth_headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert all(item["company_id"] == company_id for item in items)


def test_list_deals_pagination(client: TestClient, auth_headers: dict):
    resp = client.get(f"{BASE_DEALS}/?page=1&limit=2", headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()["items"]) <= 2


# ── Validation failures ───────────────────────────────────────────────────────

def test_create_deal_missing_required(client: TestClient, auth_headers: dict):
    resp = client.post(f"{BASE_DEALS}/", json={"deal_name": "No Company"}, headers=auth_headers)
    assert resp.status_code == 422


def test_create_deal_invalid_company_id(client: TestClient, auth_headers: dict):
    resp = client.post(
        f"{BASE_DEALS}/",
        json=_deal_payload(str(uuid.uuid4())),
        headers=auth_headers,
    )
    assert resp.status_code == 404


def test_get_nonexistent_deal(client: TestClient, auth_headers: dict):
    resp = client.get(f"{BASE_DEALS}/{uuid.uuid4()}", headers=auth_headers)
    assert resp.status_code == 404


def test_update_nonexistent_deal(client: TestClient, auth_headers: dict):
    resp = client.patch(f"{BASE_DEALS}/{uuid.uuid4()}", json={"stage": "Proposal"}, headers=auth_headers)
    assert resp.status_code == 404


def test_delete_nonexistent_deal(client: TestClient, auth_headers: dict):
    resp = client.delete(f"{BASE_DEALS}/{uuid.uuid4()}", headers=auth_headers)
    assert resp.status_code == 404


# ── Auth failures ─────────────────────────────────────────────────────────────

def test_list_deals_no_auth(client: TestClient):
    saved = dict(client.cookies)
    client.cookies.clear()
    try:
        resp = client.get(f"{BASE_DEALS}/")
        assert resp.status_code == 401
    finally:
        for k, v in saved.items():
            client.cookies.set(k, v)


def test_create_deal_no_auth(client: TestClient, company_id: str):
    saved = dict(client.cookies)
    client.cookies.clear()
    try:
        resp = client.post(f"{BASE_DEALS}/", json=_deal_payload(company_id))
        assert resp.status_code == 401
    finally:
        for k, v in saved.items():
            client.cookies.set(k, v)


# ── GET /?at_risk=true (#11) ──────────────────────────────────────────────────

def _no_auth(client):
    from contextlib import contextmanager
    @contextmanager
    def _ctx():
        saved = dict(client.cookies)
        client.cookies.clear()
        try:
            yield
        finally:
            for k, v in saved.items():
                client.cookies.set(k, v)
    return _ctx()


def _insert_old_deal(db, company_id_val, stage="Proposal"):
    """Insert a deal whose created_at is 8 days ago."""
    from app.models.deal import Deal
    from app.database.core import SessionLocal
    import uuid as _uuid
    deal = Deal(
        company_id=_uuid.UUID(company_id_val),
        deal_name=f"Old Deal {_uuid.uuid4().hex[:6]}",
        deal_value=50000,
        stage=stage,
        win_probability=30,
        created_at=datetime.now(timezone.utc) - timedelta(days=8),
    )
    db.add(deal)
    db.commit()
    db.refresh(deal)
    return deal


def test_at_risk_returns_open_idle_deals(client: TestClient, auth_headers: dict, company_id: str):
    """at_risk=true returns open deals with no activity for 7+ days."""
    before = client.get(f"{BASE_DEALS}/?at_risk=true", headers=auth_headers).json()["total"]

    from app.database.core import SessionLocal
    with SessionLocal() as db:
        _insert_old_deal(db, company_id)

    resp = client.get(f"{BASE_DEALS}/?at_risk=true", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert body["total"] == before + 1


def test_at_risk_excludes_closed_won(client: TestClient, auth_headers: dict, company_id: str):
    """Closed Won deals must NOT appear in at_risk results."""
    from app.database.core import SessionLocal
    with SessionLocal() as db:
        closed = _insert_old_deal(db, company_id, stage="Closed Won")

    resp = client.get(f"{BASE_DEALS}/?at_risk=true", headers=auth_headers)
    assert resp.status_code == 200
    ids = [item["id"] for item in resp.json()["items"]]
    assert str(closed.id) not in ids


def test_at_risk_excludes_closed_lost(client: TestClient, auth_headers: dict, company_id: str):
    """Closed Lost deals must NOT appear in at_risk results."""
    from app.database.core import SessionLocal
    with SessionLocal() as db:
        lost = _insert_old_deal(db, company_id, stage="Closed Lost")

    resp = client.get(f"{BASE_DEALS}/?at_risk=true", headers=auth_headers)
    assert resp.status_code == 200
    ids = [item["id"] for item in resp.json()["items"]]
    assert str(lost.id) not in ids


def test_at_risk_excludes_recent_deals(client: TestClient, auth_headers: dict, company_id: str):
    """A deal created just now must NOT appear in at_risk results."""
    created = client.post(f"{BASE_DEALS}/", json=_deal_payload(company_id), headers=auth_headers).json()
    resp = client.get(f"{BASE_DEALS}/?at_risk=true", headers=auth_headers)
    assert resp.status_code == 200
    ids = [item["id"] for item in resp.json()["items"]]
    assert created["id"] not in ids


def test_at_risk_no_auth(client: TestClient):
    with _no_auth(client):
        resp = client.get(f"{BASE_DEALS}/?at_risk=true")
    assert resp.status_code == 401


def test_at_risk_with_pagination(client: TestClient, auth_headers: dict, company_id: str):
    resp = client.get(f"{BASE_DEALS}/?at_risk=true&page=1&limit=2", headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()["items"]) <= 2


# ── Stage change → lead score + auto-schedule (#5 / #7) ───────────────────────

def test_stage_change_calls_update_lead_score(client: TestClient, auth_headers: dict, company_id: str):
    """Changing a deal stage must trigger update_lead_score for the associated lead."""
    from app.database.core import SessionLocal
    from app.models.leads import Lead
    import uuid as _uuid

    with SessionLocal() as db:
        lead = Lead(name="Score Test Lead", email=f"score_{_uuid.uuid4().hex[:6]}@test.com",
                    status="Contacted", interest_level="Warm", engagement_score=30)
        db.add(lead); db.commit(); db.refresh(lead)
        lead_id = lead.id

    payload = {**_deal_payload(company_id), "stage": "Prospect"}
    payload["lead_id"] = str(lead_id)
    created = client.post(f"{BASE_DEALS}/", json=payload, headers=auth_headers).json()

    with patch("app.services.lead_scoring_service.update_lead_score") as mock_score:
        resp = client.patch(
            f"{BASE_DEALS}/{created['id']}",
            json={"stage": "Proposal"},
            headers=auth_headers,
        )
    assert resp.status_code == 200
    mock_score.assert_called_once()


def test_stage_change_no_lead_does_not_crash(client: TestClient, auth_headers: dict, company_id: str):
    """Stage change on a deal with no lead_id must not raise an error."""
    created = client.post(f"{BASE_DEALS}/", json=_deal_payload(company_id), headers=auth_headers).json()
    with patch("app.services.lead_scoring_service.update_lead_score") as mock_score:
        resp = client.patch(
            f"{BASE_DEALS}/{created['id']}",
            json={"stage": "Negotiation"},
            headers=auth_headers,
        )
    assert resp.status_code == 200
    mock_score.assert_not_called()  # no lead_id → no score update


def test_stage_change_to_proposal_evaluates_deal_signal(client: TestClient, auth_headers: dict, company_id: str):
    """Stage → Proposal triggers evaluate_deal_signal check."""
    from app.database.core import SessionLocal
    from app.models.leads import Lead
    import uuid as _uuid

    with SessionLocal() as db:
        lead = Lead(name="Signal Lead", email=f"signal_{_uuid.uuid4().hex[:6]}@test.com",
                    status="Contacted", interest_level="Hot", engagement_score=70)
        db.add(lead); db.commit(); db.refresh(lead)
        lead_id = lead.id

    payload = {**_deal_payload(company_id), "stage": "Prospect", "lead_id": str(lead_id)}
    created = client.post(f"{BASE_DEALS}/", json=payload, headers=auth_headers).json()

    with (
        patch("app.services.lead_scoring_service.update_lead_score"),
        patch("app.services.deal_signal_service.evaluate_deal_signal", return_value=False) as mock_signal,
    ):
        resp = client.patch(
            f"{BASE_DEALS}/{created['id']}",
            json={"stage": "Proposal"},
            headers=auth_headers,
        )
    assert resp.status_code == 200
    mock_signal.assert_called_once()


def test_no_stage_change_skips_signal_eval(client: TestClient, auth_headers: dict, company_id: str):
    """Updating deal_value without changing stage must NOT call evaluate_deal_signal."""
    created = client.post(f"{BASE_DEALS}/", json=_deal_payload(company_id), headers=auth_headers).json()
    with patch("app.services.deal_signal_service.evaluate_deal_signal") as mock_signal:
        resp = client.patch(
            f"{BASE_DEALS}/{created['id']}",
            json={"deal_value": 200000},
            headers=auth_headers,
        )
    assert resp.status_code == 200
    mock_signal.assert_not_called()
