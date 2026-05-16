import uuid
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.database.core import SessionLocal
from app.models.product import Product
from app.models.product_knowledge import ProductKnowledge

BASE_PRODUCTS = "/api/v1/products"


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


def _create_product() -> uuid.UUID:
    from app.core.utils import new_uuid
    with SessionLocal() as db:
        p = Product(
            id=new_uuid(),
            order_code=f"TEST-KNW-{uuid.uuid4().hex[:8]}",
            name=f"Test Knowledge Product {uuid.uuid4().hex[:6]}",
            category="Test",
            brand="RDL",
            single_price=999.0,
            is_active=True,
        )
        db.add(p)
        db.commit()
        return p.id


def _mock_vs():
    vs = MagicMock()
    vs.add_documents.return_value = None
    vs.delete.return_value = None
    return vs


# ── Cleanup ───────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def clean_test_knowledge():
    def _purge():
        with SessionLocal() as db:
            from sqlalchemy import text
            db.execute(text("DELETE FROM product_knowledge_entries WHERE added_by LIKE 'test_%@rdltest.com'"))
            db.execute(text("DELETE FROM products WHERE order_code LIKE 'TEST-KNW-%'"))
            db.commit()
    _purge()
    yield
    _purge()


# ── POST /{product_id}/knowledge ──────────────────────────────────────────────

def test_add_knowledge_success(client, auth_headers):
    pid = _create_product()
    with patch("app.services.product_knowledge_service._get_vectorstore", return_value=_mock_vs()):
        resp = client.post(
            f"{BASE_PRODUCTS}/{pid}/knowledge",
            json={"category": "warranty", "content": "2 year warranty from date of purchase."},
            headers=auth_headers,
        )
    assert resp.status_code == 201
    body = resp.json()
    assert body["category"] == "warranty"
    assert body["content"] == "2 year warranty from date of purchase."
    assert body["product_id"] == str(pid)
    assert body["added_by"]  # set to current user email


def test_add_knowledge_compatibility(client, auth_headers):
    pid = _create_product()
    with patch("app.services.product_knowledge_service._get_vectorstore", return_value=_mock_vs()):
        resp = client.post(
            f"{BASE_PRODUCTS}/{pid}/knowledge",
            json={"category": "compatibility", "content": "Compatible with Arduino Uno, ESP32, Raspberry Pi."},
            headers=auth_headers,
        )
    assert resp.status_code == 201
    assert resp.json()["category"] == "compatibility"


def test_add_knowledge_nonexistent_product(client, auth_headers):
    with patch("app.services.product_knowledge_service._get_vectorstore", return_value=_mock_vs()):
        resp = client.post(
            f"{BASE_PRODUCTS}/{uuid.uuid4()}/knowledge",
            json={"category": "warranty", "content": "Test"},
            headers=auth_headers,
        )
    assert resp.status_code == 404


def test_add_knowledge_missing_category(client, auth_headers):
    pid = _create_product()
    resp = client.post(
        f"{BASE_PRODUCTS}/{pid}/knowledge",
        json={"content": "Missing category"},
        headers=auth_headers,
    )
    assert resp.status_code == 422


def test_add_knowledge_missing_content(client, auth_headers):
    pid = _create_product()
    resp = client.post(
        f"{BASE_PRODUCTS}/{pid}/knowledge",
        json={"category": "warranty"},
        headers=auth_headers,
    )
    assert resp.status_code == 422


def test_add_knowledge_no_auth(client):
    pid = _create_product()
    with _no_auth(client):
        resp = client.post(
            f"{BASE_PRODUCTS}/{pid}/knowledge",
            json={"category": "warranty", "content": "Test"},
        )
    assert resp.status_code == 401


# ── GET /{product_id}/knowledge ───────────────────────────────────────────────

def test_list_knowledge_empty(client, auth_headers):
    pid = _create_product()
    resp = client.get(f"{BASE_PRODUCTS}/{pid}/knowledge", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["items"] == []
    assert body["total"] == 0


def test_list_knowledge_returns_entries(client, auth_headers):
    pid = _create_product()
    with patch("app.services.product_knowledge_service._get_vectorstore", return_value=_mock_vs()):
        client.post(
            f"{BASE_PRODUCTS}/{pid}/knowledge",
            json={"category": "pricing", "content": "Bulk: 10+ units at 10% off."},
            headers=auth_headers,
        )
        client.post(
            f"{BASE_PRODUCTS}/{pid}/knowledge",
            json={"category": "warranty", "content": "1 year onsite warranty."},
            headers=auth_headers,
        )
    resp = client.get(f"{BASE_PRODUCTS}/{pid}/knowledge", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] == 2


def test_list_knowledge_nonexistent_product(client, auth_headers):
    resp = client.get(f"{BASE_PRODUCTS}/{uuid.uuid4()}/knowledge", headers=auth_headers)
    assert resp.status_code == 404


def test_list_knowledge_no_auth(client):
    pid = _create_product()
    with _no_auth(client):
        resp = client.get(f"{BASE_PRODUCTS}/{pid}/knowledge")
    assert resp.status_code == 401


# ── PATCH /{product_id}/knowledge/{entry_id} ──────────────────────────────────

def test_update_knowledge_success(client, auth_headers):
    pid = _create_product()
    with patch("app.services.product_knowledge_service._get_vectorstore", return_value=_mock_vs()):
        create_resp = client.post(
            f"{BASE_PRODUCTS}/{pid}/knowledge",
            json={"category": "warranty", "content": "1 year warranty."},
            headers=auth_headers,
        )
        entry_id = create_resp.json()["id"]

        resp = client.patch(
            f"{BASE_PRODUCTS}/{pid}/knowledge/{entry_id}",
            json={"content": "2 year warranty with onsite support."},
            headers=auth_headers,
        )
    assert resp.status_code == 200
    assert resp.json()["content"] == "2 year warranty with onsite support."


def test_update_knowledge_not_found(client, auth_headers):
    pid = _create_product()
    with patch("app.services.product_knowledge_service._get_vectorstore", return_value=_mock_vs()):
        resp = client.patch(
            f"{BASE_PRODUCTS}/{pid}/knowledge/{uuid.uuid4()}",
            json={"content": "Updated"},
            headers=auth_headers,
        )
    assert resp.status_code == 404


def test_update_knowledge_no_auth(client):
    pid = _create_product()
    with _no_auth(client):
        resp = client.patch(
            f"{BASE_PRODUCTS}/{pid}/knowledge/{uuid.uuid4()}",
            json={"content": "Updated"},
        )
    assert resp.status_code == 401


# ── DELETE /{product_id}/knowledge/{entry_id} ─────────────────────────────────

def test_delete_knowledge_success(client, auth_headers):
    pid = _create_product()
    with patch("app.services.product_knowledge_service._get_vectorstore", return_value=_mock_vs()):
        create_resp = client.post(
            f"{BASE_PRODUCTS}/{pid}/knowledge",
            json={"category": "general", "content": "To be deleted."},
            headers=auth_headers,
        )
        entry_id = create_resp.json()["id"]

        resp = client.delete(
            f"{BASE_PRODUCTS}/{pid}/knowledge/{entry_id}",
            headers=auth_headers,
        )
    assert resp.status_code == 204

    # Verify gone from list
    list_resp = client.get(f"{BASE_PRODUCTS}/{pid}/knowledge", headers=auth_headers)
    ids = [i["id"] for i in list_resp.json()["items"]]
    assert entry_id not in ids


def test_delete_knowledge_not_found(client, auth_headers):
    pid = _create_product()
    with patch("app.services.product_knowledge_service._get_vectorstore", return_value=_mock_vs()):
        resp = client.delete(
            f"{BASE_PRODUCTS}/{pid}/knowledge/{uuid.uuid4()}",
            headers=auth_headers,
        )
    assert resp.status_code == 404


def test_delete_knowledge_no_auth(client):
    pid = _create_product()
    with _no_auth(client):
        resp = client.delete(f"{BASE_PRODUCTS}/{pid}/knowledge/{uuid.uuid4()}")
    assert resp.status_code == 401


# ── Auto-send unit tests ──────────────────────────────────────────────────────

def test_route_sales_autosends_when_no_gaps():
    """When draft has no gaps, node_auto_send sends immediately — status=REPLIED."""
    from app.models.communication import Email, EmailLabel, EmailStatus
    from app.services.workflows.email_nodes import node_auto_send
    from app.database.core import SessionLocal
    from datetime import datetime, timezone
    import uuid as _uuid

    email_id = None
    with SessionLocal() as s:
        row = Email(
            gmail_message_id=f"test_{_uuid.uuid4().hex}",
            direction="inbound", sender="buyer@example.com",
            recipients=["dev@rdltech.in"], subject="Product query",
            body_text="What is the price?",
            received_at=datetime.now(timezone.utc),
            label=EmailLabel.SALES, status=EmailStatus.CLASSIFIED,
        )
        s.add(row); s.commit(); s.refresh(row)
        email_id = str(row.id)

    from app.database.core import SessionLocal as SL
    with SL() as db:
        config = {"configurable": {"thread_id": "test", "db": db, "gmail_svc": MagicMock()}}
        with (
            patch("app.services.workflows.email_nodes.gmail_service.create_draft", return_value={"id": "drf_tmp"}),
            patch("app.services.workflows.email_nodes.gmail_service.send_draft"),
        ):
            result = node_auto_send(
                {"email_id": email_id, "sender_email": "buyer@example.com",
                 "subject": "Product query", "draft": "The price is Rs 5799.",
                 "gmail_thread_id": None},
                config,
            )
        assert result["action"] == "auto_sent"
        db.commit()

    with SL() as s:
        row = s.query(Email).filter(Email.id == _uuid.UUID(email_id)).first()
        assert row.status == EmailStatus.REPLIED
        assert row.gmail_draft_id is None
        s.delete(row); s.commit()


def test_route_sales_sends_and_logs_gaps():
    """node_hold_draft: when gaps exist, draft is held for review with status=DRAFT_READY."""
    from app.models.communication import Email, EmailLabel, EmailStatus
    from app.services.workflows.email_nodes import node_hold_draft
    from app.database.core import SessionLocal
    from datetime import datetime, timezone
    import uuid as _uuid

    email_id = None
    with SessionLocal() as s:
        row = Email(
            gmail_message_id=f"test_{_uuid.uuid4().hex}",
            direction="inbound", sender="buyer@example.com",
            recipients=["dev@rdltech.in"], subject="Lead time query",
            body_text="What is the lead time?",
            received_at=datetime.now(timezone.utc),
            label=EmailLabel.SALES, status=EmailStatus.CLASSIFIED,
        )
        s.add(row); s.commit(); s.refresh(row)
        email_id = str(row.id)

    from app.database.core import SessionLocal as SL
    gaps = [{"question": "lead time?", "topic": "general", "resolved": False}]
    with SL() as db:
        config = {"configurable": {"thread_id": "test", "db": db, "gmail_svc": MagicMock()}}
        with patch("app.services.workflows.email_nodes.gmail_service.create_draft",
                   return_value={"id": "drf_abc"}):
            result = node_hold_draft(
                {"email_id": email_id, "sender_email": "buyer@example.com",
                 "subject": "Lead time query",
                 "draft": "Our team will confirm the lead time shortly.",
                 "gaps": gaps, "gmail_thread_id": None},
                config,
            )
        assert result["action"] == "draft_held"
        db.commit()

    with SL() as s:
        row = s.query(Email).filter(Email.id == _uuid.UUID(email_id)).first()
        assert row.status == EmailStatus.DRAFT_READY
        assert row.needs_human is True
        s.delete(row); s.commit()
