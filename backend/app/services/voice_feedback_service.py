"""
voice_feedback_service.py — Post-call feedback via unique signed URL.

Flow:
  1. Call ends → generate_feedback_url(session) creates a HMAC-signed URL
  2. URL sent as a single link in WhatsApp message OR email
     e.g. https://rdltech.in/api/v1/voice/review/{session_id}?sig=<hmac>
  3. Customer clicks → GET /voice/review/{session_id}?sig=<sig>
     → Server verifies HMAC → serves a branded HTML feedback form
     → Pre-filled with session context (no user inputs for identity)
  4. Customer selects 1–5 stars + optional comment → submits the form
     → POST /voice/review/{session_id}?sig=<sig>
     → Signature re-verified → feedback stored → "Thank you" page shown
  5. Lead score updated if rating ≤ 2
"""

import hashlib
import hmac
import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.voice_session import ChannelOrigin, VoiceCallFeedback, VoiceSession, VoiceSessionStatus

logger = logging.getLogger("rdl_app_logger")

_HMAC_KEY = settings.JWT_SECRET_KEY[:32].encode()


# ── Signed URL helpers ────────────────────────────────────────────────────────

def _sign(session_id: str) -> str:
    """HMAC-SHA256 of the session ID, first 16 hex chars (64-bit)."""
    return hmac.new(_HMAC_KEY, session_id.encode(), hashlib.sha256).hexdigest()[:16]


def verify_signature(session_id: str, sig: str) -> bool:
    """Constant-time comparison to prevent timing attacks."""
    expected = _sign(session_id)
    return hmac.compare_digest(expected, sig)


def generate_feedback_url(session: VoiceSession) -> str:
    """Return the unique feedback form URL for this session."""
    sig  = _sign(str(session.id))
    base = settings.VOICE_BASE_URL.rstrip("/")
    return f"{base}/api/v1/voice/review/{session.id}?sig={sig}"


# ── Sender helpers ────────────────────────────────────────────────────────────

def _send_whatsapp_feedback_link(db: Session, session: VoiceSession, url: str) -> None:
    try:
        from app.services.whatsapp_service import send_text_message
        from app.models.whatsapp_account import WhatsAppAccount
        from app.models.leads import Lead

        lead = db.query(Lead).filter(Lead.id == session.lead_id).first() if session.lead_id else None
        if not lead or not lead.phone:
            return

        account = (
            db.query(WhatsAppAccount)
            .filter(WhatsAppAccount.owner_id == session.owner_id, WhatsAppAccount.is_active == True)
            .first()
        )
        if not account:
            return

        msg = (
            f"Thank you for speaking with our AI assistant!\n\n"
            f"We'd love to hear how it went. Tap the link below to share your experience "
            f"(takes 10 seconds, no login needed):\n\n"
            f"{url}\n\n"
            f"— RDL Technologies Team"
        )
        send_text_message(account, lead.phone, msg)
        logger.info(f"[FEEDBACK] WhatsApp feedback link sent: session={session.id}")
    except Exception as exc:
        logger.warning(f"[FEEDBACK] WhatsApp send failed: {exc}")


def _send_gmail_feedback_link(db: Session, session: VoiceSession, url: str) -> None:
    try:
        from app.services.gmail_service import send_email, get_gmail_service
        from app.models.leads import Lead

        lead = db.query(Lead).filter(Lead.id == session.lead_id).first() if session.lead_id else None
        if not lead or not lead.email:
            return

        name  = lead.name or "there"
        body  = (
            f"Hi {name},\n\n"
            f"Thank you for trying RDL's AI voice assistant today!\n\n"
            f"It takes less than 10 seconds to rate your experience — and it helps us "
            f"improve for every future call:\n\n"
            f"Rate your experience here:\n{url}\n\n"
            f"No login or account needed — the link is personalized for you.\n\n"
            f"Best regards,\nRDL Technologies Sales Team"
        )
        gmail_svc = get_gmail_service()
        send_email(
            service = gmail_svc,
            to      = lead.email,
            subject = "How was your RDL AI voice experience? (10 sec)",
            body    = body,
        )
        logger.info(f"[FEEDBACK] Gmail feedback link sent: session={session.id}")
    except Exception as exc:
        logger.warning(f"[FEEDBACK] Gmail send failed: {exc}")


def send_feedback_request(db: Session, session: VoiceSession) -> None:
    """
    Generate the signed feedback URL and dispatch it via the session's channel.
    Safe to call multiple times — feedback_sent flag prevents duplicates.
    """
    if session.feedback_sent:
        return
    if session.status not in (VoiceSessionStatus.COMPLETED, VoiceSessionStatus.ESCALATED):
        return

    url = generate_feedback_url(session)

    origin = session.channel_origin
    if origin == ChannelOrigin.WHATSAPP:
        _send_whatsapp_feedback_link(db, session, url)
    elif origin == ChannelOrigin.GMAIL:
        _send_gmail_feedback_link(db, session, url)
    else:
        # Direct or unknown — try both channels
        _send_whatsapp_feedback_link(db, session, url)
        _send_gmail_feedback_link(db, session, url)

    session.feedback_sent = True
    db.commit()


# ── Feedback submission ───────────────────────────────────────────────────────

def submit_feedback(
    db: Session,
    session_id: UUID,
    rating: int,
    *,
    comment: Optional[str] = None,
    channel_used: str = "web",
) -> VoiceCallFeedback:
    """
    Store feedback. Idempotent — updates existing row if already submitted.
    Raises LookupError if session not found, ValueError if rating out of range.
    """
    if not 1 <= rating <= 5:
        raise ValueError("rating must be between 1 and 5")

    session = db.query(VoiceSession).filter(VoiceSession.id == session_id).first()
    if not session:
        raise LookupError(f"Voice session {session_id} not found")

    existing = (
        db.query(VoiceCallFeedback)
        .filter(VoiceCallFeedback.session_id == session_id)
        .first()
    )
    if existing:
        existing.rating       = rating
        existing.comment      = comment
        existing.channel_used = channel_used
        existing.submitted_at = datetime.utcnow()
        db.commit()
        db.refresh(existing)
        fb = existing
    else:
        fb = VoiceCallFeedback(
            session_id   = session_id,
            lead_id      = session.lead_id,
            rating       = rating,
            comment      = comment,
            channel_used = channel_used,
        )
        db.add(fb)
        db.commit()
        db.refresh(fb)

    if rating <= 2 and session.lead_id:
        try:
            from app.services.lead_scoring_service import update_lead_score
            update_lead_score(db, session.lead_id)
        except Exception as exc:
            logger.warning(f"[FEEDBACK] Lead score update failed: {exc}")

    logger.info(f"[FEEDBACK] Submitted: session={session_id} rating={rating}")
    return fb
