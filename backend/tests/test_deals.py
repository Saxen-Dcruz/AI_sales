import uuid
import pytest
from fastapi.testclient import TestClient

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
