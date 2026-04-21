import uuid
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

BASE = "/api/v1/gmail"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _raw_gmail_message(gmail_id: str = None, subject: str = "Test Subject") -> dict:
    """Minimal Gmail API message dict."""
    mid = gmail_id or uuid.uuid4().hex
    body_b64 = "SGVsbG8gd29ybGQ="  # "Hello world"
    return {
        "id": mid,
        "threadId": f"thread_{mid}",
        "payload": {
            "mimeType": "text/plain",
            "headers": [
                {"name": "From", "value": "sender@example.com"},
                {"name": "To", "value": "developer20@rdltech.in"},
                {"name": "Subject", "value": subject},
                {"name": "Date", "value": "Mon, 21 Apr 2026 10:00:00 +0000"},
            ],
            "body": {"data": body_b64},
        },
    }


# ── Sync endpoint ─────────────────────────────────────────────────────────────

def test_sync_inbox_returns_counts(client: TestClient, auth_headers: dict):
    with (
        patch("app.routers.gmail.gmail_service.get_gmail_service") as mock_svc,
        patch("app.routers.gmail.gmail_service.ensure_labels_exist"),
        patch("app.routers.gmail.gmail_service.fetch_unread_messages", return_value=[]),
        patch("app.routers.gmail.process_inbound_email", return_value=None),
    ):
        mock_svc.return_value = MagicMock()
        resp = client.post(f"{BASE}/sync", headers=auth_headers)
    assert resp.status_code == 200
    assert "processed" in resp.json()
    assert "fetched" in resp.json()


def test_sync_inbox_no_auth(client: TestClient):
    saved = dict(client.cookies)
    client.cookies.clear()
    try:
        resp = client.post(f"{BASE}/sync")
        assert resp.status_code == 401
    finally:
        for k, v in saved.items():
            client.cookies.set(k, v)


# ── Email list ────────────────────────────────────────────────────────────────

def test_list_emails_empty(client: TestClient, auth_headers: dict):
    resp = client.get(f"{BASE}/", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert "total" in body


def test_list_emails_filter_by_label(client: TestClient, auth_headers: dict):
    resp = client.get(f"{BASE}/?label=Sales", headers=auth_headers)
    assert resp.status_code == 200
    for item in resp.json()["items"]:
        assert item["label"] == "Sales"


def test_list_emails_filter_needs_human(client: TestClient, auth_headers: dict):
    resp = client.get(f"{BASE}/?needs_human=true", headers=auth_headers)
    assert resp.status_code == 200
    for item in resp.json()["items"]:
        assert item["needs_human"] is True


def test_list_emails_no_auth(client: TestClient):
    saved = dict(client.cookies)
    client.cookies.clear()
    try:
        resp = client.get(f"{BASE}/")
        assert resp.status_code == 401
    finally:
        for k, v in saved.items():
            client.cookies.set(k, v)


# ── Get single email ──────────────────────────────────────────────────────────

def test_get_nonexistent_email(client: TestClient, auth_headers: dict):
    resp = client.get(f"{BASE}/{uuid.uuid4()}", headers=auth_headers)
    assert resp.status_code == 404


# ── Resolve ───────────────────────────────────────────────────────────────────

def test_resolve_nonexistent_email(client: TestClient, auth_headers: dict):
    resp = client.post(
        f"{BASE}/{uuid.uuid4()}/resolve",
        json={"resolved_by": "agent@rdltech.in"},
        headers=auth_headers,
    )
    assert resp.status_code == 404


# ── Approve draft ─────────────────────────────────────────────────────────────

def test_approve_draft_nonexistent(client: TestClient, auth_headers: dict):
    resp = client.post(
        f"{BASE}/{uuid.uuid4()}/approve-draft",
        json={},
        headers=auth_headers,
    )
    assert resp.status_code == 404


# ── Send email ────────────────────────────────────────────────────────────────

def test_send_email_no_auth(client: TestClient):
    saved = dict(client.cookies)
    client.cookies.clear()
    try:
        resp = client.post(f"{BASE}/send", json={
            "to": "test@example.com",
            "subject": "Test",
            "body": "Hello",
        })
        assert resp.status_code == 401
    finally:
        for k, v in saved.items():
            client.cookies.set(k, v)


def test_send_email_missing_fields(client: TestClient, auth_headers: dict):
    resp = client.post(f"{BASE}/send", json={"to": "test@example.com"}, headers=auth_headers)
    assert resp.status_code == 422


# ── Classifier unit test ──────────────────────────────────────────────────────

def test_classifier_returns_valid_label():
    from app.models.communication import EmailLabel
    from app.services.email_classifier_service import classify_email

    mock_response = MagicMock()
    mock_response.content = '{"label": "Sales", "confidence": "high", "reasoning": "Product inquiry", "transactional_type": null, "transactional_data": null}'

    with patch("app.services.email_classifier_service._build_llm") as mock_llm:
        mock_llm.return_value.invoke.return_value = mock_response
        result = classify_email(
            subject="Inquiry about Biometric Kit",
            body="Hi, I would like a quote for the biometric product.",
            sender="buyer@company.com",
        )

    assert result["label"] == EmailLabel.SALES
    assert result["confidence"] == "high"


def test_classifier_falls_back_on_error():
    from app.models.communication import EmailLabel
    from app.services.email_classifier_service import classify_email

    with patch("app.services.email_classifier_service._build_llm") as mock_llm:
        mock_llm.return_value.invoke.side_effect = Exception("LLM error")
        result = classify_email(subject="Hello", body="Test", sender="x@x.com")

    assert result["label"] == EmailLabel.UNCLASSIFIED


# ── Gmail service unit tests ──────────────────────────────────────────────────

def test_parse_message_extracts_fields():
    from app.services.gmail_service import parse_message
    raw = _raw_gmail_message(gmail_id="abc123", subject="Hello there")
    parsed = parse_message(raw)
    assert parsed["gmail_message_id"] == "abc123"
    assert parsed["subject"] == "Hello there"
    assert parsed["sender"] == "sender@example.com"
    assert "developer20@rdltech.in" in parsed["recipients"]
    assert parsed["body_text"] == "Hello world"


def test_extract_email_address():
    from app.services.gmail_service import extract_email_address
    assert extract_email_address("John Doe <john@example.com>") == "john@example.com"
    assert extract_email_address("plain@example.com") == "plain@example.com"
