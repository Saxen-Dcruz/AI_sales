import uuid
import pytest
from fastapi.testclient import TestClient

BASE = "/api/v1/companies"


def _payload(name: str = None) -> dict:
    return {
        "name": name or f"Test Company {uuid.uuid4().hex[:6]}",
        "industry": "Technology",
        "company_size": "50-200",
        "headquarters": "Mumbai, India",
    }


# ── Success paths ─────────────────────────────────────────────────────────────

def test_create_company(client: TestClient, auth_headers: dict):
    resp = client.post(f"{BASE}/", json=_payload(), headers=auth_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert "id" in data
    assert data["name"] is not None


def test_list_companies(client: TestClient, auth_headers: dict):
    client.post(f"{BASE}/", json=_payload(), headers=auth_headers)
    resp = client.get(f"{BASE}/", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert "total" in body
    assert body["total"] >= 1


def test_get_company(client: TestClient, auth_headers: dict):
    created = client.post(f"{BASE}/", json=_payload(), headers=auth_headers).json()
    resp = client.get(f"{BASE}/{created['id']}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]


def test_update_company(client: TestClient, auth_headers: dict):
    created = client.post(f"{BASE}/", json=_payload(), headers=auth_headers).json()
    resp = client.patch(
        f"{BASE}/{created['id']}",
        json={"industry": "Manufacturing", "company_size": "200-500"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["industry"] == "Manufacturing"


def test_delete_company(client: TestClient, auth_headers: dict):
    created = client.post(f"{BASE}/", json=_payload(), headers=auth_headers).json()
    del_resp = client.delete(f"{BASE}/{created['id']}", headers=auth_headers)
    assert del_resp.status_code == 204
    get_resp = client.get(f"{BASE}/{created['id']}", headers=auth_headers)
    assert get_resp.status_code == 404


def test_list_companies_filter_by_industry(client: TestClient, auth_headers: dict):
    client.post(f"{BASE}/", json={**_payload(), "industry": "Healthcare"}, headers=auth_headers)
    resp = client.get(f"{BASE}/?industry=Healthcare", headers=auth_headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert all(item["industry"] == "Healthcare" for item in items)


def test_list_companies_pagination(client: TestClient, auth_headers: dict):
    resp = client.get(f"{BASE}/?page=1&limit=2", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) <= 2


# ── Validation failures ───────────────────────────────────────────────────────

def test_create_company_missing_name(client: TestClient, auth_headers: dict):
    resp = client.post(f"{BASE}/", json={"industry": "Tech"}, headers=auth_headers)
    assert resp.status_code == 422


def test_get_nonexistent_company(client: TestClient, auth_headers: dict):
    resp = client.get(f"{BASE}/{uuid.uuid4()}", headers=auth_headers)
    assert resp.status_code == 404


def test_update_nonexistent_company(client: TestClient, auth_headers: dict):
    resp = client.patch(f"{BASE}/{uuid.uuid4()}", json={"industry": "Tech"}, headers=auth_headers)
    assert resp.status_code == 404


def test_delete_nonexistent_company(client: TestClient, auth_headers: dict):
    resp = client.delete(f"{BASE}/{uuid.uuid4()}", headers=auth_headers)
    assert resp.status_code == 404


# ── Auth failures ─────────────────────────────────────────────────────────────

def test_list_companies_no_auth(client: TestClient):
    saved = dict(client.cookies)
    client.cookies.clear()
    try:
        resp = client.get(f"{BASE}/")
        assert resp.status_code == 401
    finally:
        for k, v in saved.items():
            client.cookies.set(k, v)


def test_create_company_no_auth(client: TestClient):
    saved = dict(client.cookies)
    client.cookies.clear()
    try:
        resp = client.post(f"{BASE}/", json=_payload())
        assert resp.status_code == 401
    finally:
        for k, v in saved.items():
            client.cookies.set(k, v)
