"""
Email-specific routing pipeline.

Shared intelligence (gap detection, topic inference, product detection, RAG fetch)
lives in sales_gap_service.py so it can be reused by the call pipeline without
duplication.
"""
import logging
import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Optional

from langsmith import traceable
from sqlalchemy.orm import Session

from app.models.communication import Email, EmailLabel, EmailStatus
from app.models.leads import Lead
from app.services import gmail_service
from app.services.email_classifier_service import classify_email
from app.services.sales_gap_service import (
    detect_product,
    extract_structured_gaps,
    fetch_rag_context,
    sanitize_ai_response,
)

logger = logging.getLogger("rdl_app_logger")

_GMAIL_LABEL_MAP = {
    EmailLabel.SALES: "RDL/Sales",
    EmailLabel.SUPPORT: "RDL/Support",
    EmailLabel.GRIEVANCE: "RDL/Grievance",
    EmailLabel.TRANSACTIONAL: "RDL/Transactional",
    EmailLabel.PROMOTIONAL: "RDL/Promotional",
    EmailLabel.PERSONAL: "RDL/Personal",
}

_SALES_DRAFT_PROMPT = """You are the RDL Technologies sales assistant. Write a concise, professional reply that answers only what the customer asked.

Use the RAG context below to answer the specific questions. Do not volunteer information that was not asked for.
If something is not in the RAG context, write one sentence: "Our team will follow up with you on this shortly." — do not guess.

Rules:
- Answer ONLY the questions explicitly asked — nothing more
- Keep each answer to 1-3 sentences — be direct and specific
- Use exact figures from the RAG context (price, order code, spec values) — never approximate
- If information is not in the RAG context, say you will follow up — do not speculate
- FORBIDDEN: never write [LEAD TIME], [BULK PRICE], [WARRANTY DETAILS], [EVALUATION TERMS], or any word inside square brackets
- Sign off as: RDL Technologies Sales Team

RAG Context (product knowledge):
{rag_context}

---
Original email:
From: {sender}
Subject: {subject}

{body}"""


def _get_fbt_recommendation(db: Session, product_id: Optional[str]) -> str:
    """Fetch frequently_bought_together text for a product to append as a recommendation."""
    if not product_id:
        return ""
    try:
        from app.database.core import SessionLocal
        from sqlalchemy import text
        with SessionLocal() as _db:
            row = _db.execute(text("""
                SELECT document FROM langchain_pg_embedding
                WHERE cmetadata->>'product_id' = :pid
                  AND cmetadata->>'chunk_type' = 'frequently_bought_together'
                LIMIT 1
            """), {"pid": product_id}).fetchone()
        if row:
            return f"\n\n---\nYou may also be interested in:\n{row[0]}"
    except Exception:
        pass
    return ""


def _generate_sales_draft(sender: str, subject: str, body: str) -> str:
    """
    Fetch RAG context (via sales_gap_service) then call the draft LLM via
    google.genai REST transport (avoids gRPC channel corruption from the classifier).
    """
    rag_context = fetch_rag_context(body)

    prompt = _SALES_DRAFT_PROMPT.format(
        rag_context=rag_context or "No specific product context retrieved.",
        sender=sender,
        subject=subject,
        body=body[:2000],
    )

    try:
        from google import genai
        from google.genai import types
        import google.auth

        _, project_id = google.auth.default()
        client = genai.Client(vertexai=True, project=project_id, location="us-central1")
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.3),
        )
        return sanitize_ai_response(response.text.strip())
    except Exception as e:
        logger.error(f"Failed to generate sales draft: {e}", exc_info=True)
        return ""


_MEETING_KEYWORDS = [
    "schedule a meeting", "schedule a call", "book a meeting", "book a call",
    "arrange a meeting", "arrange a call", "set up a meeting", "set up a call",
    "google meet", "gmeet", "video call",
    "can we meet", "let's meet", "meeting at", "call at",
    "confirm the meeting", "confirm our call", "confirm the call",
    "i'd like a meeting", "i want to schedule",
]

_MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _is_meeting_request(body: str) -> bool:
    """Return True if the email explicitly requests or confirms a meeting."""
    b = body.lower()
    return any(kw in b for kw in _MEETING_KEYWORDS)


def _parse_requested_time(body: str) -> Optional[datetime]:
    """
    Try to extract a datetime from natural language in the email body.
    Handles patterns like:
      '6pm on 12th may 2026', 'May 12 at 6pm', '12/05/2026 at 18:00'
    Returns a timezone-aware datetime in UTC, or None if not parseable.
    """
    from zoneinfo import ZoneInfo
    ist = ZoneInfo("Asia/Kolkata")
    b = body.lower()

    # Pattern: "at Xpm on Dth Month Year" or "at X:00pm on ..."
    m = re.search(
        r'at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm).*?(\d{1,2})(?:st|nd|rd|th)?\s+'
        r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\s*(\d{4})?',
        b
    )
    if m:
        hour = int(m.group(1))
        minute = int(m.group(2) or 0)
        ampm = m.group(3)
        day = int(m.group(4))
        month = _MONTH_MAP.get(m.group(5)[:3], 1)
        year = int(m.group(6)) if m.group(6) else datetime.now().year
        if ampm == "pm" and hour != 12:
            hour += 12
        elif ampm == "am" and hour == 12:
            hour = 0
        try:
            dt_ist = datetime(year, month, day, hour, minute, tzinfo=ist)
            return dt_ist.astimezone(timezone.utc)
        except ValueError:
            pass

    # Pattern: "Month Dth at Xpm" e.g. "May 12th at 6pm"
    m = re.search(
        r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\s+(\d{1,2})(?:st|nd|rd|th)?'
        r'(?:\s+\d{4})?\s+at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)',
        b
    )
    if m:
        month = _MONTH_MAP.get(m.group(1)[:3], 1)
        day = int(m.group(2))
        hour = int(m.group(3))
        minute = int(m.group(4) or 0)
        ampm = m.group(5)
        year = datetime.now().year
        if ampm == "pm" and hour != 12:
            hour += 12
        try:
            dt_ist = datetime(year, month, day, hour, minute, tzinfo=ist)
            return dt_ist.astimezone(timezone.utc)
        except ValueError:
            pass

    return None


def _try_schedule_from_email_body(
    db: Session,
    body: str,
    lead: Optional[Lead],
    subject: str,
    sender_email: str,
) -> None:
    """
    Schedule a Google Meet ONLY when the customer explicitly requests a meeting
    AND provides a specific date/time. If no parseable time is found, skip —
    the customer has not confirmed a time yet.
    """
    if not _is_meeting_request(body):
        return

    requested_time = _parse_requested_time(body)
    if not requested_time:
        # Customer mentioned a meeting but didn't give a specific time.
        # Don't auto-schedule — wait for them to confirm a time.
        logger.info(f"[EMAIL ROUTER] Meeting intent detected but no specific time given — skipping auto-schedule for: {subject}")
        return

    attendee = lead.email if lead else sender_email

    try:
        from app.services.calendar_service import create_meeting, _is_slot_free, get_calendar_service, find_next_free_slot
        from app.models.calendar_event import EventTrigger

        # Check if the requested slot is free; if not, find next free slot
        try:
            cal_svc = get_calendar_service()
            slot_end = requested_time + timedelta(minutes=30)
            if not _is_slot_free(cal_svc, requested_time, slot_end):
                logger.info(f"[EMAIL ROUTER] Requested slot busy — finding next free slot")
                requested_time = find_next_free_slot(hours_from_now=2)
        except Exception:
            pass

        event = create_meeting(
            db=db,
            attendee_email=attendee,
            title=f"Sales Discussion — {subject or 'Product Inquiry'}",
            description=f"Meeting requested via email.\nSubject: {subject}",
            start_time=requested_time,
            duration_minutes=30,
            trigger=EventTrigger.MANUAL,
            lead_id=lead.id if lead else None,
        )
        logger.info(f"[EMAIL ROUTER] Meeting scheduled from email request: {event.meet_link} @ {requested_time}")
    except Exception as e:
        logger.warning(f"[EMAIL ROUTER] Could not schedule meeting from email: {e}")


def _match_lead(db: Session, sender_email: str) -> Optional[Lead]:
    return db.query(Lead).filter(Lead.email == sender_email).first()


def _upsert_lead_from_email(db: Session, sender_raw: str, sender_email: str) -> tuple[Lead, bool]:
    """Return (lead, is_new) — finds existing lead by email or creates one from sender display name."""
    existing = db.query(Lead).filter(Lead.email == sender_email).first()
    if existing:
        return existing, False
    display = sender_raw.split("<")[0].strip().strip('"')
    name = display if display else sender_email.split("@")[0].replace(".", " ").title()
    lead = Lead(
        name=name,
        email=sender_email,
        status="Uncontacted",
        interest_level="Warm",
        engagement_score=20,
    )
    db.add(lead)
    db.flush()
    logger.info(f"[EMAIL ROUTER] Auto-created lead: {name} <{sender_email}>")
    return lead, True


def _parse_received_at(date_str: str) -> datetime:
    try:
        return parsedate_to_datetime(date_str).astimezone(timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)


@traceable(run_type="chain", name="process_inbound_email")
def process_inbound_email(db: Session, raw_message: dict) -> Optional[Email]:
    """
    Full pipeline for a single inbound Gmail message:
    1. Skip if already processed
    2. Parse → classify → route → persist → apply Gmail label
    Returns the persisted Email row, or None if skipped.
    """
    gmail_svc = gmail_service.get_gmail_service()
    parsed = gmail_service.parse_message(raw_message)
    gmail_message_id = parsed["gmail_message_id"]

    if db.query(Email).filter(Email.gmail_message_id == gmail_message_id).first():
        return None

    sender_raw = parsed["sender"]
    sender_email = gmail_service.extract_email_address(sender_raw)
    subject = parsed["subject"] or ""
    body = parsed["body_text"] or ""
    received_at = _parse_received_at(parsed["date_str"])

    classification = classify_email(subject=subject, body=body, sender=sender_raw)
    label: EmailLabel = classification["label"]

    # Sales emails always get a lead — create one if this is a new sender
    is_new_lead = False
    if label == EmailLabel.SALES:
        lead, is_new_lead = _upsert_lead_from_email(db, sender_raw, sender_email)
    else:
        lead = _match_lead(db, sender_email)

    email_row = Email(
        gmail_message_id=gmail_message_id,
        gmail_thread_id=parsed["gmail_thread_id"],
        lead_id=lead.id if lead else None,
        direction="inbound",
        sender=sender_raw,
        recipients=parsed["recipients"],
        subject=subject,
        body_text=body,
        body_html=parsed["body_html"],
        received_at=received_at,
        label=label,
        status=EmailStatus.CLASSIFIED,
        classifier_reasoning=classification["reasoning"],
        classifier_confidence=classification["confidence"],
        transactional_type=classification.get("transactional_type"),
        transactional_data=classification.get("transactional_data"),
        competitor_mention=classification.get("competitor_mention"),
    )

    if label == EmailLabel.SALES:
        product_id, product_name = detect_product(db, f"{subject} {body}")
        _route_sales(gmail_svc, db, email_row, sender_raw, subject, body, parsed["gmail_thread_id"], product_id, product_name)
        # Only schedule if customer explicitly requested a meeting AND gave a specific time
        _try_schedule_from_email_body(db, body, lead, subject, sender_email)

    elif label in (EmailLabel.SUPPORT, EmailLabel.GRIEVANCE):
        _route_support_grievance(gmail_svc, email_row, sender_raw, subject, body, parsed["gmail_thread_id"], label)
        logger.info(f"[EMAIL ROUTER] {label.value} acknowledged + flagged for human: {subject}")

    elif label in (EmailLabel.PROMOTIONAL, EmailLabel.PERSONAL):
        email_row.status = EmailStatus.IGNORED
        gmail_service.archive_message(gmail_svc, gmail_message_id)
        logger.info(f"[EMAIL ROUTER] {label.value} email archived: {subject}")

    elif label == EmailLabel.TRANSACTIONAL:
        email_row.status = EmailStatus.ARCHIVED
        gmail_service.archive_message(gmail_svc, gmail_message_id)
        logger.info(f"[EMAIL ROUTER] Transactional email stored: {subject}")

    gmail_label = _GMAIL_LABEL_MAP.get(label)
    if gmail_label:
        try:
            gmail_service.apply_label_to_message(gmail_svc, gmail_message_id, gmail_label)
        except Exception as e:
            logger.warning(f"Failed to apply Gmail label '{gmail_label}': {e}")

    gmail_service.mark_as_read(gmail_svc, gmail_message_id)

    db.add(email_row)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        if "UniqueViolation" in type(e).__name__ or "unique constraint" in str(e).lower():
            logger.info(f"[EMAIL ROUTER] Skipping duplicate {gmail_message_id} — concurrent cycle already committed")
            return None
        raise
    db.refresh(email_row)

    # Update lead score after every inbound Sales email
    if lead and label == EmailLabel.SALES:
        try:
            from app.services.lead_scoring_service import update_lead_score
            update_lead_score(db, lead.id)
        except Exception as e:
            logger.warning(f"[EMAIL ROUTER] Lead score update failed: {e}")

    # Auto-start a drip sequence for brand new leads from Sales emails
    if is_new_lead and label == EmailLabel.SALES:
        try:
            product_label = email_row.body_text[:60].strip() if email_row.body_text else "our products"
            from app.services.email_sequence_service import create_sequence
            create_sequence(
                db=db,
                lead_id=lead.id,
                name="New lead follow-up",
                steps=[
                    {
                        "day_offset": 2,
                        "subject": "Following up on your inquiry — RDL Technologies",
                        "body": (
                            f"Dear {lead.name},\n\n"
                            "We wanted to follow up on your recent inquiry. "
                            "Our team is ready to answer any further questions you may have.\n\n"
                            "Please reply to this email or let us know a convenient time for a quick call.\n\n"
                            "Best regards,\nRDL Technologies Sales Team"
                        ),
                    },
                    {
                        "day_offset": 5,
                        "subject": "Can we help with anything else? — RDL Technologies",
                        "body": (
                            f"Dear {lead.name},\n\n"
                            "We noticed you reached out a few days ago. "
                            "If you have any remaining questions or would like a product demo, "
                            "we'd be happy to help.\n\n"
                            "Best regards,\nRDL Technologies Sales Team"
                        ),
                    },
                ],
                created_by="system",
            )
            logger.info(f"[EMAIL ROUTER] Drip sequence started for new lead: {lead.name}")
        except Exception as e:
            logger.warning(f"[EMAIL ROUTER] Drip sequence creation failed: {e}")

    logger.info(f"[EMAIL ROUTER] Processed {gmail_message_id} → {label.value} | lead_matched={lead is not None}")
    db.refresh(email_row)
    return email_row


_GRIEVANCE_ACK = """Dear {name},

Thank you for reaching out to RDL Technologies.

We sincerely apologise for the inconvenience you have experienced. We take all complaints very seriously and want to assure you that this is being escalated to our support team immediately.

Our team will review your case and get back to you within **4 business hours** with a resolution or update.

For reference, your complaint has been logged and will be addressed as a priority.

We appreciate your patience and apologise again for the trouble caused.

Best regards,
RDL Technologies Support Team"""

_SUPPORT_ACK = """Dear {name},

Thank you for contacting RDL Technologies.

We have received your support request and it has been assigned to our technical team. We will respond with a resolution within **4 business hours**.

If you have any additional details to share, please reply to this email and we will incorporate them into your case.

Best regards,
RDL Technologies Support Team"""


def _route_support_grievance(
    gmail_svc,
    email_row: Email,
    sender: str,
    subject: str,
    body: str,
    thread_id: Optional[str],
    label: EmailLabel,
) -> None:
    """Send an immediate acknowledgment reply for Support/Grievance emails,
    then flag for human follow-up. Customer gets a response within seconds
    instead of waiting in silence."""
    email_row.needs_human = True
    email_row.status = EmailStatus.PENDING_HUMAN

    try:
        sender_email = gmail_service.extract_email_address(sender)
        # Extract first name from sender string e.g. "saxen dcruz <saxen@gmail.com>"
        display_name = sender.split("<")[0].strip() or sender_email.split("@")[0]
        first_name = display_name.split()[0].title() if display_name else "Customer"

        template = _GRIEVANCE_ACK if label == EmailLabel.GRIEVANCE else _SUPPORT_ACK
        ack_body = template.format(name=first_name)

        reply_subject = subject if subject.startswith("Re:") else f"Re: {subject}"
        gmail_service.send_email(
            gmail_svc,
            to=sender_email,
            subject=reply_subject,
            body=ack_body,
            thread_id=thread_id,
        )
        email_row.ai_draft = ack_body
        logger.info(f"[EMAIL ROUTER] {label.value} acknowledgment sent to {sender_email}")
    except Exception as e:
        logger.error(f"[EMAIL ROUTER] Failed to send {label.value} acknowledgment: {e}")


def _route_sales(
    gmail_svc,
    db: Session,
    email_row: Email,
    sender: str,
    subject: str,
    body: str,
    thread_id: Optional[str],
    product_id: Optional[str] = None,
    product_name: Optional[str] = None,
) -> None:
    draft_text = _generate_sales_draft(sender=sender, subject=subject, body=body)
    if draft_text and product_id:
        fbt = _get_fbt_recommendation(db, product_id)
        if fbt:
            draft_text = draft_text.rstrip() + fbt
    if draft_text:
        try:
            sender_email = gmail_service.extract_email_address(sender)
            reply_subject = subject if subject.startswith("Re:") else f"Re: {subject}"
            draft = gmail_service.create_draft(
                gmail_svc,
                to=sender_email,
                subject=reply_subject,
                body=draft_text,
                thread_id=thread_id,
            )
            email_row.ai_draft = draft_text
            email_row.gmail_draft_id = draft["id"]
            gaps = extract_structured_gaps(body, draft_text, product_name, product_id)
            if gaps:
                email_row.followup_gaps = gaps
                logger.info(f"[EMAIL ROUTER] {len(gaps)} RAG gap(s) logged for dashboard: {subject}")
            # Always send — gaps are logged on the dashboard for follow-up,
            # but the customer gets a reply immediately.
            gmail_service.send_draft(gmail_svc, draft["id"])
            email_row.gmail_draft_id = None
            email_row.status = EmailStatus.REPLIED
            logger.info(f"[EMAIL ROUTER] Reply sent for: {subject}")
        except Exception as e:
            logger.error(f"Failed to create Gmail draft for sales email: {e}")
            email_row.needs_human = True
            email_row.status = EmailStatus.PENDING_HUMAN
    else:
        email_row.needs_human = True
        email_row.status = EmailStatus.PENDING_HUMAN
