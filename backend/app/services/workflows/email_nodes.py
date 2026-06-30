"""
Node functions for the LangGraph email workflow.

Each node takes (state, config) and returns a partial state dict.
The DB session is passed via config["configurable"]["db"] — never in state.
"""
import logging
import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Optional
from uuid import UUID

from langchain_core.runnables import RunnableConfig
from sqlalchemy.orm import Session

from app.models.communication import Email, EmailLabel, EmailStatus
from app.models.leads import Lead
from app.services import gmail_service
from app.services.email_classifier_service import classify_email
from app.services.sales_gap_service import (
    detect_product,
    extract_structured_gaps,
    fetch_rag_context,
    find_similar_products,
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

Use the RAG context below to answer. For anything not in the RAG context, promise a follow-up email — never expose internal wording like "not available in the provided context" to the customer.

Rules:
- Answer ONLY the questions explicitly asked — nothing more
- Use exact figures from the RAG context (price, order code, spec values) — never approximate
- FORBIDDEN: never write [LEAD TIME], [BULK PRICE], [WARRANTY DETAILS], or any word inside square brackets
- FORBIDDEN: never write "not available in the provided context" or any mention of "context" — customers must never see internal language

- AMBIGUOUS CATEGORY (multiple variants found): If the customer uses a generic term (e.g. "data loggers", "sensors")
  and the RAG context contains MULTIPLE matching variants, do NOT say "Our team will follow up."
  Instead, list all variants from the context as options so the customer can choose:
    "We have several [category] models — here are the options:
     1. [Product Name] (Order Code: [code]) — ₹[price] — [1-line spec summary]
     2. [Product Name] (Order Code: [code]) — ₹[price] — [1-line spec summary]
     ..."
  Then ask which specific model they need so you can confirm the quantity pricing.

- QUANTITY PRICING (specific product identified): If the customer specifies a quantity AND the product is
  unambiguously identified, calculate: total = unit price × quantity. Show the math clearly.
  Example: "10 × ₹4,681 = ₹46,810." Do this for each product separately.
  Use bulk_price per unit if present, otherwise use unit price.

- MULTIPLE DISTINCT PRODUCTS asked about: Answer each product (or product group) in its own section.

- MISSING INFORMATION — follow-up promise:
  When a specific detail (warranty, bulk discount tiers, lead time, feature comparison) is not in the RAG context:
  DO NOT scatter multiple "will follow up" sentences through the email.
  Instead, answer everything you CAN from the RAG context first, then add ONE consolidated sentence
  at the end (before the sign-off) listing all the items you will follow up on. Format:
    "We will send you a follow-up email shortly with details on: [item 1], [item 2]."
  Keep it to one sentence. Never say "not available", "not in our context", or "we don't have this information".

- FREQUENTLY BOUGHT TOGETHER: If the RAG context contains a "You may also be interested in:" section,
  include a brief upsell line BEFORE the sign-off — one sentence mentioning the related product(s) by name.
  Example: "Customers who purchase this often pair it with the [Product Name] — let us know if you'd like details."

- Sign off as: RDL Technologies Sales Team

RAG Context (product knowledge):
{rag_context}

---
Original email:
From: {sender}
Subject: {subject}

{body}"""

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

_MEETING_KEYWORDS = [
    "schedule a meeting", "schedule a call", "schedule a demo",
    "book a meeting", "book a call", "book a demo",
    "arrange a meeting", "arrange a call", "arrange a demo",
    "set up a meeting", "set up a call", "set up a demo",
    "make a meeting", "make an online meeting", "make online meeting",
    "online meeting", "online call", "online demo",
    "google meet", "gmeet", "video call",
    "can we meet", "let's meet", "meeting at", "call at", "demo at",
    "confirm the meeting", "confirm our call", "confirm the call",
    "i'd like a meeting", "i'd like a demo", "i want to schedule",
    "i need a product demo", "i need a demo", "product demo",
    "want to talk", "want a call", "discuss this", "have a discussion",
    "talk to someone", "speak to someone", "connect with someone",
]

_MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_received_at(date_str: str) -> datetime:
    try:
        return parsedate_to_datetime(date_str).astimezone(timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)


def _get_db(config: RunnableConfig) -> Session:
    return config["configurable"]["db"]


def _get_gmail_svc(config: RunnableConfig):
    return config["configurable"]["gmail_svc"]


def _get_fbt(product_id: Optional[str]) -> str:
    if not product_id:
        return ""
    try:
        from app.database.core import SessionLocal
        from sqlalchemy import text
        with SessionLocal() as db:
            row = db.execute(text("""
                SELECT document FROM langchain_pg_embedding
                WHERE cmetadata->>'product_id' = :pid
                  AND cmetadata->>'chunk_type' = 'frequently_bought_together'
                LIMIT 1
            """), {"pid": product_id}).fetchone()
        return f"\n\n---\nYou may also be interested in:\n{row[0]}" if row else ""
    except Exception:
        return ""


_WEEKDAY_MAP = {
    "monday": 0, "mon": 0, "tuesday": 1, "tue": 1, "tues": 1,
    "wednesday": 2, "wed": 2, "thursday": 3, "thu": 3, "thurs": 3,
    "friday": 4, "fri": 4, "saturday": 5, "sat": 5, "sunday": 6, "sun": 6,
}


def _parse_time_of_day(text: str) -> Optional[tuple[int, int]]:
    """Extract HH:MM from text like 'at 4 pm', '4:30 PM', '16:00'. Returns (hour, minute) in 24h."""
    m = re.search(r'(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)', text)
    if m:
        hour = int(m.group(1))
        minute = int(m.group(2) or 0)
        ampm = m.group(3)
        if ampm == "pm" and hour != 12:
            hour += 12
        elif ampm == "am" and hour == 12:
            hour = 0
        return (hour, minute)
    # 24-hour like "16:00" or "at 14:30"
    m = re.search(r'(?:at\s+)?(\d{1,2}):(\d{2})\b', text)
    if m:
        return (int(m.group(1)), int(m.group(2)))
    return None


def _parse_requested_time(body: str) -> Optional[datetime]:
    """Parse a meeting time from email body. Handles absolute dates, 'tomorrow', 'today', 'tonight', weekday names.
    Common typos like 'tommorow', 'tommorrow', 'tmrw' are also accepted."""
    from zoneinfo import ZoneInfo
    ist = ZoneInfo("Asia/Kolkata")
    b = body.lower()
    now_ist = datetime.now(ist)

    # 1) Absolute date: "at 4 pm on 26 May 2026"
    m = re.search(
        r'at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm).*?(\d{1,2})(?:st|nd|rd|th)?\s+'
        r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\s*(\d{4})?', b
    )
    if m:
        hour, minute = int(m.group(1)), int(m.group(2) or 0)
        ampm, day = m.group(3), int(m.group(4))
        month = _MONTH_MAP.get(m.group(5)[:3], 1)
        year = int(m.group(6)) if m.group(6) else now_ist.year
        if ampm == "pm" and hour != 12: hour += 12
        elif ampm == "am" and hour == 12: hour = 0
        try:
            return datetime(year, month, day, hour, minute, tzinfo=ist).astimezone(timezone.utc)
        except ValueError:
            pass

    # 2) Relative date keywords — "tomorrow", "today", "tonight", typos
    target_date = None
    if re.search(r'\b(tomorrow|tomorow|tommorow|tommorrow|tmrw|tmr)\b', b):
        target_date = (now_ist + timedelta(days=1)).date()
    elif re.search(r'\btoday\b', b):
        target_date = now_ist.date()
    elif re.search(r'\b(tonight|this evening)\b', b):
        target_date = now_ist.date()
    else:
        # 3) Weekday name — "monday", "next thursday", etc.
        wm = re.search(r'(?:next\s+)?(monday|tuesday|wednesday|thursday|friday|saturday|sunday|mon|tue|tues|wed|thu|thurs|fri|sat|sun)\b', b)
        if wm:
            target_weekday = _WEEKDAY_MAP[wm.group(1)]
            days_ahead = (target_weekday - now_ist.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7  # "monday" said on monday = next monday
            target_date = (now_ist + timedelta(days=days_ahead)).date()

    if target_date:
        tod = _parse_time_of_day(b)
        if not tod:
            # No time given — default to 10:00 AM IST
            tod = (10, 0)
        hour, minute = tod
        try:
            return datetime(target_date.year, target_date.month, target_date.day,
                            hour, minute, tzinfo=ist).astimezone(timezone.utc)
        except ValueError:
            pass
    return None


# ── Nodes ─────────────────────────────────────────────────────────────────────

def node_parse(state: dict, config: RunnableConfig) -> dict:
    """Parse raw Gmail message and check for duplicates."""
    db = _get_db(config)
    raw = state["raw_message"]
    parsed = gmail_service.parse_message(raw)
    gmail_message_id = parsed["gmail_message_id"]

    if db.query(Email).filter(Email.gmail_message_id == gmail_message_id).first():
        return {"duplicate": True, "gmail_message_id": gmail_message_id}

    sender_raw = parsed["sender"]
    sender_email = gmail_service.extract_email_address(sender_raw)
    subject = parsed["subject"] or ""
    body = parsed["body_text"] or ""
    effective_body = body if body.strip() else subject

    return {
        "duplicate": False,
        "gmail_message_id": gmail_message_id,
        "gmail_thread_id": parsed.get("gmail_thread_id"),
        "rfc_message_id": parsed.get("rfc_message_id", ""),
        "rfc_references": parsed.get("rfc_references", ""),
        "sender_raw": sender_raw,
        "sender_email": sender_email,
        "subject": subject,
        "body": body,
        "effective_body": effective_body,
        "received_at": _parse_received_at(parsed.get("date_str", "")),
        "recipients": parsed.get("recipients", []),
        "body_html": parsed.get("body_html"),
    }


def node_fetch_thread_context(state: dict, config: RunnableConfig) -> dict:
    """Fetch original message for Re: emails to give the classifier full context."""
    if not state["subject"].lower().startswith("re:") or not state.get("gmail_thread_id"):
        return {"thread_context": None}
    gmail_svc = _get_gmail_svc(config)
    try:
        ctx = gmail_service.fetch_thread_context(
            gmail_svc, state["gmail_thread_id"], state["gmail_message_id"]
        )
        return {"thread_context": ctx}
    except Exception as e:
        logger.warning(f"[EMAIL WORKFLOW] Thread context fetch failed: {e}")
        return {"thread_context": None}


def node_classify(state: dict, config: RunnableConfig) -> dict:
    """Classify email label via Gemini."""
    result = classify_email(
        subject=state["subject"],
        body=state["effective_body"],
        sender=state["sender_raw"],
        thread_context=state.get("thread_context"),
    )
    if result.get("llm_unavailable"):
        logger.warning(
            f"[EMAIL WORKFLOW] LLM unavailable (quota/cap) — deferring email "
            f"{state.get('gmail_message_id')!r} for retry next poll cycle"
        )
    return {
        "label": result["label"].value,
        "classifier_confidence": result["confidence"],
        "classifier_reasoning": result["reasoning"],
        "transactional_type": result.get("transactional_type"),
        "transactional_data": result.get("transactional_data"),
        "competitor_mention": result.get("competitor_mention"),
        "llm_unavailable": bool(result.get("llm_unavailable")),
    }


def node_persist(state: dict, config: RunnableConfig) -> dict:
    """Write email row to DB after classification."""
    db = _get_db(config)
    label = EmailLabel(state["label"])
    # account_id/account_email live in config["configurable"], not in state
    _account_id_str = config["configurable"].get("account_id")
    _account_email = config["configurable"].get("account_email")
    _account_id = UUID(_account_id_str) if _account_id_str else None

    email_row = Email(
        gmail_message_id=state["gmail_message_id"],
        gmail_thread_id=state.get("gmail_thread_id"),
        rfc_message_id=state.get("rfc_message_id"),
        rfc_references=state.get("rfc_references"),
        direction="inbound",
        sender=state["sender_raw"],
        recipients=state.get("recipients", []),
        subject=state["subject"],
        body_text=state["effective_body"],
        body_html=state.get("body_html"),
        received_at=state["received_at"],
        label=label,
        status=EmailStatus.CLASSIFIED,
        classifier_reasoning=state.get("classifier_reasoning"),
        classifier_confidence=state.get("classifier_confidence"),
        transactional_type=state.get("transactional_type"),
        transactional_data=state.get("transactional_data"),
        competitor_mention=state.get("competitor_mention"),
        account_id=_account_id,
        account_email=_account_email,
    )
    db.add(email_row)
    try:
        db.flush()
    except Exception as e:
        db.rollback()
        if "unique" in str(e).lower():
            logger.info(f"[EMAIL WORKFLOW] Duplicate {state['gmail_message_id']} — skipping")
            return {"duplicate": True}
        raise
    return {"email_id": str(email_row.id)}


def node_upsert_lead(state: dict, config: RunnableConfig) -> dict:
    """Find or create a lead for Sales emails."""
    db = _get_db(config)
    sender_email = state["sender_email"]
    existing = db.query(Lead).filter(Lead.email == sender_email).first()
    if existing:
        db.query(Email).filter(Email.id == UUID(state["email_id"])).update({"lead_id": existing.id})
        db.flush()
        return {"lead_id": str(existing.id), "is_new_lead": False}

    # owner_id comes from the EmailAccount that received this message
    from app.models.email_account import EmailAccount
    _acc_id = config["configurable"].get("account_id")
    _owner = None
    if _acc_id:
        _acc = db.query(EmailAccount).filter(EmailAccount.id == UUID(_acc_id)).first()
        _owner = _acc.owner_id if _acc else None

    display = state["sender_raw"].split("<")[0].strip().strip('"')
    name = display if display else sender_email.split("@")[0].replace(".", " ").title()
    lead = Lead(name=name, email=sender_email, status="Uncontacted", interest_level="Warm", engagement_score=20, owner_id=_owner)
    db.add(lead)
    db.flush()
    db.query(Email).filter(Email.id == UUID(state["email_id"])).update({"lead_id": lead.id})
    db.flush()
    logger.info(f"[EMAIL WORKFLOW] Auto-created lead: {name} <{sender_email}>")
    return {"lead_id": str(lead.id), "is_new_lead": True}


_THREAD_PRODUCT_TTL_DAYS = 5


def node_detect_product(state: dict, config: RunnableConfig) -> dict:
    """3-phase product detection from email subject + body.

    Only persists detected_product_* to the DB when confidence is HIGH.
    Low/none-confidence matches trigger a clarification email instead — the
    product is not yet confirmed by the customer, so it must not show up in
    Product Intelligence analytics as a confirmed inquiry.

    Thread-product inheritance: if a prior email in the same Gmail thread
    already confirmed a product within the last 5 days, inherit it as
    high-confidence and skip detection + clarification entirely.
    """
    db = _get_db(config)

    thread_id = state.get("gmail_thread_id")
    if thread_id:
        cutoff = datetime.now(timezone.utc) - timedelta(days=_THREAD_PRODUCT_TTL_DAYS)
        prior = (
            db.query(Email)
            .filter(
                Email.gmail_thread_id == thread_id,
                Email.detected_product_id.isnot(None),
                Email.received_at >= cutoff,
            )
            .order_by(Email.received_at.desc())
            .first()
        )
        if prior:
            logger.info(
                f"[EMAIL WORKFLOW] Thread product inherited: {prior.detected_product_name} "
                f"(thread={thread_id}, last_seen={prior.received_at.date()})"
            )
            return {
                "product_id": prior.detected_product_id,
                "product_name": prior.detected_product_name,
                "product_confidence": "high",
            }

    text = f"{state['subject']} {state['effective_body']}"
    product_id, product_name, confidence = detect_product(db, text)
    if state.get("email_id") and product_name and confidence == "high":
        db.query(Email).filter(Email.id == UUID(state["email_id"])).update(
            {"detected_product_id": product_id, "detected_product_name": product_name},
            synchronize_session=False,
        )
        db.flush()
    return {
        "product_id": product_id,
        "product_name": product_name,
        "product_confidence": confidence or "none",
    }


def node_fetch_rag(state: dict, config: RunnableConfig) -> dict:
    """Fetch RAG context for the email body."""
    try:
        rag = fetch_rag_context(state["effective_body"])
        return {"rag_context": rag or ""}
    except Exception as e:
        logger.warning(f"[EMAIL WORKFLOW] RAG fetch failed: {e}")
        return {"rag_context": ""}


def generate_sales_draft(sender: str, subject: str, body: str, rag_context: Optional[str] = None) -> str:
    """Standalone draft generator — called by the /generate-draft endpoint and node_generate_draft."""
    if rag_context is None:
        rag_context = fetch_rag_context(body) or "No specific product context retrieved."
    prompt = _SALES_DRAFT_PROMPT.format(
        rag_context=rag_context,
        sender=sender,
        subject=subject,
        body=body[:2000],
    )
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain_core.messages import HumanMessage
        from google.api_core.exceptions import PermissionDenied, ResourceExhausted
        from app.core.config import settings
        base_kwargs = dict(temperature=0.3, max_output_tokens=4096, max_retries=0)
        primary_kwargs = {**base_kwargs, **({"google_api_key": settings.GOOGLE_API_KEY} if settings.GOOGLE_API_KEY else {})}
        primary = ChatGoogleGenerativeAI(model="models/gemini-2.5-flash", **primary_kwargs)
        fallback = ChatGoogleGenerativeAI(model="models/gemini-2.0-flash", **base_kwargs)
        llm = primary.with_fallbacks([fallback], exceptions_to_handle=(ResourceExhausted, PermissionDenied))
        response = llm.invoke([HumanMessage(content=prompt)])
        return sanitize_ai_response(response.content.strip())
    except Exception as e:
        logger.error(f"[EMAIL WORKFLOW] Draft generation failed: {e}", exc_info=True)
        return ""


def node_generate_draft(state: dict, config: RunnableConfig) -> dict:
    """Generate a sales reply draft — delegates to generate_sales_draft for testability."""
    rag_context = state.get("rag_context") or ""
    if state.get("product_id"):
        fbt = _get_fbt(state["product_id"])
        if fbt:
            rag_context = rag_context + fbt
    draft = generate_sales_draft(
        sender=state["sender_raw"],
        subject=state["subject"],
        body=state["effective_body"],
        # Always pass a non-None value — RAG already ran in node_fetch_rag.
        # Passing None would trigger a redundant second RAG call inside generate_sales_draft.
        rag_context=rag_context or "No specific product context retrieved.",
    )
    return {"draft": draft}


def node_extract_gaps(state: dict, config: RunnableConfig) -> dict:
    """Extract unanswered questions from the draft and persist to DB."""
    db = _get_db(config)
    gaps = extract_structured_gaps(
        state["effective_body"],
        state.get("draft", ""),
        state.get("product_name"),
        state.get("product_id"),
        db=db,
    )
    if gaps:
        db.query(Email).filter(Email.id == UUID(state["email_id"])).update(
            {"followup_gaps": gaps},
            synchronize_session=False,
        )
        db.flush()
    return {"gaps": gaps or []}


def _build_voice_cta(db, lead_id, account_id, sender_email: str) -> str:
    """
    Create a LiveKit voice room for this email lead and return a CTA footer block.
    Non-fatal — if room creation fails, returns an office-phone-only block.
    """
    from app.core.config import settings as _cfg

    join_url   = None
    owner_id   = None

    try:
        from app.models.email_account import EmailAccount
        from uuid import UUID
        acct = db.query(EmailAccount).filter(EmailAccount.id == UUID(str(account_id))).first() if account_id else None
        owner_id = acct.owner_id if acct else None
    except Exception:
        pass

    try:
        if owner_id:
            from app.services.voice_room_service import create_room
            _lead_id = UUID(str(lead_id)) if lead_id else None
            session, join_url = create_room(
                db,
                channel_origin="gmail",
                owner_id=owner_id,
                lead_id=_lead_id,
            )
    except Exception as exc:
        logger.warning(f"[EMAIL VOICE CTA] Room creation failed: {exc}")

    voice_line = (
        f"🎙️ Talk to our AI right now (no app needed):\n{join_url}\n\n"
        if join_url else ""
    )
    return (
        "\n\n---\n"
        f"{voice_line}"
        f"📅 Schedule a Google Meet with an expert: Reply 'MEET' or visit rdltech.in/schedule\n"
        f"📞 Call us directly: {_cfg.COMPANY_PHONE}"
    )


def node_auto_send(state: dict, config: RunnableConfig) -> dict:
    """Create Gmail draft and send immediately — no gaps, full confidence."""
    db = _get_db(config)
    gmail_svc = _get_gmail_svc(config)
    sender_email = state["sender_email"]
    subject = state["subject"]
    draft_text = state.get("draft", "")

    if not draft_text:
        # Draft generation failed — fall back to human review
        db.query(Email).filter(Email.id == UUID(state["email_id"])).update(
            {"needs_human": True, "status": EmailStatus.PENDING_HUMAN},
            synchronize_session=False,
        )
        db.flush()
        return {"action": "pending_human_draft_failed"}

    # Append voice CTA to every auto-sent Sales reply
    voice_cta = _build_voice_cta(db, state.get("lead_id"), state.get("account_id"), sender_email)
    full_body  = draft_text + voice_cta

    try:
        reply_subject = subject if subject.startswith("Re:") else f"Re: {subject}"
        draft = gmail_service.create_draft(
            gmail_svc, to=sender_email, subject=reply_subject,
            body=full_body, thread_id=state.get("gmail_thread_id"),
            reply_to_message_id=state.get("rfc_message_id") or None,
            references=state.get("rfc_references") or None,
        )
        gmail_service.send_draft(gmail_svc, draft["id"])
        db.query(Email).filter(Email.id == UUID(state["email_id"])).update(
            {"ai_draft": full_body, "gmail_draft_id": None, "status": EmailStatus.REPLIED,
             "tracking_token": draft.get("tracking_token")},
            synchronize_session=False,
        )
        db.flush()
        logger.info(f"[EMAIL WORKFLOW] Auto-sent (no gaps): {subject}")
        return {"action": "auto_sent"}
    except Exception as e:
        logger.error(f"[EMAIL WORKFLOW] Auto-send failed: {e}")
        db.query(Email).filter(Email.id == UUID(state["email_id"])).update(
            {"needs_human": True, "status": EmailStatus.PENDING_HUMAN},
            synchronize_session=False,
        )
        db.flush()
        return {"action": "pending_human_send_failed"}


def node_hold_draft(state: dict, config: RunnableConfig) -> dict:
    """Save draft to Gmail Drafts and hold for human review — gaps exist."""
    db = _get_db(config)
    gmail_svc = _get_gmail_svc(config)
    sender_email = state["sender_email"]
    subject = state["subject"]
    draft_text = state.get("draft", "")

    if not draft_text:
        db.query(Email).filter(Email.id == UUID(state["email_id"])).update(
            {"needs_human": True, "status": EmailStatus.PENDING_HUMAN},
            synchronize_session=False,
        )
        db.flush()
        return {"action": "pending_human_draft_failed"}

    try:
        reply_subject = subject if subject.startswith("Re:") else f"Re: {subject}"
        draft = gmail_service.create_draft(
            gmail_svc, to=sender_email, subject=reply_subject,
            body=draft_text, thread_id=state.get("gmail_thread_id"),
            reply_to_message_id=state.get("rfc_message_id") or None,
            references=state.get("rfc_references") or None,
        )
        db.query(Email).filter(Email.id == UUID(state["email_id"])).update(
            {
                "ai_draft": draft_text,
                "gmail_draft_id": draft["id"],
                "needs_human": True,
                "status": EmailStatus.DRAFT_READY,
                "tracking_token": draft.get("tracking_token"),
            },
            synchronize_session=False,
        )
        db.flush()
        logger.info(f"[EMAIL WORKFLOW] {len(state.get('gaps', []))} gap(s) — draft held for review: {subject}")
        return {"action": "draft_held"}
    except Exception as e:
        logger.error(f"[EMAIL WORKFLOW] Hold-draft failed: {e}")
        db.query(Email).filter(Email.id == UUID(state["email_id"])).update(
            {"needs_human": True, "status": EmailStatus.PENDING_HUMAN},
            synchronize_session=False,
        )
        db.flush()
        return {"action": "pending_human_hold_failed"}


def node_send_clarification(state: dict, config: RunnableConfig) -> dict:
    """Send a clarification email when product confidence is low/none."""
    db = _get_db(config)
    gmail_svc = _get_gmail_svc(config)
    similar = find_similar_products(db, f"{state['subject']} {state['effective_body']}", limit=4)

    if state.get("product_name") and similar:
        intro = (
            f"Thank you for your inquiry. We noticed you might be asking about "
            f"**{state['product_name']}**, but we want to make sure we give you the right information.\n\n"
            "Could you confirm which of the following products you're referring to?"
        )
    elif similar:
        intro = (
            "Thank you for reaching out! To point you to the right product and provide accurate details, "
            "could you confirm which product you're asking about? Here are some that may match:"
        )
    else:
        intro = (
            "Thank you for your inquiry. To provide accurate information, could you please let us know "
            "the exact product name or order code? You can browse our full catalog at https://rdltech.in/products"
        )

    lines = [intro, ""]
    for i, p in enumerate(similar, 1):
        link = p.get("product_link") or "https://rdltech.in/products"
        code = f" (Order Code: {p['order_code']})" if p.get("order_code") else ""
        lines.append(f"{i}. **{p['name']}**{code} — {link}")
    lines += ["", "Once you confirm, we'll reply with complete details, pricing, and specifications.",
              "", "Best regards,", "RDL Technologies Sales Team"]
    clarification = "\n".join(lines)

    try:
        reply_subject = state["subject"] if state["subject"].startswith("Re:") else f"Re: {state['subject']}"
        draft = gmail_service.create_draft(
            gmail_svc, to=state["sender_email"], subject=reply_subject,
            body=clarification, thread_id=state.get("gmail_thread_id"),
            reply_to_message_id=state.get("rfc_message_id") or None,
            references=state.get("rfc_references") or None,
        )
        gmail_service.send_draft(gmail_svc, draft["id"])
        db.query(Email).filter(Email.id == UUID(state["email_id"])).update(
            {"ai_draft": clarification, "gmail_draft_id": None, "status": EmailStatus.REPLIED,
             "tracking_token": draft.get("tracking_token")},
            synchronize_session=False,
        )
        db.flush()
        logger.info(f"[EMAIL WORKFLOW] Clarification sent (confidence={state['product_confidence']}): {state['subject']}")
        return {"action": "clarification_sent"}
    except Exception as e:
        logger.error(f"[EMAIL WORKFLOW] Clarification send failed: {e}")
        db.query(Email).filter(Email.id == UUID(state["email_id"])).update(
            {"needs_human": True, "status": EmailStatus.PENDING_HUMAN},
            synchronize_session=False,
        )
        db.flush()
        return {"action": "pending_human_clarification_failed"}


def node_flag_human(state: dict, config: RunnableConfig) -> dict:
    """Save draft for human review — Support/Grievance replies must NOT be auto-sent."""
    db = _get_db(config)
    gmail_svc = _get_gmail_svc(config)
    label_str = state["label"]
    label = EmailLabel(label_str)

    display_name = state["sender_raw"].split("<")[0].strip() or state["sender_email"].split("@")[0]
    first_name = display_name.split()[0].title() if display_name else "Customer"
    template = _GRIEVANCE_ACK if label == EmailLabel.GRIEVANCE else _SUPPORT_ACK
    ack_body = template.format(name=first_name)

    try:
        reply_subject = state["subject"] if state["subject"].startswith("Re:") else f"Re: {state['subject']}"
        # Save to Gmail Drafts — human reviews, edits, and sends manually
        draft = gmail_service.create_draft(
            gmail_svc, to=state["sender_email"],
            subject=reply_subject, body=ack_body,
            thread_id=state.get("gmail_thread_id"),
            reply_to_message_id=state.get("rfc_message_id") or None,
            references=state.get("rfc_references") or None,
        )
        db.query(Email).filter(Email.id == UUID(state["email_id"])).update(
            {
                "needs_human": True,
                "status": EmailStatus.DRAFT_READY,
                "ai_draft": ack_body,
                "gmail_draft_id": draft["id"],
            },
            synchronize_session=False,
        )
        db.flush()
        logger.info(f"[EMAIL WORKFLOW] {label_str} draft saved for human review: {state['subject']}")
    except Exception as e:
        logger.error(f"[EMAIL WORKFLOW] Draft save failed for {label_str}: {e}")
        db.query(Email).filter(Email.id == UUID(state["email_id"])).update(
            {"needs_human": True, "status": EmailStatus.PENDING_HUMAN},
            synchronize_session=False,
        )
        db.flush()
    return {"action": "flagged_human"}


def node_defer_human(state: dict, config: RunnableConfig) -> dict:
    """Product detection LLM was unavailable (quota/cap). Flag for human review
    without sending a clarification — the customer may have already named the
    product, we just couldn't confirm it. No auto-draft is created."""
    db = _get_db(config)
    db.query(Email).filter(Email.id == UUID(state["email_id"])).update(
        {"needs_human": True, "status": EmailStatus.PENDING_HUMAN},
        synchronize_session=False,
    )
    db.flush()
    logger.warning(
        f"[EMAIL WORKFLOW] Product detect LLM unavailable — flagged for human: {state['subject']}"
    )
    return {"action": "deferred_human_llm_cap"}


def node_archive(state: dict, config: RunnableConfig) -> dict:
    """Archive Transactional/Promotional/Personal emails.
    For Transactional messages with sales-relevant types (invoice, order, receipt)
    we also auto-create or update a Deal in the CRM pipeline.
    """
    db = _get_db(config)
    gmail_svc = _get_gmail_svc(config)
    label = EmailLabel(state["label"])
    status = EmailStatus.ARCHIVED if label == EmailLabel.TRANSACTIONAL else EmailStatus.IGNORED
    try:
        gmail_service.archive_message(gmail_svc, state["gmail_message_id"])
    except Exception as e:
        logger.warning(f"[EMAIL WORKFLOW] Archive failed: {e}")
    db.query(Email).filter(Email.id == UUID(state["email_id"])).update(
        {"status": status}, synchronize_session=False,
    )
    db.flush()
    logger.info(f"[EMAIL WORKFLOW] {state['label']} email archived: {state['subject']}")

    # Auto-create/update Deal from invoice or purchase document
    if label == EmailLabel.TRANSACTIONAL:
        ttype = state.get("transactional_type")
        tdata = state.get("transactional_data") or {}
        lead_id = state.get("lead_id")
        if ttype and lead_id:
            try:
                from app.services.transaction_deal_service import process_transaction_for_deal
                process_transaction_for_deal(
                    db            = db,
                    lead_id       = lead_id,
                    transactional_type = ttype,
                    transactional_data = tdata,
                    owner_id      = None,   # owner_id filled from lead's owner in service
                    source_channel = "email",
                )
            except Exception as exc:
                logger.warning(f"[EMAIL WORKFLOW] transaction→deal failed: {exc}")

    return {"action": "archived"}


def node_apply_gmail_label(state: dict, config: RunnableConfig) -> dict:
    """Apply RDL/* label and mark as read in Gmail."""
    gmail_svc = _get_gmail_svc(config)
    label = EmailLabel(state["label"])
    gmail_label = _GMAIL_LABEL_MAP.get(label)
    if gmail_label:
        try:
            gmail_service.apply_label_to_message(gmail_svc, state["gmail_message_id"], gmail_label)
        except Exception as e:
            logger.warning(f"[EMAIL WORKFLOW] Label apply failed: {e}")
    try:
        gmail_service.mark_as_read(gmail_svc, state["gmail_message_id"])
    except Exception as e:
        logger.warning(f"[EMAIL WORKFLOW] Mark-read failed: {e}")
    return {}


def node_update_lead_score(state: dict, config: RunnableConfig) -> dict:
    """Recompute lead engagement score."""
    if not state.get("lead_id"):
        return {}
    db = _get_db(config)
    try:
        from app.services.lead_scoring_service import update_lead_score
        update_lead_score(db, UUID(state["lead_id"]))
    except Exception as e:
        logger.warning(f"[EMAIL WORKFLOW] Lead score update failed: {e}")
    return {}


def node_start_drip(state: dict, config: RunnableConfig) -> dict:
    """Auto-start drip sequence for brand-new leads only."""
    if not state.get("is_new_lead") or not state.get("lead_id"):
        return {}
    db = _get_db(config)
    try:
        from app.services.email_sequence_service import create_sequence
        lead_id = UUID(state["lead_id"])
        lead = db.query(Lead).filter(Lead.id == lead_id).first()
        if not lead:
            return {}
        create_sequence(
            db=db, lead_id=lead_id, name="New lead follow-up",
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
                        "If you have any remaining questions or would like a product demo, we'd be happy to help.\n\n"
                        "Best regards,\nRDL Technologies Sales Team"
                    ),
                },
            ],
            created_by="system",
        )
        logger.info(f"[EMAIL WORKFLOW] Drip sequence started for new lead: {lead.name}")
    except Exception as e:
        logger.warning(f"[EMAIL WORKFLOW] Drip sequence failed: {e}")
    return {}


def _format_slot(dt: datetime) -> str:
    """Render a UTC datetime as a friendly IST string for emails."""
    from zoneinfo import ZoneInfo
    ist = dt.astimezone(ZoneInfo("Asia/Kolkata"))
    return ist.strftime("%A, %d %b %Y at %I:%M %p IST")


def _build_slot_proposal_email(name: str, product: Optional[str], slots: list[datetime]) -> str:
    """Follow-up email offering the customer a choice of free meeting slots."""
    first = name.split()[0].title() if name else "there"
    subject_line = f" about the {product}" if product else ""
    options = "\n".join(f"  {i+1}. {_format_slot(s)}" for i, s in enumerate(slots))
    return (
        f"Hi {first},\n\n"
        f"Thanks for your interest in scheduling a meeting{subject_line}. "
        f"Here are a few available times:\n\n"
        f"{options}\n\n"
        f"Just reply with the option that works best for you (or suggest another time), "
        f"and we'll send a Google Meet calendar invite to confirm.\n\n"
        f"Best regards,\nRDL Technologies Sales Team"
    )


def node_try_schedule_meeting(state: dict, config: RunnableConfig) -> dict:
    """
    Handle meeting/demo intent on a Sales email:

    - Specific time given (parsed from body) → book it on Google Calendar with a
      GMeet link + invite email. If the slot is taken, use the next free slot after it.
    - Meeting intent but NO specific time → send a threaded follow-up email proposing
      the next few free slots so the customer can pick one. (Previously this case did
      nothing, leaving the "we'll follow up" promise unfulfilled.)
    """
    body_lower = state["effective_body"].lower()
    if not any(kw in body_lower for kw in _MEETING_KEYWORDS):
        return {}

    db = _get_db(config)
    lead_id = UUID(state["lead_id"]) if state.get("lead_id") else None
    requested_time = _parse_requested_time(state["effective_body"])

    # ── Case A: explicit time → book it ────────────────────────────────────────
    if requested_time:
        try:
            from app.services.calendar_service import create_meeting, get_calendar_service, find_next_free_slot, _is_slot_free
            from app.models.calendar_event import EventTrigger
            cal_svc = get_calendar_service()
            slot_end = requested_time + timedelta(minutes=30)
            if not _is_slot_free(cal_svc, requested_time, slot_end):
                hours_offset = max(1, int((requested_time - datetime.now(timezone.utc)).total_seconds() / 3600))
                new_time = find_next_free_slot(hours_from_now=hours_offset)
                logger.info(f"[EMAIL WORKFLOW] Requested slot {requested_time} taken — using {new_time}")
                requested_time = new_time
            # owner_id comes from the EmailAccount that received this message
            from app.models.email_account import EmailAccount
            _acc_id = config["configurable"].get("account_id")
            _owner = None
            if _acc_id:
                _acc = db.query(EmailAccount).filter(EmailAccount.id == UUID(_acc_id)).first()
                _owner = _acc.owner_id if _acc else None
            if _owner is None:
                logger.warning("[EMAIL WORKFLOW] No owner_id for meeting — skipping schedule")
                return {}
            event = create_meeting(
                db=db,
                attendee_email=state["sender_email"],
                title=f"Sales Discussion — {state.get('product_name') or state['subject'] or 'Product Inquiry'}",
                description=f"Meeting requested via email.\nSubject: {state['subject']}",
                start_time=requested_time,
                owner_id=_owner,
                duration_minutes=30,
                trigger=EventTrigger.MANUAL,
                lead_id=lead_id,
                gmail_svc=_get_gmail_svc(config),
            )
            logger.info(f"[EMAIL WORKFLOW] Meeting scheduled: {event.meet_link} @ {requested_time}")
            return {"action": "meeting_scheduled"}
        except Exception as e:
            logger.warning(f"[EMAIL WORKFLOW] Meeting scheduling failed: {e}", exc_info=True)
            return {}

    # ── Case B: meeting intent, no time → propose free slots via follow-up ──────
    try:
        from app.services.calendar_service import find_free_slots
        slots = find_free_slots(count=3)
        if not slots:
            logger.info(f"[EMAIL WORKFLOW] Meeting intent but no free slots found: {state['subject']!r}")
            return {}
        body = _build_slot_proposal_email(
            state.get("sender_raw", ""), state.get("product_name"), slots
        )
        subject = state["subject"] if state["subject"].startswith("Re:") else f"Re: {state['subject']}"
        gmail_svc = _get_gmail_svc(config)
        sent = gmail_service.send_email(
            gmail_svc,
            to=state["sender_email"],
            subject=subject,
            body=body,
            thread_id=state.get("gmail_thread_id"),
            reply_to_message_id=state.get("rfc_message_id") or None,
            references=state.get("rfc_references") or None,
        )
        db.query(Email).filter(Email.id == UUID(state["email_id"])).update(
            {"tracking_token": sent.get("tracking_token")},
            synchronize_session=False,
        )
        db.flush()
        logger.info(f"[EMAIL WORKFLOW] Proposed {len(slots)} meeting slots to {state['sender_email']}")
        return {"action": "meeting_slots_proposed"}
    except Exception as e:
        logger.warning(f"[EMAIL WORKFLOW] Slot proposal failed: {e}", exc_info=True)
    return {}


def node_commit(state: dict, config: RunnableConfig) -> dict:
    """Commit the DB session — called once at the end of each branch."""
    db = _get_db(config)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"[EMAIL WORKFLOW] Final commit failed: {e}")
    return {}


# ── Routing functions ─────────────────────────────────────────────────────────

def route_after_parse(state: dict) -> str:
    if state.get("duplicate"):
        return "end_duplicate"
    return "fetch_thread_context"


def route_after_classify(state: dict) -> str:
    label = state.get("label", "")
    if label == EmailLabel.SALES.value:
        return "sales_branch"
    if label in (EmailLabel.SUPPORT.value, EmailLabel.GRIEVANCE.value):
        return "support_branch"
    return "archive_branch"


def route_after_confidence(state: dict) -> str:
    confidence = state.get("product_confidence", "none")
    if confidence == "high":
        return "rag_branch"
    if confidence == "unavailable":
        # LLM quota/cap hit during product detection — hold for human review
        # instead of sending a clarification the customer already answered.
        return "defer_human"
    return "clarification_branch"


def route_after_gaps(state: dict) -> str:
    # Hold if gaps exist OR if the receiving account has auto_send disabled
    if state.get("gaps"):
        return "hold_draft"
    if not state.get("auto_send_enabled", True):
        return "hold_draft"
    return "auto_send"
