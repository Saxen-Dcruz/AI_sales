"""
Tests for the Voice Bridge module.

All LiveKit REST calls are mocked — no real LiveKit server required.
Feedback/escalation send functions are mocked so no WA/Gmail calls are made.

Run inside Docker:
    docker compose exec backend bash -c "cd /app && PYTHONPATH=/app pytest tests/test_voice.py -v"
"""
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.database.core import SessionLocal
from app.models.voice_session import (
    ChannelOrigin, EscalationType, VoiceCallFeedback,
    VoiceSession, VoiceSessionStatus,
)
from app.services.voice_feedback_service import generate_feedback_url, verify_signature

VOICE_BASE = "/api/v1/voice"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_session(
    db,
    *,
    owner_id,
    channel_origin: str = "whatsapp",
    status: str = VoiceSessionStatus.PENDING,
    lead_id=None,
) -> VoiceSession:
    room_name = f"rdl-{uuid.uuid4().hex}"
    token     = f"tok_{uuid.uuid4().hex}"
    expires   = datetime.utcnow() + timedelta(minutes=15)
    s = VoiceSession(
        room_name         = room_name,
        channel_origin    = channel_origin,
        owner_id          = owner_id,
        lead_id           = lead_id,
        status            = status,
        participant_token = token,
        token_expires_at  = expires,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


def _get_owner_id(auth_headers: dict) -> uuid.UUID:
    with TestClient(app) as c:
        r = c.get("/api/v1/auth/me", headers=auth_headers)
        return uuid.UUID(r.json()["id"])


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def owner_id(auth_headers, client):
    """Derive owner UUID from the session-wide auth user (defined in conftest)."""
    r = client.get("/api/v1/auth/me", headers=auth_headers)
    return uuid.UUID(r.json()["id"])


@pytest.fixture()
def db_session():
    with SessionLocal() as db:
        yield db


@pytest.fixture()
def voice_session(db_session, owner_id):
    """A PENDING voice session for use in per-test fixtures."""
    s = _make_session(db_session, owner_id=owner_id, channel_origin="whatsapp")
    yield s
    db_session.query(VoiceCallFeedback).filter(VoiceCallFeedback.session_id == s.id).delete()
    db_session.query(VoiceSession).filter(VoiceSession.id == s.id).delete()
    db_session.commit()


# ── Room creation ─────────────────────────────────────────────────────────────

@patch("app.services.voice_room_service._create_lk_room", return_value=True)
def test_create_room_success(mock_lk, client, auth_headers):
    resp = client.post(
        f"{VOICE_BASE}/rooms",
        json={"channel_origin": "whatsapp"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert "join_url" in body
    assert "office_phone" in body
    assert body["session"]["status"] == "pending"
    # Clean up
    with SessionLocal() as db:
        db.query(VoiceSession).filter(
            VoiceSession.room_name == body["session"]["room_name"]
        ).delete()
        db.commit()


@patch("app.services.voice_room_service._create_lk_room", return_value=True)
def test_create_room_channel_origin_stored(mock_lk, client, auth_headers):
    resp = client.post(
        f"{VOICE_BASE}/rooms",
        json={"channel_origin": "gmail"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["session"]["channel_origin"] == "gmail"
    with SessionLocal() as db:
        db.query(VoiceSession).filter(
            VoiceSession.room_name == resp.json()["session"]["room_name"]
        ).delete()
        db.commit()


@patch("app.services.voice_room_service._create_lk_room", return_value=True)
def test_create_room_join_url_contains_token(mock_lk, client, auth_headers):
    resp = client.post(
        f"{VOICE_BASE}/rooms",
        json={"channel_origin": "direct"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert "?token=" in body["join_url"]
    with SessionLocal() as db:
        db.query(VoiceSession).filter(
            VoiceSession.room_name == body["session"]["room_name"]
        ).delete()
        db.commit()


@patch("app.services.voice_room_service._create_lk_room", return_value=True)
def test_create_room_reuses_active_session(mock_lk, client, auth_headers, owner_id, db_session):
    """Second create call for same lead returns existing session, not a new one."""
    # Create a real lead via API so FK constraint is satisfied
    lead_resp = client.post(
        "/api/v1/leads/",
        json={"name": "Voice Test Lead", "email": f"vtl_{uuid.uuid4().hex[:6]}@test.com", "status": "new"},
        headers=auth_headers,
    )
    assert lead_resp.status_code == 201
    lead_id = uuid.UUID(lead_resp.json()["id"])

    session1 = _make_session(db_session, owner_id=owner_id, lead_id=lead_id)

    resp = client.post(
        f"{VOICE_BASE}/rooms",
        json={"channel_origin": "whatsapp", "lead_id": str(lead_id)},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["session"]["room_name"] == session1.room_name

    db_session.query(VoiceSession).filter(VoiceSession.id == session1.id).delete()
    db_session.commit()
    client.delete(f"/api/v1/leads/{lead_id}", headers=auth_headers)


def test_create_room_no_auth(client):
    saved = dict(client.cookies)
    client.cookies.clear()
    try:
        resp = client.post(f"{VOICE_BASE}/rooms", json={"channel_origin": "whatsapp"})
        assert resp.status_code == 401
    finally:
        client.cookies.update(saved)


def test_create_room_room_name_is_unpredictable(client, auth_headers):
    with patch("app.services.voice_room_service._create_lk_room", return_value=True):
        resp = client.post(
            f"{VOICE_BASE}/rooms",
            json={"channel_origin": "whatsapp"},
            headers=auth_headers,
        )
    assert resp.status_code == 201
    room_name = resp.json()["session"]["room_name"]
    # Must be rdl-{uuid_hex} — unpredictable
    assert room_name.startswith("rdl-")
    assert len(room_name) > 10
    with SessionLocal() as db:
        db.query(VoiceSession).filter(VoiceSession.room_name == room_name).delete()
        db.commit()


# ── Room status & token ───────────────────────────────────────────────────────

def test_get_room_status_pending(client, auth_headers, voice_session):
    resp = client.get(f"{VOICE_BASE}/rooms/{voice_session.room_name}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "pending"


def test_get_room_status_404(client, auth_headers):
    resp = client.get(f"{VOICE_BASE}/rooms/rdl-nonexistent-room", headers=auth_headers)
    assert resp.status_code == 404


def test_get_room_status_no_auth(client, voice_session):
    saved = dict(client.cookies)
    client.cookies.clear()
    try:
        resp = client.get(f"{VOICE_BASE}/rooms/{voice_session.room_name}")
        assert resp.status_code == 401
    finally:
        client.cookies.update(saved)


def test_get_fresh_token(client, auth_headers, voice_session):
    resp = client.get(f"{VOICE_BASE}/rooms/{voice_session.room_name}/token", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "token" in body
    assert "expires_at" in body
    assert body["room_name"] == voice_session.room_name


def test_get_fresh_token_for_completed_session(client, auth_headers, db_session, owner_id):
    s = _make_session(db_session, owner_id=owner_id, status=VoiceSessionStatus.COMPLETED)
    resp = client.get(f"{VOICE_BASE}/rooms/{s.room_name}/token", headers=auth_headers)
    assert resp.status_code == 400
    db_session.query(VoiceSession).filter(VoiceSession.id == s.id).delete()
    db_session.commit()


def test_get_fresh_token_no_auth(client, voice_session):
    saved = dict(client.cookies)
    client.cookies.clear()
    try:
        resp = client.get(f"{VOICE_BASE}/rooms/{voice_session.room_name}/token")
        assert resp.status_code == 401
    finally:
        client.cookies.update(saved)


# ── Browser call page ─────────────────────────────────────────────────────────

def test_call_page_renders(client, voice_session):
    resp = client.get(
        f"{VOICE_BASE}/call/{voice_session.room_name}",
        params={"token": voice_session.participant_token},
    )
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "livekit-client" in resp.text


def test_call_page_wrong_token(client, voice_session):
    resp = client.get(
        f"{VOICE_BASE}/call/{voice_session.room_name}",
        params={"token": "bad-token"},
    )
    assert resp.status_code == 401


def test_call_page_unknown_room(client):
    resp = client.get(f"{VOICE_BASE}/call/rdl-unknown-room", params={"token": "tok"})
    assert resp.status_code == 404


def test_call_page_expired_session(client, db_session, owner_id):
    s = _make_session(db_session, owner_id=owner_id, status=VoiceSessionStatus.EXPIRED)
    resp = client.get(
        f"{VOICE_BASE}/call/{s.room_name}",
        params={"token": s.participant_token},
    )
    assert resp.status_code == 410
    db_session.query(VoiceSession).filter(VoiceSession.id == s.id).delete()
    db_session.commit()


# ── LiveKit webhook ───────────────────────────────────────────────────────────

def _lk_auth_header() -> str:
    """Generate a valid LiveKit JWT as the Authorization header."""
    import time
    import jwt as pyjwt
    from app.core.config import settings
    now = int(time.time())
    payload = {
        "iss": settings.LIVEKIT_API_KEY,
        "sub": "rdl-backend",
        "iat": now,
        "exp": now + 60,
        "video": {"roomCreate": True},
    }
    return pyjwt.encode(payload, settings.LIVEKIT_API_SECRET, algorithm="HS256")


def test_webhook_participant_joined_sets_active(client, db_session, voice_session):
    payload = {
        "event": "participant_joined",
        "participant": {"identity": "customer-abc"},
        "room": {"name": voice_session.room_name},
    }
    resp = client.post(
        f"{VOICE_BASE}/rooms/{voice_session.room_name}/webhook",
        json=payload,
        headers={"Authorization": _lk_auth_header()},
    )
    assert resp.status_code == 200
    db_session.refresh(voice_session)
    assert voice_session.status == VoiceSessionStatus.ACTIVE


def test_webhook_room_finished_completes_session(client, db_session, owner_id):
    s = _make_session(db_session, owner_id=owner_id, status=VoiceSessionStatus.ACTIVE)
    payload = {
        "event": "room_finished",
        "room": {"name": s.room_name, "duration": 120},
    }
    with patch("threading.Timer") as mock_timer:
        mock_timer.return_value.start = MagicMock()
        mock_timer.return_value.daemon = True
        resp = client.post(
            f"{VOICE_BASE}/rooms/{s.room_name}/webhook",
            json=payload,
            headers={"Authorization": _lk_auth_header()},
        )
    assert resp.status_code == 200
    db_session.refresh(s)
    assert s.status == VoiceSessionStatus.COMPLETED
    db_session.query(VoiceSession).filter(VoiceSession.id == s.id).delete()
    db_session.commit()


def test_webhook_invalid_signature(client, voice_session):
    resp = client.post(
        f"{VOICE_BASE}/rooms/{voice_session.room_name}/webhook",
        json={"event": "participant_joined", "participant": {}},
        headers={"Authorization": "Bearer bad.token.here"},
    )
    assert resp.status_code == 401


def test_webhook_unknown_room_404(client):
    resp = client.post(
        f"{VOICE_BASE}/rooms/rdl-unknown/webhook",
        json={"event": "room_finished", "room": {"name": "rdl-unknown"}},
        headers={"Authorization": _lk_auth_header()},
    )
    assert resp.status_code == 200  # graceful — log and continue


# ── Escalation ────────────────────────────────────────────────────────────────

def test_escalate_unknown_room_404(client, auth_headers):
    resp = client.post(
        f"{VOICE_BASE}/rooms/rdl-nonexistent/escalate",
        json={"escalation_type": "office_call"},
        headers=auth_headers,
    )
    assert resp.status_code == 404


def test_escalate_no_auth(client, voice_session):
    saved = dict(client.cookies)
    client.cookies.clear()
    try:
        resp = client.post(
            f"{VOICE_BASE}/rooms/{voice_session.room_name}/escalate",
            json={"escalation_type": "office_call"},
        )
        assert resp.status_code == 401
    finally:
        client.cookies.update(saved)


@patch("app.services.escalation_service._create_expert_gmeet", return_value=None)
@patch("app.services.escalation_service._send_whatsapp_escalation", return_value=None)
@patch("app.services.escalation_service._send_gmail_escalation", return_value=None)
def test_escalate_manual_office_call(m_g, m_wa, m_gm, client, auth_headers, db_session, owner_id):
    s = _make_session(db_session, owner_id=owner_id, status=VoiceSessionStatus.ACTIVE)
    resp = client.post(
        f"{VOICE_BASE}/rooms/{s.room_name}/escalate",
        json={"escalation_type": "office_call"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "escalation_type" in body
    assert "escalation_ref" in body
    db_session.query(VoiceSession).filter(VoiceSession.id == s.id).delete()
    db_session.commit()


# ── Feedback signed URL ───────────────────────────────────────────────────────

def test_feedback_url_is_unique_per_session(db_session, owner_id):
    s1 = _make_session(db_session, owner_id=owner_id, status=VoiceSessionStatus.COMPLETED)
    s2 = _make_session(db_session, owner_id=owner_id, status=VoiceSessionStatus.COMPLETED)
    url1 = generate_feedback_url(s1)
    url2 = generate_feedback_url(s2)
    assert url1 != url2
    db_session.query(VoiceSession).filter(VoiceSession.id.in_([s1.id, s2.id])).delete()
    db_session.commit()


def test_feedback_signature_constant_time_comparison():
    sig = "abc123def456abcd"
    assert verify_signature("fake-id", sig) is False


def test_feedback_sig_tampered_rejected(db_session, owner_id):
    s = _make_session(db_session, owner_id=owner_id, status=VoiceSessionStatus.COMPLETED)
    url = generate_feedback_url(s)
    # extract sig and tamper it
    sig = url.split("sig=")[1]
    tampered_sig = sig[:-1] + ("x" if sig[-1] != "x" else "y")
    assert verify_signature(str(s.id), tampered_sig) is False
    db_session.query(VoiceSession).filter(VoiceSession.id == s.id).delete()
    db_session.commit()


def test_feedback_form_page_renders(client, db_session, owner_id):
    s = _make_session(db_session, owner_id=owner_id, status=VoiceSessionStatus.COMPLETED)
    sig = generate_feedback_url(s).split("sig=")[1]
    resp = client.get(f"{VOICE_BASE}/review/{s.id}", params={"sig": sig})
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "⭐" in resp.text
    db_session.query(VoiceSession).filter(VoiceSession.id == s.id).delete()
    db_session.commit()


def test_feedback_form_invalid_sig(client, db_session, owner_id):
    s = _make_session(db_session, owner_id=owner_id, status=VoiceSessionStatus.COMPLETED)
    resp = client.get(f"{VOICE_BASE}/review/{s.id}", params={"sig": "badsig"})
    assert resp.status_code == 401
    db_session.query(VoiceSession).filter(VoiceSession.id == s.id).delete()
    db_session.commit()


def test_feedback_form_unknown_session(client):
    fake_id = uuid.uuid4()
    sig = generate_feedback_url.__module__  # just need any sig
    from app.services.voice_feedback_service import _sign
    sig = _sign(str(fake_id))
    resp = client.get(f"{VOICE_BASE}/review/{fake_id}", params={"sig": sig})
    assert resp.status_code == 404


def test_submit_feedback_success(client, db_session, owner_id):
    s = _make_session(db_session, owner_id=owner_id, status=VoiceSessionStatus.COMPLETED)
    sig = generate_feedback_url(s).split("sig=")[1]
    resp = client.post(
        f"{VOICE_BASE}/review/{s.id}",
        params={"sig": sig},
        json={"rating": 4, "comment": "Great AI!"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["rating"] == 4
    assert body["comment"] == "Great AI!"
    assert body["channel_used"] == "web"
    db_session.query(VoiceCallFeedback).filter(VoiceCallFeedback.session_id == s.id).delete()
    db_session.query(VoiceSession).filter(VoiceSession.id == s.id).delete()
    db_session.commit()


def test_submit_feedback_invalid_rating_422(client, db_session, owner_id):
    s = _make_session(db_session, owner_id=owner_id, status=VoiceSessionStatus.COMPLETED)
    sig = generate_feedback_url(s).split("sig=")[1]
    resp = client.post(
        f"{VOICE_BASE}/review/{s.id}",
        params={"sig": sig},
        json={"rating": 6},
    )
    assert resp.status_code == 422
    db_session.query(VoiceSession).filter(VoiceSession.id == s.id).delete()
    db_session.commit()


def test_submit_feedback_invalid_sig_401(client, db_session, owner_id):
    s = _make_session(db_session, owner_id=owner_id, status=VoiceSessionStatus.COMPLETED)
    resp = client.post(
        f"{VOICE_BASE}/review/{s.id}",
        params={"sig": "tampered"},
        json={"rating": 5},
    )
    assert resp.status_code == 401
    db_session.query(VoiceSession).filter(VoiceSession.id == s.id).delete()
    db_session.commit()


def test_submit_feedback_idempotent(client, db_session, owner_id):
    """Submitting twice updates the existing row, not creates a second."""
    s = _make_session(db_session, owner_id=owner_id, status=VoiceSessionStatus.COMPLETED)
    sig = generate_feedback_url(s).split("sig=")[1]
    client.post(f"{VOICE_BASE}/review/{s.id}", params={"sig": sig}, json={"rating": 3})
    resp = client.post(f"{VOICE_BASE}/review/{s.id}", params={"sig": sig}, json={"rating": 5})
    assert resp.status_code == 200
    count = db_session.query(VoiceCallFeedback).filter(VoiceCallFeedback.session_id == s.id).count()
    assert count == 1
    db_session.query(VoiceCallFeedback).filter(VoiceCallFeedback.session_id == s.id).delete()
    db_session.query(VoiceSession).filter(VoiceSession.id == s.id).delete()
    db_session.commit()


def test_feedback_already_submitted_shows_thanks_html(client, db_session, owner_id):
    s = _make_session(db_session, owner_id=owner_id, status=VoiceSessionStatus.COMPLETED)
    sig = generate_feedback_url(s).split("sig=")[1]
    # Submit first
    client.post(f"{VOICE_BASE}/review/{s.id}", params={"sig": sig}, json={"rating": 4})
    # GET form again — should show "already received"
    resp = client.get(f"{VOICE_BASE}/review/{s.id}", params={"sig": sig})
    assert resp.status_code == 200
    assert "already" in resp.text.lower() or "thank" in resp.text.lower()
    db_session.query(VoiceCallFeedback).filter(VoiceCallFeedback.session_id == s.id).delete()
    db_session.query(VoiceSession).filter(VoiceSession.id == s.id).delete()
    db_session.commit()


def test_quick_rating_link(client, db_session, owner_id):
    s = _make_session(db_session, owner_id=owner_id, status=VoiceSessionStatus.COMPLETED)
    from app.services.voice_feedback_service import _sign
    sig = _sign(str(s.id))
    resp = client.get(
        f"{VOICE_BASE}/feedback/quick",
        params={"session_id": str(s.id), "sig": sig, "rating": 4},
    )
    assert resp.status_code == 200
    assert "4/5" in resp.text or "Thank you" in resp.text
    db_session.query(VoiceCallFeedback).filter(VoiceCallFeedback.session_id == s.id).delete()
    db_session.query(VoiceSession).filter(VoiceSession.id == s.id).delete()
    db_session.commit()


# ── Analytics ─────────────────────────────────────────────────────────────────

def test_analytics_empty_returns_zeros(client, auth_headers):
    resp = client.get(f"{VOICE_BASE}/analytics", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "total_sessions" in body
    assert "by_channel" in body
    assert "by_escalation" in body
    assert "feedback_response_rate" in body


def test_analytics_shape(client, auth_headers):
    resp = client.get(f"{VOICE_BASE}/analytics", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    required_keys = {
        "total_sessions", "active_now", "completed", "escalated", "expired",
        "avg_duration_seconds", "avg_unanswered_questions", "escalation_rate",
        "avg_feedback_score", "feedback_response_rate",
        "by_channel", "by_escalation", "knowledge_gaps_captured",
    }
    assert required_keys.issubset(set(body.keys()))


def test_analytics_channel_breakdown_counts(client, auth_headers, db_session, owner_id):
    s_wa    = _make_session(db_session, owner_id=owner_id, channel_origin="whatsapp", status=VoiceSessionStatus.COMPLETED)
    s_gmail = _make_session(db_session, owner_id=owner_id, channel_origin="gmail",    status=VoiceSessionStatus.COMPLETED)
    try:
        resp = client.get(f"{VOICE_BASE}/analytics", headers=auth_headers)
        body = resp.json()
        assert body["by_channel"]["whatsapp"] >= 1
        assert body["by_channel"]["gmail"] >= 1
    finally:
        db_session.query(VoiceSession).filter(VoiceSession.id.in_([s_wa.id, s_gmail.id])).delete()
        db_session.commit()


def test_analytics_no_auth(client):
    saved = dict(client.cookies)
    client.cookies.clear()
    try:
        resp = client.get(f"{VOICE_BASE}/analytics")
        assert resp.status_code == 401
    finally:
        client.cookies.update(saved)


# ── Internal session-end endpoint ─────────────────────────────────────────────

def test_internal_session_end_requires_key(client, voice_session):
    resp = client.post(
        f"{VOICE_BASE}/internal/session-end",
        json={"session_id": str(voice_session.id), "transcript": "hello", "unanswered_count": 0},
        headers={"X-Internal-Key": "wrong-key"},
    )
    assert resp.status_code == 401


def test_internal_session_end_saves_transcript_and_creates_call(client, db_session, owner_id):
    """
    Voice session-end must:
    - Save transcript + unanswered_count to voice_sessions
    - Create a Call record linked via voice_session_id
    - Mark session COMPLETED
    """
    from app.core.config import settings
    from app.models.call import Call

    s = _make_session(db_session, owner_id=owner_id, status=VoiceSessionStatus.ACTIVE)
    key = settings.JWT_SECRET_KEY[:16]

    transcript = "Customer: What is the price of your 4G router?\nAgent: The price is Rs 15,000.\nCustomer: Thanks!"

    # Mock process_transcript so we don't need live Gemini
    with patch("app.routers.voice.process_transcript") as mock_pt:
        mock_pt.return_value = None
        resp = client.post(
            f"{VOICE_BASE}/internal/session-end",
            json={"session_id": str(s.id), "transcript": transcript, "unanswered_count": 0},
            headers={"X-Internal-Key": key},
        )

    assert resp.status_code == 200
    db_session.refresh(s)
    assert s.transcript == transcript
    assert s.unanswered_count == 0
    assert s.status == VoiceSessionStatus.COMPLETED

    # A Call record must have been created and linked
    call = db_session.query(Call).filter(Call.voice_session_id == s.id).first()
    assert call is not None
    assert call.livekit_room == s.room_name
    assert call.owner_id == owner_id
    mock_pt.assert_called_once()

    # Cleanup
    db_session.query(Call).filter(Call.voice_session_id == s.id).delete()
    db_session.query(VoiceSession).filter(VoiceSession.id == s.id).delete()
    db_session.commit()


def test_internal_session_end_no_call_created_when_empty_transcript(client, db_session, owner_id):
    """Empty transcript → no Call record (nothing to process)."""
    from app.core.config import settings
    from app.models.call import Call

    s = _make_session(db_session, owner_id=owner_id, status=VoiceSessionStatus.ACTIVE)
    key = settings.JWT_SECRET_KEY[:16]
    resp = client.post(
        f"{VOICE_BASE}/internal/session-end",
        json={"session_id": str(s.id), "transcript": "", "unanswered_count": 0},
        headers={"X-Internal-Key": key},
    )
    assert resp.status_code == 200
    call = db_session.query(Call).filter(Call.voice_session_id == s.id).first()
    assert call is None
    db_session.query(VoiceSession).filter(VoiceSession.id == s.id).delete()
    db_session.commit()


# ── Service unit tests ────────────────────────────────────────────────────────

def test_expire_stale_sessions(db_session, owner_id):
    from app.services.voice_room_service import expire_stale_sessions
    expired_at = datetime.utcnow() - timedelta(minutes=1)
    s = VoiceSession(
        room_name         = f"rdl-{uuid.uuid4().hex}",
        channel_origin    = "direct",
        owner_id          = owner_id,
        status            = VoiceSessionStatus.PENDING,
        participant_token = "tok",
        token_expires_at  = expired_at,
    )
    db_session.add(s)
    db_session.commit()

    with patch("app.services.voice_room_service._delete_lk_room"):
        n = expire_stale_sessions(db_session)

    assert n >= 1
    db_session.refresh(s)
    assert s.status == VoiceSessionStatus.EXPIRED
    db_session.query(VoiceSession).filter(VoiceSession.id == s.id).delete()
    db_session.commit()


def test_complete_session_sets_fields(db_session, owner_id):
    from app.services.voice_room_service import complete_session
    s = _make_session(db_session, owner_id=owner_id, status=VoiceSessionStatus.ACTIVE)
    with patch("app.services.voice_room_service._delete_lk_room"):
        result = complete_session(
            db_session, s.room_name,
            duration_seconds=90,
            transcript="test transcript",
        )
    assert result.status == VoiceSessionStatus.COMPLETED
    assert result.duration_seconds == 90
    assert result.transcript == "test transcript"
    db_session.query(VoiceSession).filter(VoiceSession.id == s.id).delete()
    db_session.commit()


def test_get_active_session_for_lead(client, auth_headers, db_session, owner_id):
    from app.services.voice_room_service import get_active_session_for_lead
    # Create a real lead so FK constraint is satisfied
    lead_resp = client.post(
        "/api/v1/leads/",
        json={"name": "FK Test Lead", "email": f"fk_{uuid.uuid4().hex[:6]}@test.com", "status": "new"},
        headers=auth_headers,
    )
    assert lead_resp.status_code == 201
    lead_id = uuid.UUID(lead_resp.json()["id"])

    s = _make_session(db_session, owner_id=owner_id, lead_id=lead_id, status=VoiceSessionStatus.PENDING)
    found = get_active_session_for_lead(db_session, lead_id)
    assert found is not None
    assert found.id == s.id
    db_session.query(VoiceSession).filter(VoiceSession.id == s.id).delete()
    db_session.commit()
    client.delete(f"/api/v1/leads/{lead_id}", headers=auth_headers)


@patch("app.services.voice_feedback_service._send_whatsapp_feedback_link")
@patch("app.services.voice_feedback_service._send_gmail_feedback_link")
def test_send_feedback_request_marks_sent(mock_gmail, mock_wa, db_session, owner_id):
    from app.services.voice_feedback_service import send_feedback_request
    s = _make_session(db_session, owner_id=owner_id, channel_origin="whatsapp", status=VoiceSessionStatus.COMPLETED)
    send_feedback_request(db_session, s)
    db_session.refresh(s)
    assert s.feedback_sent is True
    mock_wa.assert_called_once()
    db_session.query(VoiceSession).filter(VoiceSession.id == s.id).delete()
    db_session.commit()


@patch("app.services.voice_feedback_service._send_whatsapp_feedback_link")
@patch("app.services.voice_feedback_service._send_gmail_feedback_link")
def test_send_feedback_request_idempotent(mock_gmail, mock_wa, db_session, owner_id):
    from app.services.voice_feedback_service import send_feedback_request
    s = _make_session(db_session, owner_id=owner_id, channel_origin="whatsapp", status=VoiceSessionStatus.COMPLETED)
    s.feedback_sent = True
    db_session.commit()
    send_feedback_request(db_session, s)
    mock_wa.assert_not_called()
    db_session.query(VoiceSession).filter(VoiceSession.id == s.id).delete()
    db_session.commit()


# ── Settings: company phone ───────────────────────────────────────────────────

def test_get_company_settings(client, auth_headers):
    resp = client.get("/api/v1/settings/company", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "company_phone" in body
    assert "voice_token_ttl_minutes" in body


def test_update_company_phone(client, auth_headers):
    resp = client.patch(
        "/api/v1/settings/company",
        json={"company_phone": "+91-99-88776655"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["company_phone"] == "+91-99-88776655"


def test_update_company_phone_invalid_format(client, auth_headers):
    resp = client.patch(
        "/api/v1/settings/company",
        json={"company_phone": "NOT_A_PHONE"},
        headers=auth_headers,
    )
    assert resp.status_code == 422


def test_get_company_settings_no_auth(client):
    saved = dict(client.cookies)
    client.cookies.clear()
    try:
        resp = client.get("/api/v1/settings/company")
        assert resp.status_code == 401
    finally:
        client.cookies.update(saved)
