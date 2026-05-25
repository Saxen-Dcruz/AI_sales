"""
Send outreach emails via Gmail and record them in OutreachThread/OutreachMessage.
"""
import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.lead_gen import CampaignContact, OutreachCampaign, OutreachMessage, OutreachThread
from app.services import gmail_service

logger = logging.getLogger("rdl_app_logger")


def _get_gmail_svc(db: Session, account_id: UUID | None):
    if account_id:
        try:
            from app.services.email_account_service import get_account
            account = get_account(db, account_id)
            if account:
                return gmail_service.get_gmail_service(account=account)
        except Exception:
            pass
    return gmail_service.get_gmail_service()


def _get_or_create_thread(db: Session, cc: CampaignContact) -> OutreachThread:
    thread = db.query(OutreachThread).filter(
        OutreachThread.campaign_contact_id == cc.id
    ).first()
    if not thread:
        thread = OutreachThread(campaign_contact_id=cc.id)
        db.add(thread)
        db.flush()
    return thread


def send_outreach_message(
    db: Session,
    campaign_contact_id: UUID,
    body: str,
) -> OutreachMessage:
    """Send an outreach email and record it. Returns the OutreachMessage."""
    cc = db.query(CampaignContact).filter(CampaignContact.id == campaign_contact_id).first()
    if not cc:
        raise ValueError(f"CampaignContact {campaign_contact_id} not found")

    contact = cc.contact
    company = contact.company
    campaign: OutreachCampaign = cc.campaign

    if not contact.email:
        raise ValueError(f"Contact {contact.name} has no email address")

    subject = campaign.email_subject or f"Partnership opportunity for {company.name}"
    account_id = campaign.assigned_account_id

    thread = _get_or_create_thread(db, cc)

    # Build email subject with Re: if replying in thread
    is_reply = thread.gmail_thread_id is not None
    if is_reply and not subject.startswith("Re:"):
        subject = f"Re: {subject}"

    # Send via Gmail
    gmail_svc = _get_gmail_svc(db, account_id)
    sent = gmail_service.send_email(
        gmail_svc,
        to=contact.email,
        subject=subject,
        body=body,
        thread_id=thread.gmail_thread_id,
        reply_to_message_id=thread.rfc_message_id,
    )

    # Update thread with Gmail thread ID
    if not thread.gmail_thread_id:
        thread.gmail_thread_id = sent.get("threadId")
    thread.last_message_at = datetime.now(timezone.utc)

    # Record the outbound message
    msg = OutreachMessage(
        thread_id=thread.id,
        direction="outbound",
        content=body,
        ai_generated=True,
        gmail_message_id=sent.get("id"),
        sent_at=datetime.now(timezone.utc),
    )
    db.add(msg)

    # Update campaign contact status
    cc.status = "sent"
    db.commit()

    logger.info(f"[OUTREACH] Sent to {contact.email} | campaign_contact={cc.id}")
    return msg


def process_inbound_reply(
    db: Session,
    gmail_thread_id: str,
    from_email: str,
    body: str,
    gmail_message_id: str,
    auto_reply: bool = False,
) -> bool:
    """
    Hook called from Gmail poller when an email arrives.
    Returns True if this message belongs to an outreach thread (and should skip standard classification).
    """
    thread = db.query(OutreachThread).filter(
        OutreachThread.gmail_thread_id == gmail_thread_id
    ).first()
    if not thread:
        return False

    cc = thread.campaign_contact
    contact = cc.contact

    # Record inbound message
    msg = OutreachMessage(
        thread_id=thread.id,
        direction="inbound",
        content=body,
        ai_generated=False,
        gmail_message_id=gmail_message_id,
        sent_at=datetime.now(timezone.utc),
    )
    db.add(msg)

    # Update thread + contact status
    thread.last_message_at = datetime.now(timezone.utc)
    if cc.status == "sent":
        cc.status = "replied"

    # Regenerate AI summary
    from app.services.outreach_ai_service import summarize_thread, generate_reply
    thread.ai_summary = summarize_thread(db, thread)

    db.commit()

    # Auto-reply if campaign has auto_send enabled
    campaign = cc.campaign
    if auto_reply and campaign.auto_send and contact.email:
        try:
            reply_body = generate_reply(db, thread, body, campaign)
            send_outreach_message(db, cc.id, reply_body)
        except Exception as e:
            logger.error(f"[OUTREACH] Auto-reply failed: {e}")

    logger.info(f"[OUTREACH] Inbound reply recorded for thread {thread.id}")
    return True
