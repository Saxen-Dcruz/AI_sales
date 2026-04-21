import logging
from uuid import UUID
from typing import Optional

from sqlalchemy.orm import Session

from app.models.deal import Deal
from app.models.leads import Lead
from app.models.calendar_event import CalendarEvent, EventTrigger

logger = logging.getLogger("rdl_app_logger")

# Thresholds for a "positive deal signal"
_POSITIVE_STAGES = {"Proposal", "Negotiation", "Closed Won"}
_WIN_PROBABILITY_THRESHOLD = 50   # %
_ENGAGEMENT_SCORE_THRESHOLD = 60
_POSITIVE_SENTIMENTS = {"Positive", "positive", "POSITIVE"}


def _already_scheduled(db: Session, deal_id: UUID) -> bool:
    """Returns True if there's an active scheduled meeting for this deal already."""
    from app.models.calendar_event import EventStatus
    return db.query(CalendarEvent).filter(
        CalendarEvent.deal_id == deal_id,
        CalendarEvent.status == EventStatus.SCHEDULED,
    ).first() is not None


def evaluate_deal_signal(db: Session, deal: Deal) -> bool:
    """
    Returns True if the deal has positive signals that warrant scheduling a call.
    Signals: stage in positive set OR win_probability >= threshold.
    Skips if a meeting is already scheduled for this deal.
    """
    if _already_scheduled(db, deal.id):
        return False

    stage_positive = deal.stage in _POSITIVE_STAGES
    prob_positive = float(deal.win_probability or 0) >= _WIN_PROBABILITY_THRESHOLD

    return stage_positive or prob_positive


def evaluate_lead_signal(db: Session, lead: Lead) -> bool:
    """
    Returns True if the lead's engagement + sentiment warrant scheduling a call.
    Used when email arrives from a lead with no active deal.
    """
    engagement_ok = (lead.engagement_score or 0) >= _ENGAGEMENT_SCORE_THRESHOLD
    sentiment_ok = lead.overall_sentiment in _POSITIVE_SENTIMENTS
    return engagement_ok or sentiment_ok


def maybe_schedule_from_email(
    db: Session,
    lead: Optional[Lead],
    email_subject: str,
) -> Optional[CalendarEvent]:
    """
    Called by email_router_service after a Sales email is processed.
    Checks if the associated lead/deal has positive signals → schedules GMeet.
    Returns the CalendarEvent if scheduled, None otherwise.
    """
    if not lead or not lead.email:
        return None

    from app.services.calendar_service import create_meeting, next_available_slot

    # Check deal signal
    deal = _get_active_deal_for_lead(db, lead.id)
    if deal and evaluate_deal_signal(db, deal):
        slot = next_available_slot(hours_from_now=24)
        title = f"Sales Discussion — {lead.name} ({deal.deal_name})"
        description = (
            f"Follow-up call triggered by incoming Sales email.\n"
            f"Subject: {email_subject}\n"
            f"Deal: {deal.deal_name} | Stage: {deal.stage} | Value: ₹{deal.deal_value}"
        )
        logger.info(f"[DEAL SIGNAL] Scheduling call for deal '{deal.deal_name}' — stage={deal.stage}, prob={deal.win_probability}%")
        return create_meeting(
            db=db,
            attendee_email=lead.email,
            title=title,
            description=description,
            start_time=slot,
            duration_minutes=30,
            trigger=EventTrigger.DEAL_SIGNAL,
            lead_id=lead.id,
            deal_id=deal.id,
        )

    # Check lead signal (no deal yet)
    if evaluate_lead_signal(db, lead):
        slot = next_available_slot(hours_from_now=24)
        title = f"Introductory Call — {lead.name}"
        description = (
            f"Call triggered by high engagement from incoming Sales email.\n"
            f"Subject: {email_subject}\n"
            f"Engagement score: {lead.engagement_score} | Sentiment: {lead.overall_sentiment}"
        )
        logger.info(f"[LEAD SIGNAL] Scheduling intro call for lead '{lead.name}'")
        return create_meeting(
            db=db,
            attendee_email=lead.email,
            title=title,
            description=description,
            start_time=slot,
            duration_minutes=30,
            trigger=EventTrigger.DEAL_SIGNAL,
            lead_id=lead.id,
            deal_id=None,
        )

    return None


def schedule_from_rag_gap(
    db: Session,
    lead: Optional[Lead],
    question: str,
    deal: Optional[Deal] = None,
) -> Optional[CalendarEvent]:
    """
    Called when RAG pipeline cannot confidently answer a question.
    Schedules a call so a human expert can address it.
    """
    if not lead or not lead.email:
        logger.info("[RAG GAP] No lead email — skipping calendar schedule")
        return None

    from app.services.calendar_service import create_meeting, next_available_slot

    slot = next_available_slot(hours_from_now=48)
    title = f"Product Expert Call — {lead.name}"
    description = (
        f"Scheduled because our knowledge base could not fully answer a customer query.\n\n"
        f"Question asked: {question}\n\n"
        f"A product expert will address this on the call."
    )
    logger.info(f"[RAG GAP] Scheduling expert call for lead '{lead.name}' — question: {question[:80]}")
    return create_meeting(
        db=db,
        attendee_email=lead.email,
        title=title,
        description=description,
        start_time=slot,
        duration_minutes=45,
        trigger=EventTrigger.RAG_INSUFFICIENT,
        lead_id=lead.id,
        deal_id=deal.id if deal else None,
    )


def _get_active_deal_for_lead(db: Session, lead_id: UUID) -> Optional[Deal]:
    """Returns the most recent non-closed deal for a lead."""
    return (
        db.query(Deal)
        .filter(Deal.lead_id == lead_id, Deal.stage != "Closed Lost")
        .order_by(Deal.created_at.desc())
        .first()
    )
