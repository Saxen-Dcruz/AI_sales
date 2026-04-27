import itertools
import uuid
import pytest
from fastapi.testclient import TestClient

BASE = "/api/v1/products"

_counter = itertools.count(1)


def _order_code() -> str:
    return f"TEST-{next(_counter):06d}"


def _payload(order_code: str = None) -> dict:
    return {
        "Product_id": "Test Development Board",
        "Order Code": order_code or _order_code(),
        "Category": "Development Board",
        "Brand": "TestBrand",
        "Price": 5000.0,
        "sections": {"Description": "Test product description.", "Features": "- Feature A"},
    }


# ── Success paths ─────────────────────────────────────────────────────────────

def test_create_product(client: TestClient, auth_headers: dict):
    resp = client.post(f"{BASE}/", json=_payload(), headers=auth_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["Product_id"] == "Test Development Board"
    assert "id" in data


def test_list_products(client: TestClient, auth_headers: dict):
    client.post(f"{BASE}/", json=_payload(), headers=auth_headers)
    resp = client.get(f"{BASE}/", headers=auth_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
    assert len(resp.json()) >= 1


def test_get_product(client: TestClient, auth_headers: dict):
    created = client.post(f"{BASE}/", json=_payload(), headers=auth_headers).json()
    resp = client.get(f"{BASE}/{created['id']}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]


def test_update_product(client: TestClient, auth_headers: dict):
    created = client.post(f"{BASE}/", json=_payload(), headers=auth_headers).json()
    resp = client.patch(
        f"{BASE}/{created['id']}",
        json={"brand": "UpdatedBrand", "single_price": 9999.0},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["Brand"] == "UpdatedBrand"
    assert data["Price"] == 9999.0


def test_update_product_links(client: TestClient, auth_headers: dict):
    """PATCH can update all RAG-relevant link and pricing fields."""
    created = client.post(f"{BASE}/", json=_payload(), headers=auth_headers).json()
    resp = client.patch(
        f"{BASE}/{created['id']}",
        json={
            "datasheet_link": "https://rdltech.in/datasheets/test.pdf",
            "product_link": "https://rdltech.in/products/test",
            "user_manual_link": "https://rdltech.in/manuals/test.pdf",
            "bulk_price": 4200.0,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["Data Sheet link"] == "https://rdltech.in/datasheets/test.pdf"
    assert data["Product Link"] == "https://rdltech.in/products/test"
    assert data["User Manual"] == "https://rdltech.in/manuals/test.pdf"
    assert data["bulk_price"] == 4200.0


def test_delete_product(client: TestClient, auth_headers: dict):
    created = client.post(f"{BASE}/", json=_payload(), headers=auth_headers).json()
    del_resp = client.delete(f"{BASE}/{created['id']}", headers=auth_headers)
    assert del_resp.status_code == 204
    get_resp = client.get(f"{BASE}/{created['id']}", headers=auth_headers)
    assert get_resp.status_code == 404


# ── Validation failures ───────────────────────────────────────────────────────

def test_create_duplicate_order_code(client: TestClient, auth_headers: dict):
    code = _order_code()
    client.post(f"{BASE}/", json=_payload(code), headers=auth_headers)
    resp = client.post(f"{BASE}/", json=_payload(code), headers=auth_headers)
    assert resp.status_code == 400


def test_get_nonexistent_product(client: TestClient, auth_headers: dict):
    resp = client.get(f"{BASE}/{uuid.uuid4()}", headers=auth_headers)
    assert resp.status_code == 404


# ── Auth failures ─────────────────────────────────────────────────────────────

def test_list_products_no_auth(client: TestClient):
    saved = dict(client.cookies)
    client.cookies.clear()
    try:
        resp = client.get(f"{BASE}/")
        assert resp.status_code == 401
    finally:
        for k, v in saved.items():
            client.cookies.set(k, v)


def test_create_product_no_auth(client: TestClient):
    saved = dict(client.cookies)
    client.cookies.clear()
    try:
        resp = client.post(f"{BASE}/", json=_payload())
        assert resp.status_code == 401
    finally:
        for k, v in saved.items():
            client.cookies.set(k, v)


def test_toggle_availability(client: TestClient, auth_headers: dict):
    # Create a product (is_active=True by default)
    resp = client.post(f"{BASE}/", json=_payload(), headers=auth_headers)
    assert resp.status_code == 201
    product_id = resp.json()["id"]
    assert resp.json()["is_active"] is True

    # Toggle off
    resp = client.patch(f"{BASE}/{product_id}/availability", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False

    # Toggle back on
    resp = client.patch(f"{BASE}/{product_id}/availability", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["is_active"] is True


def test_toggle_availability_not_found(client: TestClient, auth_headers: dict):
    import uuid
    resp = client.patch(f"{BASE}/{uuid.uuid4()}/availability", headers=auth_headers)
    assert resp.status_code == 404


def test_toggle_availability_no_auth(client: TestClient):
    import uuid
    saved = dict(client.cookies)
    client.cookies.clear()
    try:
        resp = client.patch(f"{BASE}/{uuid.uuid4()}/availability")
        assert resp.status_code == 401
    finally:
        for k, v in saved.items():
            client.cookies.set(k, v)
