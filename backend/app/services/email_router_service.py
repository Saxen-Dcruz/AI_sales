import logging
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models.communication import Email, EmailLabel, EmailStatus
from app.models.leads import Lead
from app.services import gmail_service
from app.services.email_classifier_service import classify_email
from app.services.deal_signal_service import maybe_schedule_from_email

logger = logging.getLogger("rdl_app_logger")

_GMAIL_LABEL_MAP = {
    EmailLabel.SALES: "RDL/Sales",
    EmailLabel.SUPPORT: "RDL/Support",
    EmailLabel.GRIEVANCE: "RDL/Grievance",
    EmailLabel.TRANSACTIONAL: "RDL/Transactional",
    EmailLabel.PROMOTIONAL: "RDL/Promotional",
    EmailLabel.PERSONAL: "RDL/Personal",
}

_SALES_DRAFT_PROMPT = """You are the RDL Technologies sales assistant. Write a professional and helpful reply to the following sales inquiry.

Use the RAG context below to answer the customer's specific questions as accurately as possible.
For anything not covered in the RAG context, acknowledge it and say you will follow up.
At the end, invite them to schedule a call or Google Meet to discuss further.

Rules:
- Address each question the customer asked
- Use actual product details from the RAG context where available
- Do NOT make up specs, prices, or availability — if unsure, say you'll confirm
- End with: "Would you like to schedule a quick call to discuss your requirements in detail? We'd be happy to arrange a Google Meet at your convenience."
- Sign off as: RDL Technologies Sales Team

RAG Context (product knowledge):
{rag_context}

---
Original email:
From: {sender}
Subject: {subject}

{body}"""


def _build_draft_llm():
    from langchain_google_genai import ChatGoogleGenerativeAI
    from app.core.config import settings
    return ChatGoogleGenerativeAI(
        model="models/gemini-2.5-flash",
        google_api_key=settings.GOOGLE_API_KEY,
        temperature=0.3,
        max_output_tokens=800,
    )


def _fetch_rag_context(body: str) -> str:
    """Query the RAG pipeline with the email body to get relevant product context."""
    try:
        import asyncio
        import uuid
        from app.agents.tools.rag_chain import RAGManager
        # Append spec signal so budget hits standard tier (not factual 256-token tier)
        # which would truncate mid-sentence when body contains price-related words
        question = body[:1500] + "\n\nPlease include complete specifications and product details."
        result = asyncio.run(RAGManager().query_rag_database(
            question=question,
            session_id=str(uuid.uuid4()),
        ))
        return result.get("answer", "")
    except Exception as e:
        logger.warning(f"RAG context fetch failed for email draft: {e}")
        return ""


def _generate_sales_draft(sender: str, subject: str, body: str) -> str:
    try:
        rag_context = _fetch_rag_context(body)
        llm = _build_draft_llm()
        from langchain_core.messages import HumanMessage
        prompt = _SALES_DRAFT_PROMPT.format(
            rag_context=rag_context or "No specific product context retrieved.",
            sender=sender,
            subject=subject,
            body=body[:2000],
        )
        response = llm.invoke([HumanMessage(content=prompt)])
        return response.content.strip()
    except Exception as e:
        logger.error(f"Failed to generate sales draft: {e}")
        return ""


def _match_lead(db: Session, sender_email: str) -> Optional[Lead]:
    return db.query(Lead).filter(Lead.email == sender_email).first()


def _parse_received_at(date_str: str) -> datetime:
    try:
        return parsedate_to_datetime(date_str).astimezone(timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)


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

    # Idempotency — skip if already in DB
    if db.query(Email).filter(Email.gmail_message_id == gmail_message_id).first():
        return None

    sender_raw = parsed["sender"]
    sender_email = gmail_service.extract_email_address(sender_raw)
    subject = parsed["subject"] or ""
    body = parsed["body_text"] or ""
    received_at = _parse_received_at(parsed["date_str"])

    # Classify
    classification = classify_email(subject=subject, body=body, sender=sender_raw)
    label: EmailLabel = classification["label"]

    # Match to lead
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
    )

    # Route by label
    if label == EmailLabel.SALES:
        _route_sales(gmail_svc, email_row, sender_raw, subject, body, parsed["gmail_thread_id"])
        # Auto-schedule a call if deal/lead signals are positive
        try:
            maybe_schedule_from_email(db, lead, subject)
        except Exception as e:
            logger.warning(f"[EMAIL ROUTER] Auto-schedule check failed: {e}")

    elif label in (EmailLabel.SUPPORT, EmailLabel.GRIEVANCE):
        email_row.needs_human = True
        email_row.status = EmailStatus.PENDING_HUMAN
        logger.info(f"[EMAIL ROUTER] {label.value} email flagged for human: {subject}")

    elif label in (EmailLabel.PROMOTIONAL, EmailLabel.PERSONAL):
        email_row.status = EmailStatus.IGNORED
        gmail_service.archive_message(gmail_svc, gmail_message_id)
        logger.info(f"[EMAIL ROUTER] {label.value} email archived: {subject}")

    elif label == EmailLabel.TRANSACTIONAL:
        email_row.status = EmailStatus.ARCHIVED
        gmail_service.archive_message(gmail_svc, gmail_message_id)
        logger.info(f"[EMAIL ROUTER] Transactional email stored: {subject}")

    # Apply Gmail label
    gmail_label = _GMAIL_LABEL_MAP.get(label)
    if gmail_label:
        try:
            gmail_service.apply_label_to_message(gmail_svc, gmail_message_id, gmail_label)
        except Exception as e:
            logger.warning(f"Failed to apply Gmail label '{gmail_label}': {e}")

    gmail_service.mark_as_read(gmail_svc, gmail_message_id)

    db.add(email_row)
    db.commit()
    db.refresh(email_row)

    logger.info(f"[EMAIL ROUTER] Processed {gmail_message_id} → {label.value} | lead_matched={lead is not None}")
    return email_row


def _route_sales(gmail_svc, email_row: Email, sender: str, subject: str, body: str, thread_id: Optional[str]) -> None:
    draft_text = _generate_sales_draft(sender=sender, subject=subject, body=body)
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
            email_row.status = EmailStatus.DRAFT_READY
            logger.info(f"[EMAIL ROUTER] Sales draft created for: {subject}")
        except Exception as e:
            logger.error(f"Failed to create Gmail draft for sales email: {e}")
            email_row.needs_human = True
            email_row.status = EmailStatus.PENDING_HUMAN
    else:
        email_row.needs_human = True
        email_row.status = EmailStatus.PENDING_HUMAN
