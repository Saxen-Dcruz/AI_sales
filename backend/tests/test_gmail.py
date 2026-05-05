import base64
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.database.core import SessionLocal
from app.models.communication import Email, EmailLabel, EmailStatus

BASE = "/api/v1/gmail"


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


def _insert_email(**kwargs) -> uuid.UUID:
    defaults = {
        "gmail_message_id": f"test_{uuid.uuid4().hex}",
        "gmail_thread_id": f"tth_{uuid.uuid4().hex}",
        "direction": "inbound",
        "sender": "sender@example.com",
        "recipients": ["developer20@rdltech.in"],
        "subject": "Test subject",
        "body_text": "Test body",
        "received_at": datetime.now(timezone.utc),
        "label": EmailLabel.SALES,
        "status": EmailStatus.CLASSIFIED,
        "needs_human": False,
    }
    defaults.update(kwargs)
    with SessionLocal() as db:
        row = Email(**defaults)
        db.add(row)
        db.commit()
        db.refresh(row)
        return row.id


def _raw_msg(gmail_id=None, subject="Test", body="Hello", sender="sender@example.com"):
    mid = gmail_id or uuid.uuid4().hex
    data = base64.urlsafe_b64encode(body.encode()).decode().rstrip("=")
    return {
        "id": mid,
        "threadId": f"th_{mid}",
        "payload": {
            "mimeType": "text/plain",
            "headers": [
                {"name": "From", "value": sender},
                {"name": "To", "value": "developer20@rdltech.in"},
                {"name": "Subject", "value": subject},
                {"name": "Date", "value": "Mon, 21 Apr 2026 10:00:00 +0000"},
            ],
            "body": {"data": data},
        },
    }


def _mock_gmail_svc():
    svc = MagicMock()
    svc.users.return_value.messages.return_value.modify.return_value.execute.return_value = {}
    svc.users.return_value.labels.return_value.list.return_value.execute.return_value = {
        "labels": [{"name": "RDL/Sales", "id": "lbl_sales"}]
    }
    return svc


# ── Cleanup ───────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def clean_test_emails():
    def _purge():
        with SessionLocal() as db:
            db.execute(text("DELETE FROM emails WHERE gmail_message_id LIKE 'test_%'"))
            db.commit()
    _purge()
    yield
    _purge()


# ── POST /sync ────────────────────────────────────────────────────────────────

def test_sync_empty_inbox(client, auth_headers):
    with (
        patch("app.routers.gmail.gmail_service.get_gmail_service", return_value=MagicMock()),
        patch("app.routers.gmail.gmail_service.ensure_labels_exist"),
        patch("app.routers.gmail.gmail_service.fetch_unread_messages", return_value=[]),
    ):
        resp = client.post(f"{BASE}/sync", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == {"fetched": 0, "processed": 0}


def test_sync_processes_messages(client, auth_headers):
    with (
        patch("app.routers.gmail.gmail_service.get_gmail_service", return_value=MagicMock()),
        patch("app.routers.gmail.gmail_service.ensure_labels_exist"),
        patch("app.routers.gmail.gmail_service.fetch_unread_messages", return_value=[_raw_msg(), _raw_msg()]),
        patch("app.routers.gmail.process_inbound_email", return_value=MagicMock()),
    ):
        resp = client.post(f"{BASE}/sync", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["fetched"] == 2
    assert resp.json()["processed"] == 2


def test_sync_skips_already_processed(client, auth_headers):
    with (
        patch("app.routers.gmail.gmail_service.get_gmail_service", return_value=MagicMock()),
        patch("app.routers.gmail.gmail_service.ensure_labels_exist"),
        patch("app.routers.gmail.gmail_service.fetch_unread_messages", return_value=[_raw_msg()]),
        patch("app.routers.gmail.process_inbound_email", return_value=None),
    ):
        resp = client.post(f"{BASE}/sync", headers=auth_headers)
    assert resp.json()["fetched"] == 1
    assert resp.json()["processed"] == 0


def test_sync_max_results_too_high(client, auth_headers):
    resp = client.post(f"{BASE}/sync?max_results=51", headers=auth_headers)
    assert resp.status_code == 422


def test_sync_max_results_too_low(client, auth_headers):
    resp = client.post(f"{BASE}/sync?max_results=0", headers=auth_headers)
    assert resp.status_code == 422


def test_sync_no_auth(client):
    with _no_auth(client):
        resp = client.post(f"{BASE}/sync")
    assert resp.status_code == 401


# ── GET / ─────────────────────────────────────────────────────────────────────

def test_list_emails_returns_envelope(client, auth_headers):
    resp = client.get(f"{BASE}/", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    for key in ("items", "total", "page", "limit"):
        assert key in body


def test_list_emails_filter_by_label(client, auth_headers):
    _insert_email(label=EmailLabel.SUPPORT, status=EmailStatus.PENDING_HUMAN, needs_human=True)
    resp = client.get(f"{BASE}/?label=Support", headers=auth_headers)
    assert resp.status_code == 200
    for item in resp.json()["items"]:
        assert item["label"] == "Support"


def test_list_emails_filter_by_status(client, auth_headers):
    _insert_email(status=EmailStatus.DRAFT_READY, gmail_draft_id="drf_lst", ai_draft="text")
    resp = client.get(f"{BASE}/?status=draft_ready", headers=auth_headers)
    assert resp.status_code == 200
    for item in resp.json()["items"]:
        assert item["status"] == "draft_ready"


def test_list_emails_filter_needs_human_true(client, auth_headers):
    _insert_email(label=EmailLabel.GRIEVANCE, needs_human=True, status=EmailStatus.PENDING_HUMAN)
    resp = client.get(f"{BASE}/?needs_human=true", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1
    for item in resp.json()["items"]:
        assert item["needs_human"] is True


def test_list_emails_filter_needs_human_false(client, auth_headers):
    resp = client.get(f"{BASE}/?needs_human=false", headers=auth_headers)
    assert resp.status_code == 200
    for item in resp.json()["items"]:
        assert item["needs_human"] is False


def test_list_emails_pagination_respects_limit(client, auth_headers):
    for _ in range(3):
        _insert_email()
    resp = client.get(f"{BASE}/?limit=1&page=1", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 1
    assert body["limit"] == 1
    assert body["page"] == 1


def test_list_emails_page_beyond_total(client, auth_headers):
    resp = client.get(f"{BASE}/?page=9999&limit=100", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["items"] == []


def test_list_emails_invalid_limit_zero(client, auth_headers):
    resp = client.get(f"{BASE}/?limit=0", headers=auth_headers)
    assert resp.status_code == 422


def test_list_emails_limit_over_max(client, auth_headers):
    resp = client.get(f"{BASE}/?limit=101", headers=auth_headers)
    assert resp.status_code == 422


def test_list_emails_invalid_label(client, auth_headers):
    resp = client.get(f"{BASE}/?label=NotALabel", headers=auth_headers)
    assert resp.status_code == 422


def test_list_emails_no_auth(client):
    with _no_auth(client):
        resp = client.get(f"{BASE}/")
    assert resp.status_code == 401


# ── GET /{id} ─────────────────────────────────────────────────────────────────

def test_get_email_found(client, auth_headers):
    eid = _insert_email(subject="Find me by ID")
    resp = client.get(f"{BASE}/{eid}", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == str(eid)
    assert body["subject"] == "Find me by ID"


def test_get_email_response_shape(client, auth_headers):
    eid = _insert_email()
    resp = client.get(f"{BASE}/{eid}", headers=auth_headers)
    body = resp.json()
    for field in ("id", "direction", "sender", "recipients", "label", "status", "needs_human", "created_at"):
        assert field in body


def test_get_email_not_found(client, auth_headers):
    resp = client.get(f"{BASE}/{uuid.uuid4()}", headers=auth_headers)
    assert resp.status_code == 404


def test_get_email_no_auth(client):
    eid = _insert_email()
    with _no_auth(client):
        resp = client.get(f"{BASE}/{eid}")
    assert resp.status_code == 401


# ── POST /{id}/resolve ────────────────────────────────────────────────────────

def test_resolve_email_success(client, auth_headers):
    eid = _insert_email(label=EmailLabel.SUPPORT, status=EmailStatus.PENDING_HUMAN, needs_human=True)
    resp = client.post(
        f"{BASE}/{eid}/resolve",
        json={"resolved_by": "agent@rdltech.in"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "replied"
    assert body["needs_human"] is False
    assert body["resolved_by"] == "agent@rdltech.in"
    assert body["resolved_at"] is not None


def test_resolve_email_empty_resolved_by_uses_current_user(client, auth_headers):
    eid = _insert_email(label=EmailLabel.GRIEVANCE, needs_human=True, status=EmailStatus.PENDING_HUMAN)
    resp = client.post(
        f"{BASE}/{eid}/resolve",
        json={"resolved_by": ""},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["resolved_by"]  # falls back to current user email — non-empty


def test_resolve_email_not_found(client, auth_headers):
    resp = client.post(
        f"{BASE}/{uuid.uuid4()}/resolve",
        json={"resolved_by": "agent@rdltech.in"},
        headers=auth_headers,
    )
    assert resp.status_code == 404


def test_resolve_email_missing_resolved_by(client, auth_headers):
    eid = _insert_email(label=EmailLabel.SUPPORT, needs_human=True)
    resp = client.post(f"{BASE}/{eid}/resolve", json={}, headers=auth_headers)
    assert resp.status_code == 422


def test_resolve_email_no_auth(client):
    eid = _insert_email(label=EmailLabel.SUPPORT, needs_human=True)
    with _no_auth(client):
        resp = client.post(f"{BASE}/{eid}/resolve", json={"resolved_by": "x@x.com"})
    assert resp.status_code == 401


# ── POST /{id}/approve-draft ──────────────────────────────────────────────────

def test_approve_draft_not_found(client, auth_headers):
    resp = client.post(f"{BASE}/{uuid.uuid4()}/approve-draft", json={}, headers=auth_headers)
    assert resp.status_code == 404


def test_approve_draft_wrong_status(client, auth_headers):
    eid = _insert_email(status=EmailStatus.REPLIED)
    resp = client.post(f"{BASE}/{eid}/approve-draft", json={}, headers=auth_headers)
    assert resp.status_code == 400
    assert "pending draft" in resp.json()["detail"]


def test_approve_draft_no_draft_id(client, auth_headers):
    eid = _insert_email(status=EmailStatus.DRAFT_READY, gmail_draft_id=None)
    resp = client.post(f"{BASE}/{eid}/approve-draft", json={}, headers=auth_headers)
    assert resp.status_code == 400
    assert "draft ID" in resp.json()["detail"]


def test_approve_draft_success(client, auth_headers):
    eid = _insert_email(status=EmailStatus.DRAFT_READY, gmail_draft_id="drf_ok", ai_draft="Draft text")
    with (
        patch("app.routers.gmail.gmail_service.get_gmail_service", return_value=MagicMock()),
        patch("app.routers.gmail.gmail_service.send_draft", return_value={"id": "msg_sent"}),
    ):
        resp = client.post(f"{BASE}/{eid}/approve-draft", json={}, headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "replied"
    assert body["resolved_at"] is not None


def test_approve_draft_with_edit_body(client, auth_headers):
    eid = _insert_email(
        status=EmailStatus.DRAFT_READY,
        gmail_draft_id="drf_edit",
        ai_draft="Original draft",
        sender="customer@example.com",
        subject="Re: Product Query",
    )
    mock_svc = MagicMock()
    mock_svc.users.return_value.drafts.return_value.delete.return_value.execute.return_value = {}
    with (
        patch("app.routers.gmail.gmail_service.get_gmail_service", return_value=mock_svc),
        patch("app.routers.gmail.gmail_service.create_draft", return_value={"id": "drf_new"}),
        patch("app.routers.gmail.gmail_service.send_draft", return_value={"id": "msg_sent2"}),
    ):
        resp = client.post(
            f"{BASE}/{eid}/approve-draft",
            json={"edit_body": "Edited reply text"},
            headers=auth_headers,
        )
    assert resp.status_code == 200
    assert resp.json()["ai_draft"] == "Edited reply text"
    assert resp.json()["status"] == "replied"


def test_approve_draft_send_failure(client, auth_headers):
    eid = _insert_email(status=EmailStatus.DRAFT_READY, gmail_draft_id="drf_fail")
    with (
        patch("app.routers.gmail.gmail_service.get_gmail_service", return_value=MagicMock()),
        patch("app.routers.gmail.gmail_service.send_draft", side_effect=Exception("Gmail API down")),
    ):
        resp = client.post(f"{BASE}/{eid}/approve-draft", json={}, headers=auth_headers)
    assert resp.status_code == 500
    assert "Failed to send draft" in resp.json()["detail"]


def test_approve_draft_no_auth(client):
    eid = _insert_email(status=EmailStatus.DRAFT_READY, gmail_draft_id="drf_auth")
    with _no_auth(client):
        resp = client.post(f"{BASE}/{eid}/approve-draft", json={})
    assert resp.status_code == 401


# ── POST /{id}/discard-draft ──────────────────────────────────────────────────

def test_discard_draft_success(client, auth_headers):
    eid = _insert_email(
        status=EmailStatus.DRAFT_READY,
        gmail_draft_id="drf_discard",
        ai_draft="Some draft",
        needs_human=False,
    )
    mock_svc = MagicMock()
    mock_svc.users.return_value.drafts.return_value.delete.return_value.execute.return_value = {}
    with patch("app.routers.gmail.gmail_service.get_gmail_service", return_value=mock_svc):
        resp = client.post(f"{BASE}/{eid}/discard-draft", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["gmail_draft_id"] is None
    assert body["ai_draft"] is None
    assert body["needs_human"] is True
    assert body["status"] == "pending_human"


def test_discard_draft_no_existing_draft_id(client, auth_headers):
    eid = _insert_email(status=EmailStatus.CLASSIFIED, gmail_draft_id=None)
    resp = client.post(f"{BASE}/{eid}/discard-draft", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["needs_human"] is True


def test_discard_draft_not_found(client, auth_headers):
    resp = client.post(f"{BASE}/{uuid.uuid4()}/discard-draft", headers=auth_headers)
    assert resp.status_code == 404


def test_discard_draft_no_auth(client):
    eid = _insert_email()
    with _no_auth(client):
        resp = client.post(f"{BASE}/{eid}/discard-draft")
    assert resp.status_code == 401


# ── POST /send ────────────────────────────────────────────────────────────────

def test_send_email_success(client, auth_headers):
    with (
        patch("app.routers.gmail.gmail_service.get_gmail_service", return_value=MagicMock()),
        patch("app.routers.gmail.gmail_service.send_email", return_value={"id": f"msg_{uuid.uuid4().hex}", "threadId": "th_001"}),
    ):
        resp = client.post(
            f"{BASE}/send",
            json={"to": "customer@example.com", "subject": "Hello", "body": "Test body"},
            headers=auth_headers,
        )
    assert resp.status_code == 201
    body = resp.json()
    assert body["direction"] == "outbound"
    assert body["recipients"] == ["customer@example.com"]
    assert body["status"] == "replied"
    assert body["label"] == "Sales"


def test_send_email_with_thread_id(client, auth_headers):
    with (
        patch("app.routers.gmail.gmail_service.get_gmail_service", return_value=MagicMock()),
        patch("app.routers.gmail.gmail_service.send_email", return_value={"id": f"msg_{uuid.uuid4().hex}", "threadId": "th_reply"}),
    ):
        resp = client.post(
            f"{BASE}/send",
            json={"to": "c@example.com", "subject": "Re: Q", "body": "Reply", "thread_id": "th_reply"},
            headers=auth_headers,
        )
    assert resp.status_code == 201
    assert resp.json()["gmail_thread_id"] == "th_reply"


def test_send_email_missing_subject(client, auth_headers):
    resp = client.post(f"{BASE}/send", json={"to": "x@x.com", "body": "hi"}, headers=auth_headers)
    assert resp.status_code == 422


def test_send_email_missing_body(client, auth_headers):
    resp = client.post(f"{BASE}/send", json={"to": "x@x.com", "subject": "hi"}, headers=auth_headers)
    assert resp.status_code == 422


def test_send_email_missing_to(client, auth_headers):
    resp = client.post(f"{BASE}/send", json={"subject": "hi", "body": "body"}, headers=auth_headers)
    assert resp.status_code == 422


def test_send_email_gmail_failure(client, auth_headers):
    with (
        patch("app.routers.gmail.gmail_service.get_gmail_service", return_value=MagicMock()),
        patch("app.routers.gmail.gmail_service.send_email", side_effect=Exception("network error")),
    ):
        resp = client.post(
            f"{BASE}/send",
            json={"to": "x@x.com", "subject": "hi", "body": "body"},
            headers=auth_headers,
        )
    assert resp.status_code == 500
    assert "Failed to send email" in resp.json()["detail"]


def test_send_email_no_auth(client):
    with _no_auth(client):
        resp = client.post(f"{BASE}/send", json={"to": "x@x.com", "subject": "hi", "body": "body"})
    assert resp.status_code == 401


# ── Email router service unit tests ──────────────────────────────────────────

def _classify_as(label: EmailLabel, transactional_type=None, transactional_data=None) -> dict:
    return {
        "label": label,
        "confidence": "high",
        "reasoning": "test",
        "transactional_type": transactional_type,
        "transactional_data": transactional_data,
    }


def test_process_inbound_idempotent():
    from app.services.email_router_service import process_inbound_email
    mid = f"test_{uuid.uuid4().hex}"
    with (
        patch("app.services.email_router_service.gmail_service.get_gmail_service", return_value=_mock_gmail_svc()),
        patch("app.services.email_router_service.gmail_service.apply_label_to_message"),
        patch("app.services.email_router_service.gmail_service.mark_as_read"),
        patch("app.services.email_router_service.gmail_service.archive_message"),
        patch("app.services.email_router_service.classify_email", return_value=_classify_as(EmailLabel.PERSONAL)),
    ):
        with SessionLocal() as db:
            r1 = process_inbound_email(db, _raw_msg(gmail_id=mid))
            r2 = process_inbound_email(db, _raw_msg(gmail_id=mid))
    assert r1 is not None
    assert r2 is None


def test_process_inbound_sales_sends_and_logs_gaps():
    """Even when gaps exist the reply is sent immediately; gaps logged for dashboard."""
    from app.services.email_router_service import process_inbound_email
    mid = f"test_{uuid.uuid4().hex}"
    draft_with_gaps = "Dear Customer, the price is Rs 5799. Our team will confirm the lead time and follow up shortly.\n\nWould you like to schedule a call?"
    with (
        patch("app.services.email_router_service.gmail_service.get_gmail_service", return_value=_mock_gmail_svc()),
        patch("app.services.email_router_service.gmail_service.apply_label_to_message"),
        patch("app.services.email_router_service.gmail_service.mark_as_read"),
        patch("app.services.email_router_service.gmail_service.create_draft", return_value={"id": "drf_new"}),
        patch("app.services.email_router_service.gmail_service.send_draft"),
        patch("app.services.email_router_service.classify_email", return_value=_classify_as(EmailLabel.SALES)),
        patch("app.services.email_router_service._generate_sales_draft", return_value=draft_with_gaps),
    ):
        with SessionLocal() as db:
            result = process_inbound_email(db, _raw_msg(gmail_id=mid))
    assert result.label == EmailLabel.SALES
    assert result.status == EmailStatus.REPLIED      # always sent now
    assert result.gmail_draft_id is None             # cleared after send
    assert result.followup_gaps                      # gaps still logged for dashboard


def test_process_inbound_sales_autosends_when_complete():
    """Email sent immediately when RAG answered all questions."""
    from app.services.email_router_service import process_inbound_email
    mid = f"test_{uuid.uuid4().hex}"
    complete_draft = "Dear Customer, the price is Rs 5799 and it is available immediately.\n\nWould you like to schedule a call?"
    with (
        patch("app.services.email_router_service.gmail_service.get_gmail_service", return_value=_mock_gmail_svc()),
        patch("app.services.email_router_service.gmail_service.apply_label_to_message"),
        patch("app.services.email_router_service.gmail_service.mark_as_read"),
        patch("app.services.email_router_service.gmail_service.create_draft", return_value={"id": "drf_sent"}),
        patch("app.services.email_router_service.gmail_service.send_draft"),
        patch("app.services.email_router_service.classify_email", return_value=_classify_as(EmailLabel.SALES)),
        patch("app.services.email_router_service._generate_sales_draft", return_value=complete_draft),
    ):
        with SessionLocal() as db:
            result = process_inbound_email(db, _raw_msg(gmail_id=mid))
    assert result.label == EmailLabel.SALES
    assert result.status == EmailStatus.REPLIED
    assert result.gmail_draft_id is None  # cleared after send
    assert not result.followup_gaps


def test_process_inbound_sales_empty_draft_flags_human():
    from app.services.email_router_service import process_inbound_email
    mid = f"test_{uuid.uuid4().hex}"
    with (
        patch("app.services.email_router_service.gmail_service.get_gmail_service", return_value=_mock_gmail_svc()),
        patch("app.services.email_router_service.gmail_service.apply_label_to_message"),
        patch("app.services.email_router_service.gmail_service.mark_as_read"),
        patch("app.services.email_router_service.classify_email", return_value=_classify_as(EmailLabel.SALES)),
        patch("app.services.email_router_service._generate_sales_draft", return_value=""),
    ):
        with SessionLocal() as db:
            result = process_inbound_email(db, _raw_msg(gmail_id=mid))
    assert result.needs_human is True
    assert result.status == EmailStatus.PENDING_HUMAN


def test_process_inbound_support_acks_and_flags_human():
    """Support emails get an immediate acknowledgment reply + flagged for human follow-up."""
    from app.services.email_router_service import process_inbound_email
    mid = f"test_{uuid.uuid4().hex}"
    with (
        patch("app.services.email_router_service.gmail_service.get_gmail_service", return_value=_mock_gmail_svc()),
        patch("app.services.email_router_service.gmail_service.apply_label_to_message"),
        patch("app.services.email_router_service.gmail_service.mark_as_read"),
        patch("app.services.email_router_service.gmail_service.send_email", return_value={"id": f"msg_{uuid.uuid4().hex}"}),
        patch("app.services.email_router_service.classify_email", return_value=_classify_as(EmailLabel.SUPPORT)),
    ):
        with SessionLocal() as db:
            result = process_inbound_email(db, _raw_msg(gmail_id=mid))
    assert result.needs_human is True
    assert result.status == EmailStatus.PENDING_HUMAN
    assert result.label == EmailLabel.SUPPORT
    assert result.ai_draft  # acknowledgment stored


def test_process_inbound_grievance_acks_and_flags_human():
    """Grievance emails get an immediate apology acknowledgment + flagged for human follow-up."""
    from app.services.email_router_service import process_inbound_email
    mid = f"test_{uuid.uuid4().hex}"
    with (
        patch("app.services.email_router_service.gmail_service.get_gmail_service", return_value=_mock_gmail_svc()),
        patch("app.services.email_router_service.gmail_service.apply_label_to_message"),
        patch("app.services.email_router_service.gmail_service.mark_as_read"),
        patch("app.services.email_router_service.gmail_service.send_email", return_value={"id": f"msg_{uuid.uuid4().hex}"}),
        patch("app.services.email_router_service.classify_email", return_value=_classify_as(EmailLabel.GRIEVANCE)),
    ):
        with SessionLocal() as db:
            result = process_inbound_email(db, _raw_msg(gmail_id=mid))
    assert result.needs_human is True
    assert result.label == EmailLabel.GRIEVANCE
    assert result.ai_draft  # apology acknowledgment stored


def test_process_inbound_promotional_ignored():
    from app.services.email_router_service import process_inbound_email
    mid = f"test_{uuid.uuid4().hex}"
    with (
        patch("app.services.email_router_service.gmail_service.get_gmail_service", return_value=_mock_gmail_svc()),
        patch("app.services.email_router_service.gmail_service.apply_label_to_message"),
        patch("app.services.email_router_service.gmail_service.mark_as_read"),
        patch("app.services.email_router_service.gmail_service.archive_message"),
        patch("app.services.email_router_service.classify_email", return_value=_classify_as(EmailLabel.PROMOTIONAL)),
    ):
        with SessionLocal() as db:
            result = process_inbound_email(db, _raw_msg(gmail_id=mid))
    assert result.status == EmailStatus.IGNORED
    assert result.label == EmailLabel.PROMOTIONAL


def test_process_inbound_personal_ignored():
    from app.services.email_router_service import process_inbound_email
    mid = f"test_{uuid.uuid4().hex}"
    with (
        patch("app.services.email_router_service.gmail_service.get_gmail_service", return_value=_mock_gmail_svc()),
        patch("app.services.email_router_service.gmail_service.apply_label_to_message"),
        patch("app.services.email_router_service.gmail_service.mark_as_read"),
        patch("app.services.email_router_service.gmail_service.archive_message"),
        patch("app.services.email_router_service.classify_email", return_value=_classify_as(EmailLabel.PERSONAL)),
    ):
        with SessionLocal() as db:
            result = process_inbound_email(db, _raw_msg(gmail_id=mid))
    assert result.status == EmailStatus.IGNORED


def test_process_inbound_transactional_archived():
    from app.services.email_router_service import process_inbound_email
    mid = f"test_{uuid.uuid4().hex}"
    t_data = {"amount": "₹5000", "reference_number": "INV-001", "due_date": None, "vendor": "Acme"}
    with (
        patch("app.services.email_router_service.gmail_service.get_gmail_service", return_value=_mock_gmail_svc()),
        patch("app.services.email_router_service.gmail_service.apply_label_to_message"),
        patch("app.services.email_router_service.gmail_service.mark_as_read"),
        patch("app.services.email_router_service.gmail_service.archive_message"),
        patch(
            "app.services.email_router_service.classify_email",
            return_value=_classify_as(EmailLabel.TRANSACTIONAL, "invoice", t_data),
        ),
    ):
        with SessionLocal() as db:
            result = process_inbound_email(db, _raw_msg(gmail_id=mid))
    assert result.status == EmailStatus.ARCHIVED
    assert result.transactional_type == "invoice"
    assert result.transactional_data["amount"] == "₹5000"


def test_process_inbound_no_lead_match():
    from app.services.email_router_service import process_inbound_email
    mid = f"test_{uuid.uuid4().hex}"
    unknown_sender = f"unknown_{uuid.uuid4().hex}@example.com"
    with (
        patch("app.services.email_router_service.gmail_service.get_gmail_service", return_value=_mock_gmail_svc()),
        patch("app.services.email_router_service.gmail_service.apply_label_to_message"),
        patch("app.services.email_router_service.gmail_service.mark_as_read"),
        patch("app.services.email_router_service.gmail_service.archive_message"),
        patch("app.services.email_router_service.classify_email", return_value=_classify_as(EmailLabel.PERSONAL)),
    ):
        with SessionLocal() as db:
            result = process_inbound_email(db, _raw_msg(gmail_id=mid, sender=unknown_sender))
    assert result.lead_id is None


def test_process_inbound_persists_classifier_fields():
    from app.services.email_router_service import process_inbound_email
    mid = f"test_{uuid.uuid4().hex}"
    with (
        patch("app.services.email_router_service.gmail_service.get_gmail_service", return_value=_mock_gmail_svc()),
        patch("app.services.email_router_service.gmail_service.apply_label_to_message"),
        patch("app.services.email_router_service.gmail_service.mark_as_read"),
        patch("app.services.email_router_service.gmail_service.archive_message"),
        patch("app.services.email_router_service.classify_email", return_value={
            "label": EmailLabel.PERSONAL,
            "confidence": "medium",
            "reasoning": "Looks like a greeting",
            "transactional_type": None,
            "transactional_data": None,
        }),
    ):
        with SessionLocal() as db:
            result = process_inbound_email(db, _raw_msg(gmail_id=mid))
    assert result.classifier_confidence == "medium"
    assert result.classifier_reasoning == "Looks like a greeting"


# ── Gmail service unit tests ──────────────────────────────────────────────────

def test_parse_message_plain_text():
    from app.services.gmail_service import parse_message
    raw = _raw_msg(gmail_id="x123", subject="Plain subject", body="Hello world", sender="John <john@example.com>")
    parsed = parse_message(raw)
    assert parsed["gmail_message_id"] == "x123"
    assert parsed["subject"] == "Plain subject"
    assert parsed["sender"] == "John <john@example.com>"
    assert "developer20@rdltech.in" in parsed["recipients"]
    assert "Hello world" in parsed["body_text"]
    assert parsed["body_html"] == ""


def test_parse_message_multipart():
    from app.services.gmail_service import parse_message
    plain_b64 = base64.urlsafe_b64encode(b"Plain part").decode()
    html_b64 = base64.urlsafe_b64encode(b"<b>HTML part</b>").decode()
    raw = {
        "id": "multi_01",
        "threadId": "th_multi",
        "payload": {
            "mimeType": "multipart/alternative",
            "headers": [
                {"name": "From", "value": "a@b.com"},
                {"name": "To", "value": "r@r.com"},
                {"name": "Subject", "value": "Multi"},
                {"name": "Date", "value": "Mon, 21 Apr 2026 10:00:00 +0000"},
            ],
            "body": {},
            "parts": [
                {"mimeType": "text/plain", "body": {"data": plain_b64}},
                {"mimeType": "text/html", "body": {"data": html_b64}},
            ],
        },
    }
    parsed = parse_message(raw)
    assert "Plain part" in parsed["body_text"]
    assert "<b>HTML part</b>" in parsed["body_html"]


def test_parse_message_missing_headers():
    from app.services.gmail_service import parse_message
    raw = {
        "id": "no_hdr",
        "threadId": None,
        "payload": {"mimeType": "text/plain", "headers": [], "body": {}},
    }
    parsed = parse_message(raw)
    assert parsed["sender"] == ""
    assert parsed["subject"] == ""
    assert parsed["recipients"] == []
    assert parsed["body_text"] == ""


def test_parse_message_multiple_recipients():
    from app.services.gmail_service import parse_message
    data = base64.urlsafe_b64encode(b"hi").decode()
    raw = {
        "id": "multi_rcpt",
        "threadId": "th_x",
        "payload": {
            "mimeType": "text/plain",
            "headers": [
                {"name": "From", "value": "a@b.com"},
                {"name": "To", "value": "x@x.com, y@y.com"},
                {"name": "Subject", "value": "Multi"},
                {"name": "Date", "value": "Mon, 21 Apr 2026 10:00:00 +0000"},
            ],
            "body": {"data": data},
        },
    }
    parsed = parse_message(raw)
    assert "x@x.com" in parsed["recipients"]
    assert "y@y.com" in parsed["recipients"]


def test_extract_email_address_angle_brackets():
    from app.services.gmail_service import extract_email_address
    assert extract_email_address("John Doe <john@example.com>") == "john@example.com"


def test_extract_email_address_plain():
    from app.services.gmail_service import extract_email_address
    assert extract_email_address("plain@example.com") == "plain@example.com"


def test_extract_email_address_strips_whitespace():
    from app.services.gmail_service import extract_email_address
    assert extract_email_address("  spaced@example.com  ") == "spaced@example.com"


def test_extract_email_address_bare_angle_brackets():
    from app.services.gmail_service import extract_email_address
    assert extract_email_address("<bare@example.com>") == "bare@example.com"


def test_decode_data_valid():
    from app.services.gmail_service import _decode_data
    encoded = base64.urlsafe_b64encode(b"Hello world").decode()
    assert _decode_data(encoded) == "Hello world"


def test_decode_data_empty():
    from app.services.gmail_service import _decode_data
    assert _decode_data("") == ""


def test_decode_data_invalid_does_not_raise():
    from app.services.gmail_service import _decode_data
    result = _decode_data("not_valid_base64!!!")
    assert isinstance(result, str)


def test_decode_data_unicode():
    from app.services.gmail_service import _decode_data
    encoded = base64.urlsafe_b64encode("नमस्ते".encode("utf-8")).decode()
    assert "नमस्ते" in _decode_data(encoded)


def test_extract_body_plain():
    from app.services.gmail_service import _extract_body
    data = base64.urlsafe_b64encode(b"Plain text").decode()
    text, html = _extract_body({"mimeType": "text/plain", "body": {"data": data}})
    assert text == "Plain text"
    assert html == ""


def test_extract_body_html():
    from app.services.gmail_service import _extract_body
    data = base64.urlsafe_b64encode(b"<p>HTML</p>").decode()
    text, html = _extract_body({"mimeType": "text/html", "body": {"data": data}})
    assert text == ""
    assert html == "<p>HTML</p>"


def test_extract_body_multipart():
    from app.services.gmail_service import _extract_body
    plain_b64 = base64.urlsafe_b64encode(b"plain content").decode()
    html_b64 = base64.urlsafe_b64encode(b"<div>html</div>").decode()
    payload = {
        "mimeType": "multipart/alternative",
        "body": {},
        "parts": [
            {"mimeType": "text/plain", "body": {"data": plain_b64}},
            {"mimeType": "text/html", "body": {"data": html_b64}},
        ],
    }
    text, html = _extract_body(payload)
    assert text == "plain content"
    assert html == "<div>html</div>"


def test_extract_body_nested_multipart():
    from app.services.gmail_service import _extract_body
    inner_b64 = base64.urlsafe_b64encode(b"inner text").decode()
    payload = {
        "mimeType": "multipart/mixed",
        "body": {},
        "parts": [{
            "mimeType": "multipart/alternative",
            "body": {},
            "parts": [{"mimeType": "text/plain", "body": {"data": inner_b64}}],
        }],
    }
    text, _ = _extract_body(payload)
    assert text == "inner text"


def test_extract_body_empty_payload():
    from app.services.gmail_service import _extract_body
    text, html = _extract_body({"mimeType": "text/plain", "body": {}})
    assert text == ""
    assert html == ""


def test_build_mime_encodes_all_fields():
    from app.services.gmail_service import _build_mime
    raw = _build_mime("to@example.com", "Test Subject", "Body content")
    decoded = base64.urlsafe_b64decode(raw + "==").decode("utf-8", errors="replace")
    assert "to@example.com" in decoded
    assert "Test Subject" in decoded
    assert "Body content" in decoded


# ── Classifier unit tests ─────────────────────────────────────────────────────

def _mock_llm_response(content: str):
    r = MagicMock()
    r.content = content
    return r


def test_classifier_sales_label():
    from app.models.communication import EmailLabel
    from app.services.email_classifier_service import classify_email
    with patch("app.services.email_classifier_service._build_llm") as m:
        m.return_value.invoke.return_value = _mock_llm_response(
            '{"label": "Sales", "confidence": "high", "reasoning": "Product inquiry", "transactional_type": null, "transactional_data": null}'
        )
        result = classify_email("RFQ for IoT Kit", "Please quote.", "buyer@corp.com")
    assert result["label"] == EmailLabel.SALES
    assert result["confidence"] == "high"


def test_classifier_support_label():
    from app.models.communication import EmailLabel
    from app.services.email_classifier_service import classify_email
    with patch("app.services.email_classifier_service._build_llm") as m:
        m.return_value.invoke.return_value = _mock_llm_response(
            '{"label": "Support", "confidence": "medium", "reasoning": "Technical issue", "transactional_type": null, "transactional_data": null}'
        )
        result = classify_email("Device not working", "Sensor giving wrong readings.", "user@corp.com")
    assert result["label"] == EmailLabel.SUPPORT


def test_classifier_grievance_label():
    from app.models.communication import EmailLabel
    from app.services.email_classifier_service import classify_email
    with patch("app.services.email_classifier_service._build_llm") as m:
        m.return_value.invoke.return_value = _mock_llm_response(
            '{"label": "Grievance", "confidence": "high", "reasoning": "Complaint", "transactional_type": null, "transactional_data": null}'
        )
        result = classify_email("Terrible service", "I want a refund.", "angry@corp.com")
    assert result["label"] == EmailLabel.GRIEVANCE


def test_classifier_promotional_label():
    from app.models.communication import EmailLabel
    from app.services.email_classifier_service import classify_email
    with patch("app.services.email_classifier_service._build_llm") as m:
        m.return_value.invoke.return_value = _mock_llm_response(
            '{"label": "Promotional", "confidence": "high", "reasoning": "Newsletter", "transactional_type": null, "transactional_data": null}'
        )
        result = classify_email("Weekly Digest", "Check our latest offers.", "news@brand.com")
    assert result["label"] == EmailLabel.PROMOTIONAL


def test_classifier_transactional_with_type_and_data():
    from app.models.communication import EmailLabel
    from app.services.email_classifier_service import classify_email
    with patch("app.services.email_classifier_service._build_llm") as m:
        m.return_value.invoke.return_value = _mock_llm_response(
            '{"label": "Transactional", "confidence": "high", "reasoning": "Invoice received", '
            '"transactional_type": "invoice", "transactional_data": {"amount": "5000", "reference_number": "INV-001", "due_date": null, "vendor": "Acme Corp"}}'
        )
        result = classify_email("Invoice #INV-001", "Please find invoice.", "billing@acme.com")
    assert result["label"] == EmailLabel.TRANSACTIONAL
    assert result["transactional_type"] == "invoice"
    assert result["transactional_data"]["amount"] == "5000"
    assert result["transactional_data"]["vendor"] == "Acme Corp"


def test_classifier_strips_markdown_code_fence():
    from app.models.communication import EmailLabel
    from app.services.email_classifier_service import classify_email
    with patch("app.services.email_classifier_service._build_llm") as m:
        m.return_value.invoke.return_value = _mock_llm_response(
            '```json\n{"label": "Promotional", "confidence": "high", "reasoning": "Newsletter", "transactional_type": null, "transactional_data": null}\n```'
        )
        result = classify_email("Weekly Digest", "Check offers.", "news@brand.com")
    assert result["label"] == EmailLabel.PROMOTIONAL


def test_classifier_malformed_json_regex_fallback():
    from app.models.communication import EmailLabel
    from app.services.email_classifier_service import classify_email
    # Unescaped quote in reasoning breaks JSON — regex fallback should still extract label
    with patch("app.services.email_classifier_service._build_llm") as m:
        m.return_value.invoke.return_value = _mock_llm_response(
            '{"label": "Sales", "confidence": "high", "reasoning": "Subject line: "Meeting records" is a sales inquiry", "transactional_type": null}'
        )
        result = classify_email("Meeting records", "Body", "x@x.com")
    assert result["label"] == EmailLabel.SALES
    assert result["confidence"] == "high"


def test_classifier_unknown_label_becomes_unclassified():
    from app.models.communication import EmailLabel
    from app.services.email_classifier_service import classify_email
    with patch("app.services.email_classifier_service._build_llm") as m:
        m.return_value.invoke.return_value = _mock_llm_response(
            '{"label": "Spam", "confidence": "low", "reasoning": "Unknown category", "transactional_type": null, "transactional_data": null}'
        )
        result = classify_email("Hi", "Body", "x@x.com")
    assert result["label"] == EmailLabel.UNCLASSIFIED


def test_classifier_llm_error_returns_unclassified():
    from app.models.communication import EmailLabel
    from app.services.email_classifier_service import classify_email
    with patch("app.services.email_classifier_service._build_llm") as m:
        m.return_value.invoke.side_effect = Exception("Network timeout")
        result = classify_email("Subject", "Body", "x@x.com")
    assert result["label"] == EmailLabel.UNCLASSIFIED
    assert result["confidence"] == "low"


def test_classifier_sanitizes_double_quotes_in_subject():
    from app.models.communication import EmailLabel
    from app.services.email_classifier_service import classify_email
    with patch("app.services.email_classifier_service._build_llm") as m:
        m.return_value.invoke.return_value = _mock_llm_response(
            '{"label": "Sales", "confidence": "high", "reasoning": "Sales inquiry", "transactional_type": null, "transactional_data": null}'
        )
        result = classify_email(
            subject='Meeting records: "S7.Net Handover"',
            body="Please find attached.",
            sender="a@b.com",
        )
    # Verify double quotes were replaced before being sent to LLM
    call_args = m.return_value.invoke.call_args
    user_msg_content = call_args[0][0][1].content
    assert '"S7.Net Handover"' not in user_msg_content
    assert "'S7.Net Handover'" in user_msg_content
    assert result["label"] == EmailLabel.SALES


def test_classifier_low_confidence_preserved():
    from app.models.communication import EmailLabel
    from app.services.email_classifier_service import classify_email
    with patch("app.services.email_classifier_service._build_llm") as m:
        m.return_value.invoke.return_value = _mock_llm_response(
            '{"label": "Personal", "confidence": "low", "reasoning": "Ambiguous message", "transactional_type": null, "transactional_data": null}'
        )
        result = classify_email("Hello", "Hi there!", "friend@example.com")
    assert result["confidence"] == "low"
    assert result["label"] == EmailLabel.PERSONAL


# ── Auto lead creation from Sales emails (#1) ─────────────────────────────────

def _classify_sales():
    return {
        "label": EmailLabel.SALES,
        "confidence": "high",
        "reasoning": "Sales inquiry",
        "transactional_type": None,
        "transactional_data": None,
        "competitor_mention": None,
    }


def _apply_sales_patches(stack, draft="Dear Customer, the price is Rs 5799.", extra_patches=None):
    """Enter all standard Sales email mocks into an ExitStack. Returns list of entered contexts."""
    all_patches = [
        patch("app.services.email_router_service.gmail_service.get_gmail_service", return_value=_mock_gmail_svc()),
        patch("app.services.email_router_service.gmail_service.apply_label_to_message"),
        patch("app.services.email_router_service.gmail_service.mark_as_read"),
        patch("app.services.email_router_service.gmail_service.create_draft", return_value={"id": "drf_x"}),
        patch("app.services.email_router_service.gmail_service.send_draft"),
        patch("app.services.email_router_service.classify_email", return_value=_classify_sales()),
        patch("app.services.email_router_service._generate_sales_draft", return_value=draft),
        patch("app.services.email_router_service.extract_structured_gaps", return_value=[]),
        patch("app.services.email_router_service.detect_product", return_value=(None, None)),
    ] + (extra_patches or [])
    return [stack.enter_context(p) for p in all_patches]


def test_sales_email_auto_creates_lead_for_unknown_sender():
    """Sales email from an unknown address → lead is auto-created with email_row.lead_id set."""
    from contextlib import ExitStack
    from app.services.email_router_service import process_inbound_email
    from app.models.leads import Lead
    unique_email = f"newcustomer_{uuid.uuid4().hex[:8]}@company.com"
    mid = f"test_{uuid.uuid4().hex}"
    captured_lead_id = {}

    with ExitStack() as stack:
        _apply_sales_patches(stack)
        with SessionLocal() as db:
            result = process_inbound_email(
                db, _raw_msg(gmail_id=mid, sender=f"New Customer <{unique_email}>")
            )
            # Read inside session before detach
            captured_lead_id["id"] = result.lead_id
            assert result is not None
            assert result.lead_id is not None, "lead_id must be set for Sales email"

    with SessionLocal() as db:
        lead = db.query(Lead).filter(Lead.email == unique_email).first()
    assert lead is not None
    assert str(captured_lead_id["id"]) == str(lead.id)


def test_sales_email_reuses_existing_lead():
    """Sales email from a known address → existing lead reused, no duplicate created."""
    from contextlib import ExitStack
    from app.services.email_router_service import process_inbound_email
    from app.models.leads import Lead
    unique_email = f"existing_{uuid.uuid4().hex[:8]}@company.com"

    with SessionLocal() as db:
        existing_lead = Lead(name="Existing", email=unique_email,
                             status="Contacted", interest_level="Hot", engagement_score=50)
        db.add(existing_lead); db.commit()
        existing_id = existing_lead.id

    mid = f"test_{uuid.uuid4().hex}"
    captured = {}
    with ExitStack() as stack:
        _apply_sales_patches(stack)
        with SessionLocal() as db:
            result = process_inbound_email(
                db, _raw_msg(gmail_id=mid, sender=f"Existing Customer <{unique_email}>")
            )
            captured["lead_id"] = result.lead_id

    assert str(captured["lead_id"]) == str(existing_id)

    with SessionLocal() as db:
        count = db.query(Lead).filter(Lead.email == unique_email).count()
    assert count == 1, "Must not create a duplicate lead"


def test_support_email_does_not_auto_create_lead():
    """Non-Sales emails must NOT create a lead if sender is unknown."""
    from app.services.email_router_service import process_inbound_email
    from app.models.leads import Lead
    unique_email = f"support_unknown_{uuid.uuid4().hex[:8]}@company.com"
    mid = f"test_{uuid.uuid4().hex}"

    with (
        patch("app.services.email_router_service.gmail_service.get_gmail_service", return_value=_mock_gmail_svc()),
        patch("app.services.email_router_service.gmail_service.apply_label_to_message"),
        patch("app.services.email_router_service.gmail_service.mark_as_read"),
        patch("app.services.email_router_service.gmail_service.send_email", return_value={"id": "msg_x"}),
        patch("app.services.email_router_service.classify_email", return_value={
            "label": EmailLabel.SUPPORT, "confidence": "high", "reasoning": "Support",
            "transactional_type": None, "transactional_data": None, "competitor_mention": None,
        }),
    ):
        with SessionLocal() as db:
            result = process_inbound_email(
                db, _raw_msg(gmail_id=mid, sender=f"Unknown Support <{unique_email}>")
            )

    assert result.label == EmailLabel.SUPPORT
    with SessionLocal() as db:
        lead = db.query(Lead).filter(Lead.email == unique_email).first()
    assert lead is None


# ── Drip sequence auto-start for new leads (#8) ───────────────────────────────

def test_drip_sequence_started_for_new_lead():
    """Brand-new lead from a Sales email → drip sequence is created."""
    from contextlib import ExitStack
    from app.services.email_router_service import process_inbound_email
    unique_email = f"drip_new_{uuid.uuid4().hex[:8]}@company.com"
    mid = f"test_{uuid.uuid4().hex}"

    with ExitStack() as stack:
        _apply_sales_patches(stack)
        mock_seq = stack.enter_context(
            patch("app.services.email_sequence_service.create_sequence")
        )
        with SessionLocal() as db:
            process_inbound_email(
                db, _raw_msg(gmail_id=mid, sender=f"Drip New <{unique_email}>")
            )

    mock_seq.assert_called_once()


def test_drip_sequence_not_started_for_existing_lead():
    """Existing lead receiving a Sales email must NOT trigger a new drip sequence."""
    from contextlib import ExitStack
    from app.services.email_router_service import process_inbound_email
    from app.models.leads import Lead
    unique_email = f"drip_existing_{uuid.uuid4().hex[:8]}@company.com"

    with SessionLocal() as db:
        lead = Lead(name="Old Customer", email=unique_email,
                    status="Contacted", interest_level="Warm", engagement_score=40)
        db.add(lead); db.commit()

    mid = f"test_{uuid.uuid4().hex}"
    with ExitStack() as stack:
        _apply_sales_patches(stack)
        mock_seq = stack.enter_context(
            patch("app.services.email_sequence_service.create_sequence")
        )
        with SessionLocal() as db:
            process_inbound_email(
                db, _raw_msg(gmail_id=mid, sender=f"Old Customer <{unique_email}>")
            )

    mock_seq.assert_not_called()


def test_drip_sequence_failure_does_not_crash():
    """If drip sequence creation raises, the email must still be processed successfully."""
    from contextlib import ExitStack
    from app.services.email_router_service import process_inbound_email
    unique_email = f"drip_fail_{uuid.uuid4().hex[:8]}@company.com"
    mid = f"test_{uuid.uuid4().hex}"

    with ExitStack() as stack:
        _apply_sales_patches(stack)
        stack.enter_context(
            patch("app.services.email_sequence_service.create_sequence", side_effect=Exception("DB error"))
        )
        with SessionLocal() as db:
            result = process_inbound_email(
                db, _raw_msg(gmail_id=mid, sender=f"Fail Customer <{unique_email}>")
            )

    assert result is not None
    assert result.label == EmailLabel.SALES


# ── Resolution confirmation email (#3 / #9) ───────────────────────────────────

def test_resolve_email_sends_confirmation_to_customer(client, auth_headers):
    """Resolving a Support/Grievance email sends a confirmation reply to the customer."""
    eid = _insert_email(
        label=EmailLabel.SUPPORT,
        status=EmailStatus.PENDING_HUMAN,
        needs_human=True,
        sender="customer@example.com",
        subject="My support request",
    )
    with patch("app.routers.gmail.gmail_service.get_gmail_service", return_value=_mock_gmail_svc()) as _:
        with patch("app.routers.gmail.gmail_service.send_email") as mock_send:
            resp = client.post(
                f"{BASE}/{eid}/resolve",
                json={"resolved_by": "agent@rdltech.in"},
                headers=auth_headers,
            )

    assert resp.status_code == 200
    assert resp.json()["status"] == "replied"
    assert resp.json()["needs_human"] is False
    mock_send.assert_called_once()
    # Confirm reply was addressed to the customer
    call_kwargs = mock_send.call_args.kwargs
    assert call_kwargs.get("to") == "customer@example.com"


def test_resolve_email_confirmation_includes_note(client, auth_headers):
    """Resolution note must appear in the confirmation email body."""
    eid = _insert_email(
        label=EmailLabel.GRIEVANCE,
        status=EmailStatus.PENDING_HUMAN,
        needs_human=True,
        sender="upset@example.com",
        subject="My grievance",
    )
    resolution_note = "We have replaced the unit and dispatched a replacement."

    with patch("app.routers.gmail.gmail_service.get_gmail_service", return_value=_mock_gmail_svc()):
        with patch("app.routers.gmail.gmail_service.send_email") as mock_send:
            resp = client.post(
                f"{BASE}/{eid}/resolve",
                json={"resolved_by": "agent@rdltech.in", "note": resolution_note},
                headers=auth_headers,
            )

    assert resp.status_code == 200
    body_sent = mock_send.call_args.kwargs.get("body", "")
    assert resolution_note in body_sent


def test_resolve_email_confirmation_failure_does_not_crash(client, auth_headers):
    """If the confirmation email send fails, the resolve must still succeed (200)."""
    eid = _insert_email(
        label=EmailLabel.SUPPORT,
        status=EmailStatus.PENDING_HUMAN,
        needs_human=True,
        sender="failsend@example.com",
        subject="Support request",
    )
    with patch("app.routers.gmail.gmail_service.get_gmail_service", return_value=_mock_gmail_svc()):
        with patch("app.routers.gmail.gmail_service.send_email", side_effect=Exception("SMTP error")):
            resp = client.post(
                f"{BASE}/{eid}/resolve",
                json={"resolved_by": "agent@rdltech.in"},
                headers=auth_headers,
            )

    assert resp.status_code == 200
    assert resp.json()["status"] == "replied"


def test_resolve_email_not_found(client, auth_headers):
    resp = client.post(
        f"{BASE}/{uuid.uuid4()}/resolve",
        json={"resolved_by": "agent@rdltech.in"},
        headers=auth_headers,
    )
    assert resp.status_code == 404


def test_resolve_email_no_auth(client):
    eid = _insert_email(label=EmailLabel.SUPPORT, status=EmailStatus.PENDING_HUMAN, needs_human=True)
    with _no_auth(client):
        resp = client.post(f"{BASE}/{eid}/resolve", json={"resolved_by": "x@x.com"})
    assert resp.status_code == 401


# ── GET /analytics ─────────────────────────────────────────────────────────────

def test_analytics_response_shape(client, auth_headers):
    """Response contains all required top-level keys."""
    resp = client.get(f"{BASE}/analytics", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    required = {
        "total_emails", "total_inbound", "total_outbound",
        "total_sales_emails", "auto_sent", "drafted_for_review",
        "pending_human", "auto_sent_rate_pct", "avg_reply_minutes",
        "sla_breached", "competitor_mentions", "by_label",
        "by_status", "by_direction",
    }
    assert required.issubset(data.keys())


def test_analytics_by_direction_counts_inbound(client, auth_headers):
    """Inbound emails appear in by_direction and total_inbound."""
    before = client.get(f"{BASE}/analytics", headers=auth_headers).json()
    _insert_email(direction="inbound", label=EmailLabel.SALES, status=EmailStatus.CLASSIFIED)
    after = client.get(f"{BASE}/analytics", headers=auth_headers).json()
    assert after["total_inbound"] == before["total_inbound"] + 1
    assert after["by_direction"].get("inbound", 0) == before["by_direction"].get("inbound", 0) + 1
    assert after["total_emails"] == before["total_emails"] + 1


def test_analytics_by_direction_counts_outbound(client, auth_headers):
    """Outbound emails appear in by_direction and total_outbound."""
    before = client.get(f"{BASE}/analytics", headers=auth_headers).json()
    _insert_email(direction="outbound", label=EmailLabel.SALES, status=EmailStatus.REPLIED)
    after = client.get(f"{BASE}/analytics", headers=auth_headers).json()
    assert after["total_outbound"] == before["total_outbound"] + 1
    assert after["by_direction"].get("outbound", 0) == before["by_direction"].get("outbound", 0) + 1


def test_analytics_by_label_includes_all_inserted_labels(client, auth_headers):
    """Each inserted label appears in by_label."""
    _insert_email(label=EmailLabel.SUPPORT, status=EmailStatus.PENDING_HUMAN, needs_human=True)
    _insert_email(label=EmailLabel.GRIEVANCE, status=EmailStatus.PENDING_HUMAN, needs_human=True)
    _insert_email(label=EmailLabel.TRANSACTIONAL, status=EmailStatus.ARCHIVED)
    resp = client.get(f"{BASE}/analytics", headers=auth_headers)
    by_label = resp.json()["by_label"]
    assert by_label.get("Support", 0) >= 1
    assert by_label.get("Grievance", 0) >= 1
    assert by_label.get("Transactional", 0) >= 1


def test_analytics_by_status_tracks_replied(client, auth_headers):
    """Replied emails appear in by_status."""
    before = client.get(f"{BASE}/analytics", headers=auth_headers).json()
    _insert_email(label=EmailLabel.SALES, status=EmailStatus.REPLIED, direction="outbound")
    after = client.get(f"{BASE}/analytics", headers=auth_headers).json()
    assert after["by_status"].get("replied", 0) >= before["by_status"].get("replied", 0) + 1


def test_analytics_by_status_tracks_pending_human(client, auth_headers):
    """Pending-human emails appear in by_status and pending_human count."""
    before = client.get(f"{BASE}/analytics", headers=auth_headers).json()
    _insert_email(label=EmailLabel.SUPPORT, status=EmailStatus.PENDING_HUMAN, needs_human=True)
    after = client.get(f"{BASE}/analytics", headers=auth_headers).json()
    assert after["by_status"].get("pending_human", 0) >= before["by_status"].get("pending_human", 0) + 1
    assert after["pending_human"] >= before["pending_human"] + 1


def test_analytics_auto_sent_rate_is_percentage(client, auth_headers):
    """auto_sent_rate_pct is between 0 and 100."""
    data = client.get(f"{BASE}/analytics", headers=auth_headers).json()
    assert 0.0 <= data["auto_sent_rate_pct"] <= 100.0


def test_analytics_avg_reply_minutes_non_negative(client, auth_headers):
    """avg_reply_minutes is >= 0."""
    data = client.get(f"{BASE}/analytics", headers=auth_headers).json()
    assert data["avg_reply_minutes"] >= 0.0


def test_analytics_total_equals_direction_sum(client, auth_headers):
    """total_emails equals sum of all by_direction values."""
    data = client.get(f"{BASE}/analytics", headers=auth_headers).json()
    direction_sum = sum(data["by_direction"].values())
    assert data["total_emails"] == direction_sum


def test_analytics_total_equals_label_sum(client, auth_headers):
    """total_emails equals sum of all by_label values."""
    data = client.get(f"{BASE}/analytics", headers=auth_headers).json()
    label_sum = sum(data["by_label"].values())
    assert data["total_emails"] == label_sum


def test_analytics_total_equals_status_sum(client, auth_headers):
    """total_emails equals sum of all by_status values."""
    data = client.get(f"{BASE}/analytics", headers=auth_headers).json()
    status_sum = sum(data["by_status"].values())
    assert data["total_emails"] == status_sum


def test_analytics_competitor_mentions_non_negative(client, auth_headers):
    """competitor_mentions is >= 0."""
    data = client.get(f"{BASE}/analytics", headers=auth_headers).json()
    assert data["competitor_mentions"] >= 0


def test_analytics_no_auth(client):
    """Analytics endpoint requires authentication."""
    with _no_auth(client):
        resp = client.get(f"{BASE}/analytics")
    assert resp.status_code == 401
