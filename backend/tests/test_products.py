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


# ── Product search & filter ───────────────────────────────────────────────────

def test_search_by_name(client: TestClient, auth_headers: dict):
    code = _order_code()
    client.post(f"{BASE}/", json={**_payload(code), "Product_id": "SearchableWidget Pro"}, headers=auth_headers)
    resp = client.get(f"{BASE}/?search=SearchableWidget", headers=auth_headers)
    assert resp.status_code == 200
    names = [p["Product_id"] for p in resp.json()]
    assert any("SearchableWidget" in n for n in names)


def test_search_by_order_code(client: TestClient, auth_headers: dict):
    code = _order_code()
    client.post(f"{BASE}/", json=_payload(code), headers=auth_headers)
    resp = client.get(f"{BASE}/?search={code}", headers=auth_headers)
    assert resp.status_code == 200
    codes = [p.get("Order Code") for p in resp.json()]
    assert code in codes


def test_search_no_results(client: TestClient, auth_headers: dict):
    resp = client.get(f"{BASE}/?search=ZZZNOMATCHXYZ999", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == []


def test_filter_by_category(client: TestClient, auth_headers: dict):
    code = _order_code()
    payload = {**_payload(code), "Category": "UniqueCatXYZ"}
    client.post(f"{BASE}/", json=payload, headers=auth_headers)
    resp = client.get(f"{BASE}/?category=UniqueCatXYZ", headers=auth_headers)
    assert resp.status_code == 200
    assert all(p["Category"] == "UniqueCatXYZ" for p in resp.json())
    assert len(resp.json()) >= 1


def test_filter_active_only(client: TestClient, auth_headers: dict):
    code = _order_code()
    created = client.post(f"{BASE}/", json=_payload(code), headers=auth_headers).json()
    # Deactivate it
    client.patch(f"{BASE}/{created['id']}/availability", headers=auth_headers)
    # Filter active only — should not include our deactivated product
    resp = client.get(f"{BASE}/?is_active=true", headers=auth_headers)
    assert resp.status_code == 200
    ids = [p["id"] for p in resp.json()]
    assert created["id"] not in ids


def test_search_no_auth(client: TestClient):
    saved = dict(client.cookies)
    client.cookies.clear()
    try:
        resp = client.get(f"{BASE}/?search=test")
        assert resp.status_code == 401
    finally:
        for k, v in saved.items():
            client.cookies.set(k, v)


# ── Embedding endpoints ───────────────────────────────────────────────────────

def test_list_all_embeddings_shape(client: TestClient, auth_headers: dict):
    """GET /products/embeddings returns expected top-level keys."""
    resp = client.get(f"{BASE}/embeddings", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "total_products" in data
    assert "total_embeddings" in data
    assert "not_embedded" in data
    assert "items" in data
    assert isinstance(data["items"], list)
    assert isinstance(data["not_embedded"], list)


def test_list_all_embeddings_product_fields(client: TestClient, auth_headers: dict):
    """Each item in embeddings list has the required product detail fields."""
    # Create a product so there's at least one to inspect
    client.post(f"{BASE}/", json=_payload(), headers=auth_headers)
    resp = client.get(f"{BASE}/embeddings", headers=auth_headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) >= 1
    p = items[0]
    for field in ("product_id", "name", "order_code", "category", "single_price",
                  "bulk_price", "brand", "coverage_score", "is_active",
                  "total_chunks", "chunk_types", "chunks"):
        assert field in p, f"Missing field: {field}"


def test_new_product_has_zero_chunks(client: TestClient, auth_headers: dict):
    """A freshly created product with no embeddings appears in not_embedded list."""
    code = _order_code()
    created = client.post(f"{BASE}/", json=_payload(code), headers=auth_headers).json()
    resp = client.get(f"{BASE}/embeddings", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    # Find our product in items
    match = next((p for p in data["items"] if p["product_id"] == created["id"]), None)
    assert match is not None
    assert match["total_chunks"] == 0
    assert match["name"] in data["not_embedded"]


def test_list_all_embeddings_no_auth(client: TestClient):
    saved = dict(client.cookies)
    client.cookies.clear()
    try:
        resp = client.get(f"{BASE}/embeddings")
        assert resp.status_code == 401
    finally:
        for k, v in saved.items():
            client.cookies.set(k, v)


def test_get_product_embeddings_shape(client: TestClient, auth_headers: dict):
    """GET /products/{id}/embeddings returns product detail and chunks list."""
    created = client.post(f"{BASE}/", json=_payload(), headers=auth_headers).json()
    resp = client.get(f"{BASE}/{created['id']}/embeddings", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    for field in ("product_id", "name", "order_code", "category", "single_price",
                  "bulk_price", "brand", "coverage_score", "total_chunks", "chunks"):
        assert field in data, f"Missing field: {field}"
    assert data["product_id"] == created["id"]
    assert isinstance(data["chunks"], list)
    assert data["total_chunks"] == 0  # freshly created, not yet ingested


def test_get_product_embeddings_not_found(client: TestClient, auth_headers: dict):
    resp = client.get(f"{BASE}/{uuid.uuid4()}/embeddings", headers=auth_headers)
    assert resp.status_code == 404


def test_get_product_embeddings_no_auth(client: TestClient):
    saved = dict(client.cookies)
    client.cookies.clear()
    try:
        resp = client.get(f"{BASE}/{uuid.uuid4()}/embeddings")
        assert resp.status_code == 401
    finally:
        for k, v in saved.items():
            client.cookies.set(k, v)
