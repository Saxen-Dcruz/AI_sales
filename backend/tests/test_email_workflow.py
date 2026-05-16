"""
Tests for the LangGraph email workflow.

Tests are split into two layers:
  1. Node unit tests  — test each node function in isolation (no graph, no DB)
  2. Graph smoke test — run the full compiled graph against a fake message with
                        mocked external calls (Gmail API, Gemini, RAG)

Run with:
  docker compose exec backend bash -c "cd /app && PYTHONPATH=/app pytest tests/test_email_workflow.py -v"
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, call
import pytest
from sqlalchemy.orm import Session

from app.models.communication import Email, EmailLabel, EmailStatus
from app.models.leads import Lead


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def db(request):
    """Real DB session. Commits are explicit; rollback on close cleans uncommitted state."""
    from app.database.core import SessionLocal
    session = SessionLocal()
    yield session
    try:
        session.rollback()
    except Exception:
        pass
    session.close()


def _insert_and_get_id(**kwargs) -> str:
    """Insert an Email in a fresh committed session and return its ID as string."""
    from app.database.core import SessionLocal
    defaults = dict(
        direction="inbound", sender="x@x.com", recipients=[],
        subject="X", body_text="X",
        received_at=datetime.now(timezone.utc),
        label=EmailLabel.SALES, status=EmailStatus.CLASSIFIED,
    )
    defaults.update(kwargs)
    if "gmail_message_id" not in defaults:
        defaults["gmail_message_id"] = f"test_{uuid.uuid4().hex}"
    with SessionLocal() as s:
        row = Email(**defaults)
        s.add(row)
        s.commit()
        s.refresh(row)
        return str(row.id)


def _delete_rows(db, email_ids=(), lead_ids=()):
    """Commit db session (releases locks) then delete rows in a fresh session."""
    from app.database.core import SessionLocal
    try:
        db.commit()
    except Exception:
        db.rollback()
    with SessionLocal() as s:
        for eid in email_ids:
            s.query(Email).filter(Email.id == uuid.UUID(eid)).delete(synchronize_session=False)
        for lid in lead_ids:
            from app.models.leads import Lead as _Lead
            s.query(_Lead).filter(_Lead.id == uuid.UUID(lid)).delete(synchronize_session=False)
        s.commit()


def _make_raw_message(gmail_id=None, subject="Test inquiry", body="Hello, what is the price?",
                      sender="customer@example.com"):
    mid = gmail_id or f"test_{uuid.uuid4().hex}"
    import base64
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
                {"name": "Date", "value": "Mon, 05 May 2026 10:00:00 +0530"},
                {"name": "Message-ID", "value": f"<{mid}@mail.gmail.com>"},
            ],
            "body": {"data": data},
            "parts": [],
        },
    }


def _make_config(db, gmail_svc=None, account_id=None, account_email=None):
    return {
        "configurable": {
            "thread_id": f"test_{uuid.uuid4().hex}",
            "db": db,
            "gmail_svc": gmail_svc or MagicMock(),
            "account_id": account_id,
            "account_email": account_email,
        }
    }


# ── Node: parse ───────────────────────────────────────────────────────────────

def test_node_parse_returns_parsed_fields(db):
    from app.services.workflows.email_nodes import node_parse
    raw = _make_raw_message()
    state = node_parse({"raw_message": raw}, _make_config(db))
    assert state["gmail_message_id"] == raw["id"]
    assert state["sender_email"] == "customer@example.com"
    assert state["subject"] == "Test inquiry"
    assert state["effective_body"] == "Hello, what is the price?"
    assert state["duplicate"] is False


def test_node_parse_marks_duplicate(db):
    from app.services.workflows.email_nodes import node_parse
    from app.database.core import SessionLocal

    # Insert existing email
    raw = _make_raw_message()
    with SessionLocal() as s:
        s.add(Email(
            gmail_message_id=raw["id"],
            direction="inbound", sender="x@x.com",
            recipients=[], subject="X", body_text="X",
            received_at=datetime.now(timezone.utc),
            label=EmailLabel.SALES, status=EmailStatus.CLASSIFIED,
        ))
        s.commit()

    state = node_parse({"raw_message": raw}, _make_config(db))
    assert state["duplicate"] is True

    # Cleanup
    with SessionLocal() as s:
        s.query(Email).filter(Email.gmail_message_id == raw["id"]).delete()
        s.commit()


def test_node_parse_uses_subject_as_body_when_empty(db):
    from app.services.workflows.email_nodes import node_parse
    raw = _make_raw_message(body="")
    state = node_parse({"raw_message": raw}, _make_config(db))
    assert state["effective_body"] == state["subject"]


# ── Node: fetch_thread_context ────────────────────────────────────────────────

def test_node_fetch_thread_context_skips_non_reply(db):
    from app.services.workflows.email_nodes import node_fetch_thread_context
    state = {
        "subject": "Product inquiry",
        "gmail_thread_id": "th_123",
        "gmail_message_id": "msg_123",
    }
    result = node_fetch_thread_context(state, _make_config(db))
    assert result["thread_context"] is None


def test_node_fetch_thread_context_fetches_for_reply(db):
    from app.services.workflows.email_nodes import node_fetch_thread_context
    gmail_svc = MagicMock()
    with patch("app.services.workflows.email_nodes.gmail_service.fetch_thread_context",
               return_value="Original email body") as mock_fetch:
        result = node_fetch_thread_context(
            {"subject": "Re: Product inquiry", "gmail_thread_id": "th_123", "gmail_message_id": "msg_456"},
            _make_config(db, gmail_svc),
        )
    assert result["thread_context"] == "Original email body"
    mock_fetch.assert_called_once()


# ── Node: classify ────────────────────────────────────────────────────────────

def test_node_classify_sales_label(db):
    from app.services.workflows.email_nodes import node_classify
    mock_result = {
        "label": EmailLabel.SALES, "confidence": "high",
        "reasoning": "Product price inquiry",
        "transactional_type": None, "transactional_data": None, "competitor_mention": None,
    }
    with patch("app.services.workflows.email_nodes.classify_email", return_value=mock_result):
        result = node_classify(
            {"subject": "Pricing query", "effective_body": "What is the price?",
             "sender_raw": "customer@example.com", "thread_context": None},
            _make_config(db),
        )
    assert result["label"] == EmailLabel.SALES.value
    assert result["classifier_confidence"] == "high"


def test_node_classify_support_label(db):
    from app.services.workflows.email_nodes import node_classify
    mock_result = {
        "label": EmailLabel.SUPPORT, "confidence": "high",
        "reasoning": "Technical issue", "transactional_type": None,
        "transactional_data": None, "competitor_mention": None,
    }
    with patch("app.services.workflows.email_nodes.classify_email", return_value=mock_result):
        result = node_classify(
            {"subject": "Device broken", "effective_body": "My device is not working",
             "sender_raw": "customer@example.com", "thread_context": None},
            _make_config(db),
        )
    assert result["label"] == EmailLabel.SUPPORT.value


# ── Node: persist ─────────────────────────────────────────────────────────────

def test_node_persist_creates_email_row(db):
    from app.services.workflows.email_nodes import node_persist
    from app.database.core import SessionLocal

    state = {
        "gmail_message_id": f"test_{uuid.uuid4().hex}",
        "gmail_thread_id": None,
        "sender_raw": "customer@example.com",
        "recipients": ["developer20@rdltech.in"],
        "subject": "Test",
        "effective_body": "Hello",
        "body_html": None,
        "received_at": datetime.now(timezone.utc),
        "label": EmailLabel.SALES.value,
        "classifier_confidence": "high",
        "classifier_reasoning": "Sales inquiry",
        "transactional_type": None,
        "transactional_data": None,
        "competitor_mention": None,
    }
    result = node_persist(state, _make_config(db))
    assert "email_id" in result
    assert result.get("duplicate") is not True

    # Verify row is in the same session (flush doesn't commit, so we query the same session)
    row = db.query(Email).filter(Email.gmail_message_id == state["gmail_message_id"]).first()
    assert row is not None
    assert str(row.id) == result["email_id"]


def test_node_persist_sets_account_id_and_email(db):
    """account_id and account_email must be read from config, not state."""
    from app.services.workflows.email_nodes import node_persist
    from app.models.email_account import EmailAccount
    from app.core.utils import new_uuid

    # Create a real EmailAccount so FK constraint is satisfied
    fake_account_id = new_uuid()
    acct = EmailAccount(
        id=fake_account_id,
        email_address=f"acct_{uuid.uuid4().hex[:6]}@test.com",
        display_name="Test",
        token_data="dGVzdA==",  # base64 "test" — won't be decoded in this test
    )
    db.add(acct)
    db.commit()

    mid = f"test_{uuid.uuid4().hex}"
    state = {
        "gmail_message_id": mid,
        "gmail_thread_id": None,
        "sender_raw": "customer@example.com",
        "recipients": [],
        "subject": "Account test",
        "effective_body": "Test body",
        "body_html": None,
        "received_at": datetime.now(timezone.utc),
        "label": EmailLabel.SALES.value,
        "classifier_confidence": "high",
        "classifier_reasoning": None,
        "transactional_type": None,
        "transactional_data": None,
        "competitor_mention": None,
    }
    cfg = _make_config(db, account_id=str(fake_account_id), account_email=acct.email_address)
    node_persist(state, cfg)

    row = db.query(Email).filter(Email.gmail_message_id == mid).first()
    assert row is not None, "Email row must be created"
    assert row.account_id == fake_account_id, "account_id must be set from config, not state"
    assert row.account_email == acct.email_address, "account_email must be set from config, not state"


def test_node_persist_account_id_null_when_not_in_config(db):
    """When config has no account_id, row.account_id must be NULL (not crash)."""
    from app.services.workflows.email_nodes import node_persist
    mid = f"test_{uuid.uuid4().hex}"
    state = {
        "gmail_message_id": mid,
        "gmail_thread_id": None,
        "sender_raw": "x@example.com",
        "recipients": [],
        "subject": "No account",
        "effective_body": "body",
        "body_html": None,
        "received_at": datetime.now(timezone.utc),
        "label": EmailLabel.PROMOTIONAL.value,
        "classifier_confidence": None,
        "classifier_reasoning": None,
        "transactional_type": None,
        "transactional_data": None,
        "competitor_mention": None,
    }
    node_persist(state, _make_config(db))  # no account_id/account_email in config
    row = db.query(Email).filter(Email.gmail_message_id == mid).first()
    assert row is not None
    assert row.account_id is None
    assert row.account_email is None


# ── Node: upsert_lead ─────────────────────────────────────────────────────────

def test_node_upsert_lead_creates_new_lead(db):
    from app.services.workflows.email_nodes import node_upsert_lead
    from app.database.core import SessionLocal

    email_id = None
    mid = f"test_{uuid.uuid4().hex}"
    with SessionLocal() as s:
        row = Email(
            gmail_message_id=mid, direction="inbound",
            sender="new_lead@example.com", recipients=[],
            subject="X", body_text="X",
            received_at=datetime.now(timezone.utc),
            label=EmailLabel.SALES, status=EmailStatus.CLASSIFIED,
        )
        s.add(row)
        s.commit()
        s.refresh(row)
        email_id = str(row.id)

    state = {"email_id": email_id, "sender_email": f"new_{uuid.uuid4().hex}@example.com",
             "sender_raw": "New Lead <new_lead@example.com>"}
    result = node_upsert_lead(state, _make_config(db))
    assert "lead_id" in result
    assert result["is_new_lead"] is True

    # Cleanup within the SAME db session to avoid lock conflict —
    # node_upsert_lead holds a row lock on the email via its UPDATE flush.
    # A separate session would deadlock waiting for that lock.
    db.query(Email).filter(Email.id == uuid.UUID(email_id)).delete(synchronize_session=False)
    if result.get("lead_id"):
        db.query(Lead).filter(Lead.id == uuid.UUID(result["lead_id"])).delete(synchronize_session=False)
    db.commit()


def test_node_upsert_lead_reuses_existing_lead(db):
    from app.services.workflows.email_nodes import node_upsert_lead
    from app.database.core import SessionLocal

    unique_email = f"existing_{uuid.uuid4().hex}@example.com"
    with SessionLocal() as s:
        lead = Lead(name="Existing Lead", email=unique_email,
                    status="Contacted", interest_level="Hot", engagement_score=60)
        s.add(lead)
        s.flush()
        email_row = Email(
            gmail_message_id=f"test_{uuid.uuid4().hex}",
            direction="inbound", sender=unique_email, recipients=[],
            subject="X", body_text="X",
            received_at=datetime.now(timezone.utc),
            label=EmailLabel.SALES, status=EmailStatus.CLASSIFIED,
        )
        s.add(email_row)
        s.commit()
        s.refresh(lead)
        s.refresh(email_row)
        lead_id = str(lead.id)
        email_id = str(email_row.id)

    state = {"email_id": email_id, "sender_email": unique_email, "sender_raw": unique_email}
    result = node_upsert_lead(state, _make_config(db))
    assert result["lead_id"] == lead_id
    assert result["is_new_lead"] is False

    # Same session to avoid lock conflict
    db.query(Email).filter(Email.id == uuid.UUID(email_id)).delete(synchronize_session=False)
    db.query(Lead).filter(Lead.id == uuid.UUID(lead_id)).delete(synchronize_session=False)
    db.commit()


# ── Node: detect_product ──────────────────────────────────────────────────────

def test_node_detect_product_high_confidence(db):
    from app.services.workflows.email_nodes import node_detect_product
    with patch("app.services.workflows.email_nodes.detect_product",
               return_value=("prod-uuid", "Industrial Data Logger 4G LTE", "high")):
        result = node_detect_product(
            {"subject": "Data Logger inquiry", "effective_body": "Price of Industrial Data Logger 4G LTE?"},
            _make_config(db),
        )
    assert result["product_confidence"] == "high"
    assert result["product_name"] == "Industrial Data Logger 4G LTE"


def test_node_detect_product_no_match(db):
    from app.services.workflows.email_nodes import node_detect_product
    with patch("app.services.workflows.email_nodes.detect_product",
               return_value=(None, None, "none")):
        result = node_detect_product(
            {"subject": "Hi", "effective_body": "I need something"},
            _make_config(db),
        )
    assert result["product_confidence"] == "none"
    assert result["product_id"] is None


# ── Node: extract_gaps ────────────────────────────────────────────────────────

def test_node_extract_gaps_finds_gaps(db):
    from app.services.workflows.email_nodes import node_extract_gaps
    from app.database.core import SessionLocal

    with SessionLocal() as s:
        row = Email(
            gmail_message_id=f"test_{uuid.uuid4().hex}",
            direction="inbound", sender="x@x.com", recipients=[],
            subject="X", body_text="X",
            received_at=datetime.now(timezone.utc),
            label=EmailLabel.SALES, status=EmailStatus.CLASSIFIED,
        )
        s.add(row)
        s.commit()
        s.refresh(row)
        email_id = str(row.id)

    gap = {"question": "What is warranty?", "topic": "warranty",
           "product_name": "Widget", "product_id": None, "resolved": False}
    with patch("app.services.workflows.email_nodes.extract_structured_gaps", return_value=[gap]):
        result = node_extract_gaps(
            {"email_id": email_id, "effective_body": "What is warranty?",
             "draft": "Our team will confirm warranty.", "product_name": "Widget", "product_id": None},
            _make_config(db),
        )
    assert len(result["gaps"]) == 1
    assert result["gaps"][0]["topic"] == "warranty"

    _delete_rows(db, email_ids=[email_id])


def test_node_extract_gaps_no_gaps(db):
    from app.services.workflows.email_nodes import node_extract_gaps
    from app.database.core import SessionLocal

    with SessionLocal() as s:
        row = Email(
            gmail_message_id=f"test_{uuid.uuid4().hex}",
            direction="inbound", sender="x@x.com", recipients=[],
            subject="X", body_text="X",
            received_at=datetime.now(timezone.utc),
            label=EmailLabel.SALES, status=EmailStatus.CLASSIFIED,
        )
        s.add(row)
        s.commit()
        s.refresh(row)
        email_id = str(row.id)

    with patch("app.services.workflows.email_nodes.extract_structured_gaps", return_value=[]):
        result = node_extract_gaps(
            {"email_id": email_id, "effective_body": "Price?",
             "draft": "The price is ₹1,364.", "product_name": None, "product_id": None},
            _make_config(db),
        )
    assert result["gaps"] == []

    _delete_rows(db, email_ids=[email_id])


# ── Routing functions ─────────────────────────────────────────────────────────

def test_route_after_parse_duplicate():
    from app.services.workflows.email_nodes import route_after_parse
    assert route_after_parse({"duplicate": True}) == "end_duplicate"


def test_route_after_parse_not_duplicate():
    from app.services.workflows.email_nodes import route_after_parse
    assert route_after_parse({"duplicate": False}) == "fetch_thread_context"


def test_route_after_classify_sales():
    from app.services.workflows.email_nodes import route_after_classify
    assert route_after_classify({"label": "Sales"}) == "sales_branch"


def test_route_after_classify_support():
    from app.services.workflows.email_nodes import route_after_classify
    assert route_after_classify({"label": "Support"}) == "support_branch"


def test_route_after_classify_grievance():
    from app.services.workflows.email_nodes import route_after_classify
    assert route_after_classify({"label": "Grievance"}) == "support_branch"


def test_route_after_classify_transactional():
    from app.services.workflows.email_nodes import route_after_classify
    assert route_after_classify({"label": "Transactional"}) == "archive_branch"


def test_route_after_classify_promotional():
    from app.services.workflows.email_nodes import route_after_classify
    assert route_after_classify({"label": "Promotional"}) == "archive_branch"


def test_route_after_confidence_high():
    from app.services.workflows.email_nodes import route_after_confidence
    assert route_after_confidence({"product_confidence": "high"}) == "rag_branch"


def test_route_after_confidence_low():
    from app.services.workflows.email_nodes import route_after_confidence
    assert route_after_confidence({"product_confidence": "low"}) == "clarification_branch"


def test_route_after_confidence_none():
    from app.services.workflows.email_nodes import route_after_confidence
    assert route_after_confidence({"product_confidence": "none"}) == "clarification_branch"


def test_route_after_gaps_has_gaps():
    from app.services.workflows.email_nodes import route_after_gaps
    assert route_after_gaps({"gaps": [{"question": "Warranty?"}]}) == "hold_draft"


def test_route_after_gaps_no_gaps():
    from app.services.workflows.email_nodes import route_after_gaps
    assert route_after_gaps({"gaps": []}) == "auto_send"


# ── Graph: full workflow smoke test ───────────────────────────────────────────

def test_full_graph_sales_auto_send(db):
    """Sales email with high-confidence product and no gaps → auto_sent."""
    from langgraph.checkpoint.memory import MemorySaver
    import app.services.workflows.email_workflow as wf
    wf.get_checkpointer = lambda: MemorySaver()
    wf._email_graph = None  # force rebuild with MemorySaver

    raw = _make_raw_message(subject="Data Logger price?", body="What is the price of the Industrial Data Logger?")

    gmail_svc_mock = MagicMock()
    gmail_svc_mock.return_value = MagicMock()

    with patch("app.services.workflows.email_nodes.gmail_service.get_gmail_service", return_value=MagicMock()), \
         patch("app.services.workflows.email_nodes.gmail_service.parse_message") as mock_parse, \
         patch("app.services.workflows.email_nodes.gmail_service.extract_email_address", return_value="customer@example.com"), \
         patch("app.services.workflows.email_nodes.gmail_service.fetch_thread_context", return_value=None), \
         patch("app.services.workflows.email_nodes.gmail_service.apply_label_to_message"), \
         patch("app.services.workflows.email_nodes.gmail_service.mark_as_read"), \
         patch("app.services.workflows.email_nodes.gmail_service.create_draft", return_value={"id": "draft_123"}), \
         patch("app.services.workflows.email_nodes.gmail_service.send_draft"), \
         patch("app.services.workflows.email_nodes.classify_email", return_value={
             "label": EmailLabel.SALES, "confidence": "high",
             "reasoning": "Price inquiry", "transactional_type": None,
             "transactional_data": None, "competitor_mention": None,
         }), \
         patch("app.services.workflows.email_nodes.detect_product",
               return_value=("prod-uuid-123", "Industrial Data Logger 4G LTE", "high")), \
         patch("app.services.workflows.email_nodes.fetch_rag_context", return_value="Price: ₹12,000"), \
         patch("app.services.workflows.email_nodes.extract_structured_gaps", return_value=[]), \
         patch("app.services.workflows.email_nodes.sanitize_ai_response", side_effect=lambda x: x):

        mid = f"test_{uuid.uuid4().hex}"
        mock_parse.return_value = {
            "gmail_message_id": mid,
            "gmail_thread_id": f"th_{mid}",
            "sender": "customer@example.com",
            "recipients": ["developer20@rdltech.in"],
            "subject": "Data Logger price?",
            "body_text": "What is the price of the Industrial Data Logger?",
            "body_html": None,
            "date_str": "Mon, 05 May 2026 10:00:00 +0530",
        }

        with patch("app.services.workflows.email_nodes.generate_sales_draft",
                    return_value="The price of the Industrial Data Logger is ₹12,000."):
            from app.services.workflows.email_workflow import run_email_workflow
            result = run_email_workflow(db, raw)

    assert result is not None
    assert result.status == EmailStatus.REPLIED
    assert result.label == EmailLabel.SALES


def test_full_graph_support_flags_human(db):
    """Support email → flag_human → draft saved (DRAFT_READY), needs_human=True."""
    from langgraph.checkpoint.memory import MemorySaver
    import app.services.workflows.email_workflow as wf
    wf.get_checkpointer = lambda: MemorySaver()
    wf._email_graph = None

    raw = _make_raw_message(subject="Device not working", body="My device stopped working yesterday")

    with patch("app.services.workflows.email_nodes.gmail_service.get_gmail_service", return_value=MagicMock()), \
         patch("app.services.workflows.email_nodes.gmail_service.parse_message") as mock_parse, \
         patch("app.services.workflows.email_nodes.gmail_service.extract_email_address", return_value="customer@example.com"), \
         patch("app.services.workflows.email_nodes.gmail_service.apply_label_to_message"), \
         patch("app.services.workflows.email_nodes.gmail_service.mark_as_read"), \
         patch("app.services.workflows.email_nodes.gmail_service.create_draft",
               return_value={"id": "draft_test", "message": {"id": "msg_test"}}), \
         patch("app.services.workflows.email_nodes.classify_email", return_value={
             "label": EmailLabel.SUPPORT, "confidence": "high",
             "reasoning": "Device issue", "transactional_type": None,
             "transactional_data": None, "competitor_mention": None,
         }):

        mid = f"test_{uuid.uuid4().hex}"
        mock_parse.return_value = {
            "gmail_message_id": mid, "gmail_thread_id": f"th_{mid}",
            "sender": "customer@example.com", "recipients": ["dev@rdltech.in"],
            "subject": "Device not working", "body_text": "My device stopped working",
            "body_html": None, "date_str": "Mon, 05 May 2026 10:00:00 +0530",
            "rfc_message_id": "",
        }

        from app.services.workflows.email_workflow import run_email_workflow
        result = run_email_workflow(db, raw)

    assert result is not None
    assert result.status == EmailStatus.DRAFT_READY
    assert result.needs_human is True


def test_full_graph_duplicate_skipped(db):
    """Duplicate gmail_message_id → returns None."""
    from langgraph.checkpoint.memory import MemorySaver
    from app.database.core import SessionLocal
    import app.services.workflows.email_workflow as wf
    wf.get_checkpointer = lambda: MemorySaver()
    wf._email_graph = None

    mid = f"test_{uuid.uuid4().hex}"
    with SessionLocal() as s:
        s.add(Email(
            gmail_message_id=mid, direction="inbound",
            sender="x@x.com", recipients=[], subject="X", body_text="X",
            received_at=datetime.now(timezone.utc),
            label=EmailLabel.SALES, status=EmailStatus.CLASSIFIED,
        ))
        s.commit()

    raw = _make_raw_message(gmail_id=mid)
    with patch("app.services.workflows.email_nodes.gmail_service.get_gmail_service", return_value=MagicMock()), \
         patch("app.services.workflows.email_nodes.gmail_service.parse_message") as mock_parse:

        mock_parse.return_value = {
            "gmail_message_id": mid, "gmail_thread_id": None,
            "sender": "x@x.com", "recipients": [], "subject": "X",
            "body_text": "X", "body_html": None,
            "date_str": "Mon, 05 May 2026 10:00:00 +0530",
        }
        from app.services.workflows.email_workflow import run_email_workflow
        result = run_email_workflow(db, raw)

    assert result is None

    with SessionLocal() as s:
        s.query(Email).filter(Email.gmail_message_id == mid).delete()
        s.commit()


# ── Edge cases: node_auto_send failure ────────────────────────────────────────

def test_node_auto_send_falls_back_when_draft_empty(db):
    """auto_send with empty draft → sets pending_human, returns pending_human_draft_failed."""
    from app.services.workflows.email_nodes import node_auto_send
    from app.database.core import SessionLocal

    with SessionLocal() as s:
        row = Email(
            gmail_message_id=f"test_{uuid.uuid4().hex}",
            direction="inbound", sender="x@x.com", recipients=[],
            subject="X", body_text="X",
            received_at=datetime.now(timezone.utc),
            label=EmailLabel.SALES, status=EmailStatus.CLASSIFIED,
        )
        s.add(row); s.commit(); s.refresh(row)
        email_id = str(row.id)

    result = node_auto_send(
        {"email_id": email_id, "sender_email": "x@x.com", "subject": "X",
         "draft": "", "gmail_thread_id": None},
        _make_config(db),
    )
    assert result["action"] == "pending_human_draft_failed"

    _delete_rows(db, email_ids=[email_id])


def test_node_auto_send_falls_back_when_gmail_fails(db):
    """auto_send Gmail API failure → sets pending_human."""
    from app.services.workflows.email_nodes import node_auto_send
    from app.database.core import SessionLocal

    with SessionLocal() as s:
        row = Email(
            gmail_message_id=f"test_{uuid.uuid4().hex}",
            direction="inbound", sender="x@x.com", recipients=[],
            subject="X", body_text="X",
            received_at=datetime.now(timezone.utc),
            label=EmailLabel.SALES, status=EmailStatus.CLASSIFIED,
        )
        s.add(row); s.commit(); s.refresh(row)
        email_id = str(row.id)

    with patch("app.services.workflows.email_nodes.gmail_service.create_draft",
               side_effect=Exception("Gmail API down")):
        result = node_auto_send(
            {"email_id": email_id, "sender_email": "x@x.com", "subject": "X",
             "draft": "The price is ₹1,000.", "gmail_thread_id": None},
            _make_config(db),
        )
    assert result["action"] == "pending_human_send_failed"

    _delete_rows(db, email_ids=[email_id])


# ── Edge cases: node_hold_draft ───────────────────────────────────────────────

def test_node_hold_draft_sets_draft_ready(db):
    """hold_draft with valid draft → status=draft_ready, needs_human=True."""
    from app.services.workflows.email_nodes import node_hold_draft
    from app.database.core import SessionLocal

    with SessionLocal() as s:
        row = Email(
            gmail_message_id=f"test_{uuid.uuid4().hex}",
            direction="inbound", sender="x@x.com", recipients=[],
            subject="X", body_text="X",
            received_at=datetime.now(timezone.utc),
            label=EmailLabel.SALES, status=EmailStatus.CLASSIFIED,
        )
        s.add(row); s.commit(); s.refresh(row)
        email_id = str(row.id)

    gmail_svc = MagicMock()
    with patch("app.services.workflows.email_nodes.gmail_service.create_draft",
               return_value={"id": "draft_abc"}):
        result = node_hold_draft(
            {"email_id": email_id, "sender_email": "x@x.com", "subject": "Pricing query",
             "draft": "Price is ₹1,364.", "gaps": [{"question": "Warranty?"}],
             "gmail_thread_id": None},
            _make_config(db, gmail_svc),
        )
    assert result["action"] == "draft_held"

    # Commit db session to release lock and make update visible to verification query
    db.commit()
    from app.database.core import SessionLocal as _SL
    with _SL() as s:
        row = s.query(Email).filter(Email.id == uuid.UUID(email_id)).first()
        assert row.status == EmailStatus.DRAFT_READY
        assert row.needs_human is True
        assert row.gmail_draft_id == "draft_abc"
        s.delete(row); s.commit()


# ── Edge cases: node_flag_human ───────────────────────────────────────────────

def test_node_flag_human_saves_draft_not_sends(db):
    """Grievance must save a Gmail draft (not auto-send) so human can edit before sending."""
    from app.services.workflows.email_nodes import node_flag_human
    from app.database.core import SessionLocal

    with SessionLocal() as s:
        row = Email(
            gmail_message_id=f"test_{uuid.uuid4().hex}",
            direction="inbound", sender="angry@customer.com", recipients=[],
            subject="Terrible product!", body_text="I want a refund",
            received_at=datetime.now(timezone.utc),
            label=EmailLabel.GRIEVANCE, status=EmailStatus.CLASSIFIED,
        )
        s.add(row); s.commit(); s.refresh(row)
        email_id = str(row.id)

    mock_draft = {"id": "draft_abc123", "message": {"id": "msg_xyz"}}
    with patch("app.services.workflows.email_nodes.gmail_service.create_draft",
               return_value=mock_draft) as mock_create, \
         patch("app.services.workflows.email_nodes.gmail_service.send_email") as mock_send:
        result = node_flag_human(
            {"email_id": email_id, "label": "Grievance",
             "sender_raw": "Angry Customer <angry@customer.com>",
             "sender_email": "angry@customer.com",
             "subject": "Terrible product!", "gmail_thread_id": None,
             "rfc_message_id": ""},
            _make_config(db),
        )
    assert result["action"] == "flagged_human"
    mock_create.assert_called_once()          # draft saved
    mock_send.assert_not_called()             # NOT auto-sent
    # Verify ack body contains apology language
    body_arg = mock_create.call_args.kwargs.get("body", "") or mock_create.call_args[1].get("body", "")
    assert "apologise" in body_arg.lower() or "apolog" in body_arg.lower()
    # Verify DB status is DRAFT_READY (not PENDING_HUMAN)
    db.commit()
    from app.database.core import SessionLocal as _SL
    with _SL() as s:
        row = s.query(Email).filter(Email.id == uuid.UUID(email_id)).first()
        assert row.status == EmailStatus.DRAFT_READY
        assert row.needs_human is True
        assert row.gmail_draft_id == "draft_abc123"
        s.delete(row); s.commit()

    _delete_rows(db, email_ids=[email_id])


def test_node_flag_human_still_sets_pending_when_draft_fails(db):
    """Draft creation failure must not block — email falls back to pending_human."""
    from app.services.workflows.email_nodes import node_flag_human
    from app.database.core import SessionLocal

    with SessionLocal() as s:
        row = Email(
            gmail_message_id=f"test_{uuid.uuid4().hex}",
            direction="inbound", sender="x@x.com", recipients=[],
            subject="Help", body_text="Help me",
            received_at=datetime.now(timezone.utc),
            label=EmailLabel.SUPPORT, status=EmailStatus.CLASSIFIED,
        )
        s.add(row); s.commit(); s.refresh(row)
        email_id = str(row.id)

    with patch("app.services.workflows.email_nodes.gmail_service.create_draft",
               side_effect=Exception("Gmail error")):
        result = node_flag_human(
            {"email_id": email_id, "label": "Support",
             "sender_raw": "x@x.com", "sender_email": "x@x.com",
             "subject": "Help", "gmail_thread_id": None, "rfc_message_id": ""},
            _make_config(db),
        )
    assert result["action"] == "flagged_human"

    db.commit()
    from app.database.core import SessionLocal as _SL
    with _SL() as s:
        row = s.query(Email).filter(Email.id == uuid.UUID(email_id)).first()
        assert row.needs_human is True
        assert row.status == EmailStatus.PENDING_HUMAN
        s.delete(row); s.commit()


# ── Edge cases: node_archive ──────────────────────────────────────────────────

def test_node_archive_transactional_sets_archived(db):
    from app.services.workflows.email_nodes import node_archive
    from app.database.core import SessionLocal

    with SessionLocal() as s:
        row = Email(
            gmail_message_id=f"test_{uuid.uuid4().hex}",
            direction="inbound", sender="invoice@vendor.com", recipients=[],
            subject="Invoice #1234", body_text="Please find attached",
            received_at=datetime.now(timezone.utc),
            label=EmailLabel.TRANSACTIONAL, status=EmailStatus.CLASSIFIED,
        )
        s.add(row); s.commit(); s.refresh(row)
        email_id = str(row.id)

    with patch("app.services.workflows.email_nodes.gmail_service.archive_message"):
        result = node_archive(
            {"email_id": email_id, "label": "Transactional",
             "gmail_message_id": "msg_xyz", "subject": "Invoice #1234"},
            _make_config(db),
        )
    assert result["action"] == "archived"

    db.commit()
    from app.database.core import SessionLocal as _SL
    with _SL() as s:
        row = s.query(Email).filter(Email.id == uuid.UUID(email_id)).first()
        assert row.status == EmailStatus.ARCHIVED
        s.delete(row); s.commit()


def test_node_archive_promotional_sets_ignored(db):
    from app.services.workflows.email_nodes import node_archive
    from app.database.core import SessionLocal

    with SessionLocal() as s:
        row = Email(
            gmail_message_id=f"test_{uuid.uuid4().hex}",
            direction="inbound", sender="promo@vendor.com", recipients=[],
            subject="50% off sale!", body_text="Limited time offer",
            received_at=datetime.now(timezone.utc),
            label=EmailLabel.PROMOTIONAL, status=EmailStatus.CLASSIFIED,
        )
        s.add(row); s.commit(); s.refresh(row)
        email_id = str(row.id)

    with patch("app.services.workflows.email_nodes.gmail_service.archive_message"):
        result = node_archive(
            {"email_id": email_id, "label": "Promotional",
             "gmail_message_id": "msg_xyz", "subject": "50% off sale!"},
            _make_config(db),
        )
    assert result["action"] == "archived"

    db.commit()
    from app.database.core import SessionLocal as _SL
    with _SL() as s:
        row = s.query(Email).filter(Email.id == uuid.UUID(email_id)).first()
        assert row.status == EmailStatus.IGNORED
        s.delete(row); s.commit()


# ── Edge cases: send_clarification ───────────────────────────────────────────

def test_node_send_clarification_with_no_similar_products(db):
    """Clarification with no similar products → fallback message with catalog link."""
    from app.services.workflows.email_nodes import node_send_clarification
    from app.database.core import SessionLocal

    with SessionLocal() as s:
        row = Email(
            gmail_message_id=f"test_{uuid.uuid4().hex}",
            direction="inbound", sender="x@x.com", recipients=[],
            subject="Vague query", body_text="I need something",
            received_at=datetime.now(timezone.utc),
            label=EmailLabel.SALES, status=EmailStatus.CLASSIFIED,
        )
        s.add(row); s.commit(); s.refresh(row)
        email_id = str(row.id)

    with patch("app.services.workflows.email_nodes.find_similar_products", return_value=[]), \
         patch("app.services.workflows.email_nodes.gmail_service.create_draft",
               return_value={"id": "draft_cl1"}), \
         patch("app.services.workflows.email_nodes.gmail_service.send_draft"):
        result = node_send_clarification(
            {"email_id": email_id, "subject": "Vague query",
             "effective_body": "I need something",
             "sender_email": "x@x.com", "gmail_thread_id": None,
             "product_name": None, "product_confidence": "none"},
            _make_config(db),
        )
    assert result["action"] == "clarification_sent"

    _delete_rows(db, email_ids=[email_id])


# ── Edge cases: resume_after_gaps_resolved ────────────────────────────────────

def test_resume_sends_when_all_gaps_resolved(db):
    from app.services.workflows.email_workflow import resume_after_gaps_resolved
    from app.database.core import SessionLocal

    with SessionLocal() as s:
        row = Email(
            gmail_message_id=f"test_{uuid.uuid4().hex}",
            direction="inbound", sender="x@x.com", recipients=[],
            subject="X", body_text="X",
            received_at=datetime.now(timezone.utc),
            label=EmailLabel.SALES, status=EmailStatus.DRAFT_READY,
            gmail_draft_id="draft_resume_123",
            needs_human=True,
            followup_gaps=[{"question": "Warranty?", "resolved": True, "answer": "1 year"}],
        )
        s.add(row); s.commit(); s.refresh(row)
        email_id = str(row.id)

    with patch("app.services.gmail_service.get_gmail_service", return_value=MagicMock()), \
         patch("app.services.gmail_service.send_draft"):
        result = resume_after_gaps_resolved(db, email_id)

    assert result is True

    with SessionLocal() as s:
        row = s.query(Email).filter(Email.id == uuid.UUID(email_id)).first()
        assert row.status == EmailStatus.REPLIED
        assert row.needs_human is False
        s.delete(row); s.commit()


def test_resume_does_nothing_when_gaps_still_open(db):
    from app.services.workflows.email_workflow import resume_after_gaps_resolved
    from app.database.core import SessionLocal

    with SessionLocal() as s:
        row = Email(
            gmail_message_id=f"test_{uuid.uuid4().hex}",
            direction="inbound", sender="x@x.com", recipients=[],
            subject="X", body_text="X",
            received_at=datetime.now(timezone.utc),
            label=EmailLabel.SALES, status=EmailStatus.DRAFT_READY,
            gmail_draft_id="draft_partial",
            needs_human=True,
            followup_gaps=[
                {"question": "Warranty?", "resolved": True, "answer": "1 year"},
                {"question": "Price?", "resolved": False},
            ],
        )
        s.add(row); s.commit(); s.refresh(row)
        email_id = str(row.id)

    result = resume_after_gaps_resolved(db, email_id)
    assert result is False

    with SessionLocal() as s:
        row = s.query(Email).filter(Email.id == uuid.UUID(email_id)).first()
        assert row.status == EmailStatus.DRAFT_READY  # unchanged
        s.delete(row); s.commit()


def test_resume_returns_false_for_missing_email(db):
    from app.services.workflows.email_workflow import resume_after_gaps_resolved
    result = resume_after_gaps_resolved(db, str(uuid.uuid4()))
    assert result is False


def test_resume_returns_false_when_no_draft_id(db):
    from app.services.workflows.email_workflow import resume_after_gaps_resolved
    from app.database.core import SessionLocal

    with SessionLocal() as s:
        row = Email(
            gmail_message_id=f"test_{uuid.uuid4().hex}",
            direction="inbound", sender="x@x.com", recipients=[],
            subject="X", body_text="X",
            received_at=datetime.now(timezone.utc),
            label=EmailLabel.SALES, status=EmailStatus.DRAFT_READY,
            gmail_draft_id=None,  # no draft
            followup_gaps=[{"question": "Price?", "resolved": True, "answer": "₹1,000"}],
        )
        s.add(row); s.commit(); s.refresh(row)
        email_id = str(row.id)

    result = resume_after_gaps_resolved(db, email_id)
    assert result is False

    _delete_rows(db, email_ids=[email_id])


# ── Edge cases: full graph — low confidence → clarification ──────────────────

def test_full_graph_low_confidence_sends_clarification(db):
    """Low product confidence → clarification email sent, not RAG draft."""
    from langgraph.checkpoint.memory import MemorySaver
    import app.services.workflows.email_workflow as wf
    wf.get_checkpointer = lambda: MemorySaver()
    wf._email_graph = None

    raw = _make_raw_message(subject="I need a sensor", body="Do you have sensors?")

    with patch("app.services.workflows.email_nodes.gmail_service.get_gmail_service", return_value=MagicMock()), \
         patch("app.services.workflows.email_nodes.gmail_service.parse_message") as mock_parse, \
         patch("app.services.workflows.email_nodes.gmail_service.extract_email_address", return_value="c@c.com"), \
         patch("app.services.workflows.email_nodes.gmail_service.apply_label_to_message"), \
         patch("app.services.workflows.email_nodes.gmail_service.mark_as_read"), \
         patch("app.services.workflows.email_nodes.gmail_service.create_draft", return_value={"id": "d1"}), \
         patch("app.services.workflows.email_nodes.gmail_service.send_draft"), \
         patch("app.services.workflows.email_nodes.classify_email", return_value={
             "label": EmailLabel.SALES, "confidence": "high", "reasoning": "Inquiry",
             "transactional_type": None, "transactional_data": None, "competitor_mention": None,
         }), \
         patch("app.services.workflows.email_nodes.detect_product",
               return_value=(None, None, "none")), \
         patch("app.services.workflows.email_nodes.find_similar_products",
               return_value=[{"name": "Soil Moisture Sensor", "order_code": "RDL100",
                              "product_link": "https://rdltech.in/p/rdl100"}]):

        mid = f"test_{uuid.uuid4().hex}"
        mock_parse.return_value = {
            "gmail_message_id": mid, "gmail_thread_id": None,
            "sender": "c@c.com", "recipients": ["dev@rdltech.in"],
            "subject": "I need a sensor", "body_text": "Do you have sensors?",
            "body_html": None, "date_str": "Mon, 05 May 2026 10:00:00 +0530",
        }

        from app.services.workflows.email_workflow import run_email_workflow
        result = run_email_workflow(db, raw)

    assert result is not None
    assert result.status == EmailStatus.REPLIED
    assert result.ai_draft is not None


# ── Edge cases: full graph — has gaps → hold draft ────────────────────────────

def test_full_graph_with_gaps_holds_draft(db):
    """Sales email where RAG can't answer everything → draft held, needs_human=True."""
    from langgraph.checkpoint.memory import MemorySaver
    import app.services.workflows.email_workflow as wf
    wf.get_checkpointer = lambda: MemorySaver()
    wf._email_graph = None

    raw = _make_raw_message(subject="Warranty and price?",
                            body="What is warranty and price of Data Logger?")

    with patch("app.services.workflows.email_nodes.gmail_service.get_gmail_service", return_value=MagicMock()), \
         patch("app.services.workflows.email_nodes.gmail_service.parse_message") as mock_parse, \
         patch("app.services.workflows.email_nodes.gmail_service.extract_email_address", return_value="c@c.com"), \
         patch("app.services.workflows.email_nodes.gmail_service.apply_label_to_message"), \
         patch("app.services.workflows.email_nodes.gmail_service.mark_as_read"), \
         patch("app.services.workflows.email_nodes.gmail_service.create_draft", return_value={"id": "draft_gap_1"}), \
         patch("app.services.workflows.email_nodes.classify_email", return_value={
             "label": EmailLabel.SALES, "confidence": "high", "reasoning": "Price+warranty",
             "transactional_type": None, "transactional_data": None, "competitor_mention": None,
         }), \
         patch("app.services.workflows.email_nodes.detect_product",
               return_value=("prod-uuid", "Industrial Data Logger", "high")), \
         patch("app.services.workflows.email_nodes.fetch_rag_context", return_value="Price: ₹12,000"), \
         patch("app.services.workflows.email_nodes.extract_structured_gaps", return_value=[
             {"question": "What is the warranty?", "topic": "warranty",
              "product_name": "Industrial Data Logger", "product_id": "prod-uuid",
              "resolved": False, "answer": None, "resolved_by": None}
         ]), \
         patch("app.services.workflows.email_nodes.sanitize_ai_response", side_effect=lambda x: x):

        mid = f"test_{uuid.uuid4().hex}"
        mock_parse.return_value = {
            "gmail_message_id": mid, "gmail_thread_id": None,
            "sender": "c@c.com", "recipients": ["dev@rdltech.in"],
            "subject": "Warranty and price?", "body_text": "What is warranty and price?",
            "body_html": None, "date_str": "Mon, 05 May 2026 10:00:00 +0530",
        }

        with patch("app.services.workflows.email_nodes.generate_sales_draft",
                    return_value="Price is ₹12,000. Our team will follow up on warranty."):
            from app.services.workflows.email_workflow import run_email_workflow
            result = run_email_workflow(db, raw)

    assert result is not None
    assert result.status == EmailStatus.DRAFT_READY
    assert result.needs_human is True
    assert result.followup_gaps is not None and len(result.followup_gaps) > 0


# ── Edge cases: node_try_schedule_meeting ─────────────────────────────────────

def test_node_try_schedule_meeting_skips_without_keywords(db):
    from app.services.workflows.email_nodes import node_try_schedule_meeting
    result = node_try_schedule_meeting(
        {"effective_body": "What is the price?", "subject": "Price query",
         "sender_email": "x@x.com", "lead_id": None},
        _make_config(db),
    )
    assert result == {}


def test_node_try_schedule_meeting_skips_without_specific_time(db):
    from app.services.workflows.email_nodes import node_try_schedule_meeting
    result = node_try_schedule_meeting(
        {"effective_body": "Can we schedule a meeting sometime?",
         "subject": "Meeting", "sender_email": "x@x.com", "lead_id": None},
        _make_config(db),
    )
    # No specific time given — should skip gracefully
    assert result == {}


def test_node_try_schedule_meeting_schedules_with_specific_time(db):
    from app.services.workflows.email_nodes import node_try_schedule_meeting
    with patch("app.services.workflows.email_nodes._parse_requested_time",
               return_value=datetime(2026, 6, 10, 10, 0, tzinfo=timezone.utc)), \
         patch("app.services.calendar_service.create_meeting", return_value=MagicMock(meet_link="https://meet.google.com/abc")), \
         patch("app.services.calendar_service.get_calendar_service", return_value=MagicMock()), \
         patch("app.services.calendar_service._is_slot_free", return_value=True):
        result = node_try_schedule_meeting(
            {"effective_body": "Can we schedule a meeting at 10am on June 10?",
             "subject": "Meeting request", "sender_email": "x@x.com", "lead_id": None},
            _make_config(db),
        )
    assert result == {}  # node returns empty dict — side effect is the meeting creation


# ── Edge cases: node_update_lead_score ───────────────────────────────────────

def test_node_update_lead_score_skips_without_lead_id(db):
    from app.services.workflows.email_nodes import node_update_lead_score
    result = node_update_lead_score({"lead_id": None}, _make_config(db))
    assert result == {}


def test_node_update_lead_score_calls_service(db):
    from app.services.workflows.email_nodes import node_update_lead_score
    lead_id = str(uuid.uuid4())
    with patch("app.services.lead_scoring_service.update_lead_score") as mock_update:
        node_update_lead_score({"lead_id": lead_id}, _make_config(db))
    mock_update.assert_called_once()


# ── Edge cases: node_start_drip ──────────────────────────────────────────────

def test_node_start_drip_skips_for_existing_lead(db):
    from app.services.workflows.email_nodes import node_start_drip
    with patch("app.services.email_sequence_service.create_sequence") as mock_seq:
        node_start_drip({"is_new_lead": False, "lead_id": str(uuid.uuid4())}, _make_config(db))
    mock_seq.assert_not_called()


def test_node_start_drip_skips_without_lead_id(db):
    from app.services.workflows.email_nodes import node_start_drip
    with patch("app.services.email_sequence_service.create_sequence") as mock_seq:
        node_start_drip({"is_new_lead": True, "lead_id": None}, _make_config(db))
    mock_seq.assert_not_called()


# ── Edge cases: node_persist concurrent duplicate ─────────────────────────────

def test_node_persist_handles_concurrent_duplicate(db):
    """Simulate a race condition where another process already committed the same gmail_message_id."""
    from app.services.workflows.email_nodes import node_persist
    from sqlalchemy.exc import IntegrityError

    state = {
        "gmail_message_id": f"test_{uuid.uuid4().hex}",
        "gmail_thread_id": None,
        "sender_raw": "x@x.com", "recipients": [], "subject": "X",
        "effective_body": "X", "body_html": None,
        "received_at": datetime.now(timezone.utc),
        "label": EmailLabel.SALES.value, "classifier_confidence": "high",
        "classifier_reasoning": "Sales", "transactional_type": None,
        "transactional_data": None, "competitor_mention": None,
    }

    with patch.object(db, "flush", side_effect=IntegrityError("dup", {}, Exception("unique violation"))):
        result = node_persist(state, _make_config(db))
    assert result.get("duplicate") is True


# ── Edge cases: personal email archived correctly ────────────────────────────

def test_full_graph_personal_email_ignored(db):
    from langgraph.checkpoint.memory import MemorySaver
    import app.services.workflows.email_workflow as wf
    wf.get_checkpointer = lambda: MemorySaver()
    wf._email_graph = None

    raw = _make_raw_message(subject="Happy Birthday!", body="Wishing you a great day!")

    with patch("app.services.workflows.email_nodes.gmail_service.get_gmail_service", return_value=MagicMock()), \
         patch("app.services.workflows.email_nodes.gmail_service.parse_message") as mock_parse, \
         patch("app.services.workflows.email_nodes.gmail_service.extract_email_address", return_value="friend@x.com"), \
         patch("app.services.workflows.email_nodes.gmail_service.apply_label_to_message"), \
         patch("app.services.workflows.email_nodes.gmail_service.mark_as_read"), \
         patch("app.services.workflows.email_nodes.gmail_service.archive_message"), \
         patch("app.services.workflows.email_nodes.classify_email", return_value={
             "label": EmailLabel.PERSONAL, "confidence": "high", "reasoning": "Personal greeting",
             "transactional_type": None, "transactional_data": None, "competitor_mention": None,
         }):

        mid = f"test_{uuid.uuid4().hex}"
        mock_parse.return_value = {
            "gmail_message_id": mid, "gmail_thread_id": None,
            "sender": "friend@x.com", "recipients": ["dev@rdltech.in"],
            "subject": "Happy Birthday!", "body_text": "Wishing you a great day!",
            "body_html": None, "date_str": "Mon, 05 May 2026 10:00:00 +0530",
        }

        from app.services.workflows.email_workflow import run_email_workflow
        result = run_email_workflow(db, raw)

    assert result is not None
    assert result.status == EmailStatus.IGNORED


# ── sales_gap_service unit tests ─────────────────────────────────────────────

class TestExtractNumberedItems:
    """Tests for _extract_numbered_items — covers bugs found in production."""

    def _fn(self, text):
        from app.services.sales_gap_service import _extract_numbered_items
        return _extract_numbered_items(text)

    def test_numbered_list_at_start_of_string(self):
        """First question must NOT be dropped when list starts at position 0."""
        text = "1. What is the price?\n2. What is the warranty?\n3. Bulk discount?"
        items = self._fn(text)
        assert len(items) == 3, f"Expected 3 items, got {len(items)}: {items}"
        assert "What is the price?" in items[0]

    def test_numbered_list_after_intro(self):
        items = self._fn("Hello,\n1. Price?\n2. Warranty?")
        assert len(items) == 2
        assert "Price?" in items[0]

    def test_bullet_list_parsed(self):
        """Bullet points (- item) must be parsed as separate items."""
        text = "I have questions:\n- What is the price?\n- Is it waterproof?\n- Delivery time?"
        items = self._fn(text)
        assert len(items) == 3, f"Expected 3, got {len(items)}: {items}"
        assert all("-" not in i for i in items), "Bullet marker leaked into item text"

    def test_asterisk_bullet_list(self):
        text = "* What is the price?\n* Warranty period?"
        items = self._fn(text)
        assert len(items) == 2

    def test_fallback_question_split(self):
        """Single-line questions split on ? when no list detected."""
        text = "What is the price of Industrial Data Logger 4G LTE? Does it have warranty?"
        items = self._fn(text)
        assert len(items) == 2

    def test_empty_text(self):
        assert self._fn("") == []

    def test_no_questions_or_list(self):
        assert self._fn("Just a statement with no questions.") == []


class TestExtractStructuredGaps:
    """Tests for extract_structured_gaps."""

    def _fn(self, customer, response, pname=None, pid=None):
        from app.services.sales_gap_service import extract_structured_gaps
        return extract_structured_gaps(customer, response, pname, pid)

    def test_numbered_list_at_start_maps_correctly(self):
        """Regression: first gap must not be missed when customer uses a list at position 0."""
        customer = "1. What is the price?\n2. What is the warranty?"
        response = "1. The price is ₹4,500.\n2. Our team will follow up on warranty details."
        gaps = self._fn(customer, response, "Product A", "pid-1")
        assert len(gaps) == 1
        assert "warranty" in gaps[0]["question"].lower()
        assert gaps[0]["topic"] == "warranty"

    def test_bullet_list_customer_questions(self):
        customer = "- What is the price?\n- Warranty period?"
        response = "1. Price is ₹4,500.\n2. Our team will follow up on the warranty."
        gaps = self._fn(customer, response, "Product A", "pid-1")
        assert len(gaps) == 1
        assert "warranty" in gaps[0]["question"].lower()

    def test_no_gaps_when_all_answered(self):
        customer = "1. Price?\n2. Warranty?"
        response = "1. Price is ₹4,000.\n2. Warranty is 1 year."
        gaps = self._fn(customer, response)
        assert gaps == []

    def test_fallback_gap_uses_customer_text(self):
        """When no list structure, fallback gap question is the customer's text."""
        customer = "Can you tell me about the data logger?"
        response = "Our team will follow up with full specifications."
        gaps = self._fn(customer, response, "DL", "pid-x")
        assert len(gaps) == 1
        assert "data logger" in gaps[0]["question"].lower()

    def test_fallback_gap_truncated_at_600(self):
        """Gap question must not be cut short below 600 chars."""
        customer = "x" * 700
        response = "Our team will confirm this and follow up shortly."
        gaps = self._fn(customer, response)
        assert len(gaps) == 1
        assert len(gaps[0]["question"]) == 600

    def test_product_name_propagated(self):
        customer = "What is the warranty?"
        response = "Our team will follow up on the warranty."
        gaps = self._fn(customer, response, "Industrial Data Logger", "pid-dl")
        assert gaps[0]["product_name"] == "Industrial Data Logger"
        assert gaps[0]["product_id"] == "pid-dl"

    def test_empty_response_no_gaps(self):
        assert self._fn("Some question?", "") == []

    def test_empty_customer_text_no_gaps(self):
        assert self._fn("", "Our team will follow up.") == []


class TestInferTopic:
    def _fn(self, text):
        from app.services.sales_gap_service import infer_topic
        return infer_topic(text)

    def test_warranty_detected(self):
        assert self._fn("what is the warranty period?") == "warranty"

    def test_pricing_detected(self):
        assert self._fn("what is the bulk price for 10 units?") == "pricing"

    def test_technical_detected(self):
        assert self._fn("what accuracy does the sensor have?") == "technical"

    def test_availability_detected(self):
        assert self._fn("what is the lead time for delivery?") == "availability"

    def test_general_fallback(self):
        assert self._fn("tell me more about this") == "general"


class TestNodeGenerateDraftNoDuplicateRag:
    """Regression: node_generate_draft must not trigger a second RAG fetch."""

    def test_no_second_rag_fetch_when_rag_context_empty(self, db):
        """If node_fetch_rag returned '' (failed), generate_sales_draft must not re-fetch."""
        from app.services.workflows.email_nodes import node_generate_draft
        from unittest.mock import patch, MagicMock

        state = {
            "sender_raw": "cust@example.com",
            "subject": "Price query",
            "effective_body": "What is the price?",
            "rag_context": "",     # RAG already ran and returned nothing
            "product_id": None,
        }
        config = {"configurable": {"db": db, "gmail_svc": MagicMock()}}

        with patch("app.services.sales_gap_service.fetch_rag_context") as mock_rag, \
             patch("app.services.workflows.email_nodes.generate_sales_draft", return_value="Draft") as mock_draft:
            node_generate_draft(state, config)
            mock_rag.assert_not_called()
            # generate_sales_draft must be called with non-None rag_context
            call_kwargs = mock_draft.call_args
            assert call_kwargs.kwargs.get("rag_context") is not None or \
                   (call_kwargs.args and call_kwargs.args[3] is not None), \
                   "rag_context must not be None — would trigger second RAG fetch"
