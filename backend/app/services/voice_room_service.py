"""
voice_room_service.py — LiveKit room lifecycle management.

Responsibilities:
- Create/close LiveKit rooms via REST API
- Generate short-lived participant tokens (customer browser) + agent tokens
- Enforce rate limits (1 active session per lead)
- Build the browser join URL served by the /voice/call/{room} endpoint
- Handle session state transitions (PENDING → ACTIVE → COMPLETED/ESCALATED/EXPIRED)
"""

import hashlib
import hmac
import json
import logging
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

import httpx
import jwt as pyjwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.voice_session import (
    ChannelOrigin, EscalationType, VoiceSession, VoiceSessionStatus,
)

logger = logging.getLogger("rdl_app_logger")

_LK_API   = settings.LIVEKIT_API_URL.rstrip("/")
_LK_KEY   = settings.LIVEKIT_API_KEY
_LK_SEC   = settings.LIVEKIT_API_SECRET
_TTL_MIN  = settings.VOICE_TOKEN_TTL_MINUTES


# ── JWT helpers ──────────────────────────────────────────────────────────────

def _make_token(
    room_name: str,
    identity: str,
    *,
    can_publish: bool = False,
    can_subscribe: bool = True,
    ttl_seconds: int = _TTL_MIN * 60,
) -> tuple[str, datetime]:
    """Return (jwt_token, expires_at_utc)."""
    now = int(time.time())
    exp = now + ttl_seconds
    payload = {
        "iss": _LK_KEY,
        "sub": identity,
        "iat": now,
        "exp": exp,
        "nbf": now,
        "video": {
            "roomJoin": True,
            "room": room_name,
            "canPublish": can_publish,
            "canSubscribe": can_subscribe,
            "canPublishData": True,
        },
    }
    token = pyjwt.encode(payload, _LK_SEC, algorithm="HS256")
    expires_at = datetime.fromtimestamp(exp, tz=timezone.utc)
    return token, expires_at


def generate_agent_token(room_name: str) -> str:
    """Token for the LiveKit AI agent to join (publish + subscribe)."""
    token, _ = _make_token(room_name, identity="rdl-ai-agent", can_publish=True, ttl_seconds=3600)
    return token


def refresh_participant_token(session: VoiceSession) -> tuple[str, datetime]:
    """Generate a fresh 15-min participant token for an existing session."""
    return _make_token(
        session.room_name,
        identity=f"customer-{session.id}",
        can_publish=True,
    )


# ── LiveKit REST API ─────────────────────────────────────────────────────────

def _lk_headers() -> dict:
    """Authorization header using a short-lived admin token."""
    admin_token, _ = _make_token(
        room_name="",
        identity="rdl-backend",
        can_publish=False,
        ttl_seconds=60,
    )
    # Rebuild as admin claim (no room restrictions)
    now = int(time.time())
    payload = {
        "iss": _LK_KEY,
        "sub": "rdl-backend",
        "iat": now,
        "exp": now + 60,
        "video": {"roomCreate": True, "roomList": True, "roomAdmin": True},
    }
    admin_token = pyjwt.encode(payload, _LK_SEC, algorithm="HS256")
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


def _create_lk_room(room_name: str, max_participants: int = 2) -> bool:
    """Create a LiveKit room via REST. Returns True on success."""
    try:
        resp = httpx.post(
            f"{_LK_API}/twirp/livekit.RoomService/CreateRoom",
            headers=_lk_headers(),
            json={
                "name": room_name,
                "max_participants": max_participants,
                "empty_timeout": _TTL_MIN * 60 + 30,  # auto-close slightly after token TTL
            },
            timeout=10,
        )
        resp.raise_for_status()
        return True
    except Exception as exc:
        logger.warning(f"[VOICE] LiveKit CreateRoom failed for {room_name}: {exc}")
        return False


def _delete_lk_room(room_name: str) -> None:
    """Delete a LiveKit room via REST (best-effort)."""
    try:
        httpx.post(
            f"{_LK_API}/twirp/livekit.RoomService/DeleteRoom",
            headers=_lk_headers(),
            json={"room": room_name},
            timeout=10,
        )
    except Exception as exc:
        logger.warning(f"[VOICE] LiveKit DeleteRoom failed for {room_name}: {exc}")


# ── Session management ───────────────────────────────────────────────────────

def _build_join_url(room_name: str, token: str) -> str:
    """URL opened by the customer's browser."""
    base = settings.VOICE_BASE_URL.rstrip("/")
    return f"{base}/api/v1/voice/call/{room_name}?token={token}"


def get_active_session_for_lead(db: Session, lead_id: UUID) -> Optional[VoiceSession]:
    """Return an ACTIVE or PENDING session for this lead, if one exists."""
    return (
        db.query(VoiceSession)
        .filter(
            VoiceSession.lead_id == lead_id,
            VoiceSession.status.in_([VoiceSessionStatus.PENDING, VoiceSessionStatus.ACTIVE]),
        )
        .first()
    )


def count_active_sessions(db: Session) -> int:
    return (
        db.query(VoiceSession)
        .filter(VoiceSession.status.in_([VoiceSessionStatus.PENDING, VoiceSessionStatus.ACTIVE]))
        .count()
    )


def create_room(
    db: Session,
    *,
    channel_origin: str,
    owner_id: UUID,
    lead_id: Optional[UUID] = None,
    channel_ref_id: Optional[UUID] = None,
) -> tuple[VoiceSession, str]:
    """
    Create a LiveKit room and persist a VoiceSession.
    Returns (session, join_url).

    Raises ValueError if:
    - lead already has an active/pending session
    - concurrent session cap is reached
    """
    # Rate-limit: 1 active session per lead
    if lead_id:
        existing = get_active_session_for_lead(db, lead_id)
        if existing:
            token, expires_at = refresh_participant_token(existing)
            existing.participant_token = token
            existing.token_expires_at  = expires_at
            db.commit()
            db.refresh(existing)
            join_url = _build_join_url(existing.room_name, token)
            logger.info(f"[VOICE] Reusing existing session {existing.room_name} for lead {lead_id}")
            return existing, join_url

    # Concurrent cap
    active = count_active_sessions(db)
    if active >= settings.LIVEKIT_MAX_CONCURRENT_SESSIONS:
        raise ValueError(f"Concurrent session cap reached ({settings.LIVEKIT_MAX_CONCURRENT_SESSIONS})")

    room_name = f"rdl-{uuid.uuid4().hex}"
    participant_token, token_expires_at = _make_token(
        room_name,
        identity=f"customer-{uuid.uuid4().hex[:8]}",
        can_publish=True,
    )

    _create_lk_room(room_name)  # best-effort; webhook confirms actual state

    session = VoiceSession(
        room_name         = room_name,
        channel_origin    = channel_origin,
        channel_ref_id    = channel_ref_id,
        lead_id           = lead_id,
        owner_id          = owner_id,
        status            = VoiceSessionStatus.PENDING,
        participant_token = participant_token,
        token_expires_at  = token_expires_at,
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    join_url = _build_join_url(room_name, participant_token)
    logger.info(f"[VOICE] Created room {room_name} origin={channel_origin} lead={lead_id}")
    return session, join_url


def mark_session_active(db: Session, room_name: str) -> Optional[VoiceSession]:
    session = db.query(VoiceSession).filter(VoiceSession.room_name == room_name).first()
    if session and session.status == VoiceSessionStatus.PENDING:
        session.status    = VoiceSessionStatus.ACTIVE
        session.joined_at = datetime.utcnow()
        db.commit()
    return session


def complete_session(
    db: Session,
    room_name: str,
    *,
    duration_seconds: Optional[int] = None,
    transcript: Optional[str] = None,
    ai_summary: Optional[str] = None,
    unanswered_count: int = 0,
) -> Optional[VoiceSession]:
    """Called from the LiveKit webhook when a room finishes."""
    session = db.query(VoiceSession).filter(VoiceSession.room_name == room_name).first()
    if not session:
        return None
    if session.status not in (VoiceSessionStatus.ACTIVE, VoiceSessionStatus.PENDING):
        return session
    session.status           = VoiceSessionStatus.COMPLETED
    session.ended_at         = datetime.utcnow()
    session.duration_seconds = duration_seconds
    session.transcript       = transcript
    session.ai_summary       = ai_summary
    session.unanswered_count = unanswered_count
    db.commit()
    db.refresh(session)
    _delete_lk_room(room_name)
    logger.info(f"[VOICE] Session completed: {room_name} duration={duration_seconds}s gaps={unanswered_count}")
    return session


def expire_stale_sessions(db: Session) -> int:
    """Mark PENDING sessions whose token has expired as EXPIRED. Called every 5 min."""
    now = datetime.utcnow()
    rows = (
        db.query(VoiceSession)
        .filter(
            VoiceSession.status == VoiceSessionStatus.PENDING,
            VoiceSession.token_expires_at < now,
        )
        .all()
    )
    for s in rows:
        s.status = VoiceSessionStatus.EXPIRED
        _delete_lk_room(s.room_name)
    if rows:
        db.commit()
    return len(rows)


# ── Webhook signature verification ─────────────────────────────────────────

def verify_livekit_webhook_signature(body: bytes, authorization: str) -> bool:
    """
    LiveKit signs webhooks with HMAC-SHA256 of the raw body using the API secret.
    The Authorization header is the signature hex string.
    """
    if not _LK_SEC:
        return False
    try:
        # LiveKit uses JWT as the Authorization header, not HMAC.
        # Verify it's a valid JWT signed with our secret.
        decoded = pyjwt.decode(authorization, _LK_SEC, algorithms=["HS256"])
        # The token sub should be our key
        return decoded.get("iss") == _LK_KEY
    except Exception:
        return False


# ── Analytics helper ─────────────────────────────────────────────────────────

def get_voice_analytics(db: Session, owner_id_filter: Optional[UUID] = None) -> dict:
    query = db.query(VoiceSession)
    if owner_id_filter:
        query = query.filter(VoiceSession.owner_id == owner_id_filter)

    sessions = query.all()
    if not sessions:
        return {
            "total_sessions": 0, "active_now": 0, "completed": 0,
            "escalated": 0, "expired": 0, "avg_duration_seconds": None,
            "avg_unanswered_questions": 0.0, "escalation_rate": 0.0,
            "avg_feedback_score": None, "feedback_response_rate": 0.0,
            "by_channel": {"whatsapp": 0, "gmail": 0, "direct": 0},
            "by_escalation": {"none": 0, "gmeet": 0, "office_call": 0},
            "knowledge_gaps_captured": 0,
        }

    total     = len(sessions)
    active    = sum(1 for s in sessions if s.status == VoiceSessionStatus.ACTIVE)
    completed = sum(1 for s in sessions if s.status == VoiceSessionStatus.COMPLETED)
    escalated = sum(1 for s in sessions if s.status == VoiceSessionStatus.ESCALATED)
    expired   = sum(1 for s in sessions if s.status == VoiceSessionStatus.EXPIRED)

    durations  = [s.duration_seconds for s in sessions if s.duration_seconds]
    avg_dur    = sum(durations) / len(durations) if durations else None
    avg_unanswered = sum(s.unanswered_count for s in sessions) / total

    esc_rate   = (escalated / total * 100) if total else 0.0

    by_channel = {"whatsapp": 0, "gmail": 0, "direct": 0}
    by_esc     = {"none": 0, "gmeet": 0, "office_call": 0}
    for s in sessions:
        by_channel[s.channel_origin] = by_channel.get(s.channel_origin, 0) + 1
        by_esc[s.escalation_type]    = by_esc.get(s.escalation_type, 0) + 1

    # Count actual gap items stored in Call records from voice sessions
    # (more accurate than summing unanswered_count, which is the raw agent miss count)
    try:
        from app.models.call import Call
        voice_calls = (
            db.query(Call)
            .filter(
                Call.voice_session_id.in_([s.id for s in sessions]),
                Call.followup_gaps.isnot(None),
            )
            .all()
        )
        knowledge_gaps = sum(len(c.followup_gaps or []) for c in voice_calls)
    except Exception:
        knowledge_gaps = sum(s.unanswered_count for s in sessions if s.status == VoiceSessionStatus.COMPLETED)

    # Feedback
    from app.models.voice_session import VoiceCallFeedback
    fb_query = db.query(VoiceCallFeedback)
    if owner_id_filter:
        fb_query = fb_query.join(VoiceSession, VoiceCallFeedback.session_id == VoiceSession.id).filter(
            VoiceSession.owner_id == owner_id_filter
        )
    feedbacks = fb_query.all()
    avg_fb = (sum(f.rating for f in feedbacks) / len(feedbacks)) if feedbacks else None
    fb_rate = (len(feedbacks) / completed * 100) if completed else 0.0

    return {
        "total_sessions": total,
        "active_now": active,
        "completed": completed,
        "escalated": escalated,
        "expired": expired,
        "avg_duration_seconds": avg_dur,
        "avg_unanswered_questions": avg_unanswered,
        "escalation_rate": esc_rate,
        "avg_feedback_score": avg_fb,
        "feedback_response_rate": fb_rate,
        "by_channel": by_channel,
        "by_escalation": by_esc,
        "knowledge_gaps_captured": knowledge_gaps,
    }
