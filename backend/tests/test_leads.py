import uuid
import pytest
from fastapi.testclient import TestClient

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
