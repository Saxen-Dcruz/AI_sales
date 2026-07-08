"""
escalation_service.py — Voice call escalation to human paths.

Two escalation options (always send both):
  Option 2: Office phone number (immediate, zero wait)
  Option 3: Google Meet with a human expert (scheduled)

Triggered when:
  - Agent detects ≥ VOICE_ESCALATION_THRESHOLD consecutive unanswered questions
  - Customer says "speak to human / connect me / I need a person"
  - Manual trigger from POST /voice/rooms/{room}/escalate endpoint

Channel routing:
  - channel_origin=whatsapp → send WA interactive buttons (GMeet URL + phone)
  - channel_origin=gmail    → send reply email with both options
  - channel_origin=direct   → send via lead's preferred channel if known
"""

import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.voice_session import ChannelOrigin, EscalationType, VoiceSession, VoiceSessionStatus

logger = logging.getLogger("rdl_app_logger")

OFFICE_PHONE = settings.COMPANY_PHONE


def _create_expert_gmeet(db: Session, session: VoiceSession) -> Optional[str]:
    """Schedule a GMeet for immediate or next-available slot. Returns meet URL."""
    try:
        from app.services.calendar_service import create_meeting, find_next_free_slot
        from app.models.leads import Lead

        lead = db.query(Lead).filter(Lead.id == session.lead_id).first() if session.lead_id else None
        attendee = lead.email if lead and lead.email else None
        if not attendee:
            return None

        start_time = find_next_free_slot(duration_minutes=30, hours_from_now=1)
        event = create_meeting(
            db           = db,
            attendee_email = attendee,
            title        = "RDL Expert Consultation (from AI Voice Bridge)",
            description  = (
                f"This meeting was auto-scheduled because the AI voice agent could not "
                f"fully answer your questions. A product expert will join to assist you.\n\n"
                f"Session ID: {session.id}"
            ),
            start_time   = start_time,
            owner_id     = session.owner_id,
            duration_minutes = 30,
            lead_id      = session.lead_id,
        )
        return event.meet_link
    except Exception as exc:
        logger.warning(f"[ESCALATION] GMeet creation failed: {exc}")
        return None


def _send_whatsapp_escalation(session: VoiceSession, gmeet_url: Optional[str]) -> None:
    """Send escalation options to customer via WhatsApp buttons."""
    try:
        from app.database.core import SessionLocal
        from app.services.whatsapp_service import send_button_message, send_text_message
        from app.models.whatsapp_account import WhatsAppAccount
        from app.models.leads import Lead

        with SessionLocal() as db:
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

            body = (
                "I wasn't able to fully answer all your questions. "
                "Here are your options to speak with a human expert:"
            )

            if gmeet_url:
                buttons = [
                    {"id": "join_gmeet",   "title": "Join GMeet Expert"},
                    {"id": "call_office",  "title": f"Call {OFFICE_PHONE}"},
                ]
                footer = f"GMeet: {gmeet_url} | Phone: {OFFICE_PHONE}"
                send_button_message(
                    account    = account,
                    to_number  = lead.phone,
                    body       = body,
                    buttons    = buttons,
                    footer     = footer,
                )
            else:
                send_text_message(
                    account   = account,
                    to_number = lead.phone,
                    body      = f"{body}\n\nPlease call us at: {OFFICE_PHONE}",
                )
    except Exception as exc:
        logger.warning(f"[ESCALATION] WhatsApp escalation send failed: {exc}")


def _send_gmail_escalation(session: VoiceSession, gmeet_url: Optional[str]) -> None:
    """Send escalation options email via Gmail."""
    try:
        from app.services.gmail_service import send_email, get_gmail_service
        from app.models.leads import Lead
        from app.database.core import SessionLocal

        with SessionLocal() as db:
            lead = db.query(Lead).filter(Lead.id == session.lead_id).first() if session.lead_id else None
            if not lead or not lead.email:
                return

        gmail_svc = get_gmail_service()
        name  = lead.name or "there"
        gmeet_section = (
            f"\n\n📅 Join a Google Meet with our expert:\n{gmeet_url}"
            if gmeet_url else ""
        )
        body = (
            f"Hi {name},\n\n"
            f"Our AI voice assistant wasn't able to fully address your questions. "
            f"We'd love to connect you with a human expert who can help right away.\n"
            f"{gmeet_section}\n\n"
            f"📞 Call us directly: {OFFICE_PHONE}\n\n"
            f"Best regards,\nRDL Technologies Sales Team"
        )
        send_email(
            service  = gmail_svc,
            to       = lead.email,
            subject  = "RDL Technologies – Let's Connect You With an Expert",
            body     = body,
        )
    except Exception as exc:
        logger.warning(f"[ESCALATION] Gmail escalation send failed: {exc}")


def offer_escalation_options(
    db: Session,
    session: VoiceSession,
    *,
    escalation_type: str = EscalationType.GMEET,
) -> str:
    """
    Escalate: create GMeet if requested, send both options (GMeet + phone)
    via the session's channel, update session status.
    Returns the primary escalation reference (GMeet URL or OFFICE_PHONE).
    """
    gmeet_url = None
    if escalation_type == EscalationType.GMEET:
        gmeet_url = _create_expert_gmeet(db, session)

    primary_ref = gmeet_url or OFFICE_PHONE

    origin = session.channel_origin
    if origin == ChannelOrigin.WHATSAPP:
        _send_whatsapp_escalation(session, gmeet_url)
    elif origin == ChannelOrigin.GMAIL:
        _send_gmail_escalation(session, gmeet_url)
    else:
        # Direct or unknown — try WhatsApp first, then Gmail
        _send_whatsapp_escalation(session, gmeet_url)
        _send_gmail_escalation(session, gmeet_url)

    session.status          = VoiceSessionStatus.ESCALATED
    session.escalation_type = escalation_type if gmeet_url else EscalationType.OFFICE_CALL
    session.escalation_ref  = primary_ref
    session.ended_at        = datetime.utcnow()
    db.commit()

    logger.info(
        f"[ESCALATION] Session {session.room_name} escalated via {session.escalation_type} "
        f"ref={primary_ref}"
    )
    return primary_ref


def check_and_auto_escalate(db: Session, session: VoiceSession) -> bool:
    """
    Auto-escalate if unanswered_count >= threshold.
    Returns True if escalation was triggered.
    Called from the Redis transcript update handler.
    """
    threshold = settings.VOICE_ESCALATION_THRESHOLD
    if session.unanswered_count >= threshold and session.status == VoiceSessionStatus.ACTIVE:
        logger.info(
            f"[ESCALATION] Auto-escalating {session.room_name} "
            f"(unanswered={session.unanswered_count} >= {threshold})"
        )
        offer_escalation_options(db, session, escalation_type=EscalationType.GMEET)
        return True
    return False
