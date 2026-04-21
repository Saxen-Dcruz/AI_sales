from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.models.communication import Email, EmailLabel, EmailStatus
from app.models.user import User
from app.schema.gmail import (
    ApproveDraftRequest,
    EmailListResponse,
    EmailOut,
    ResolveEmailRequest,
    SendEmailRequest,
)
from app.services import gmail_service
from app.services.email_router_service import process_inbound_email

router = APIRouter(prefix="/gmail", tags=["Gmail"])


# ── Inbox sync ────────────────────────────────────────────────────────────────

@router.post("/sync", status_code=status.HTTP_200_OK)
def sync_inbox(
    max_results: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Manually trigger inbox fetch and classification. Returns count processed."""
    svc = gmail_service.get_gmail_service()
    gmail_service.ensure_labels_exist(svc)
    messages = gmail_service.fetch_unread_messages(svc, max_results=max_results)
    processed = 0
    for raw_msg in messages:
        result = process_inbound_email(db, raw_msg)
        if result:
            processed += 1
    return {"processed": processed, "fetched": len(messages)}


# ── Email list ────────────────────────────────────────────────────────────────

@router.get("/", response_model=EmailListResponse)
def list_emails(
    label: Optional[EmailLabel] = Query(default=None),
    status: Optional[EmailStatus] = Query(default=None),
    needs_human: Optional[bool] = Query(default=None),
    lead_id: Optional[UUID] = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = db.query(Email)
    if label:
        q = q.filter(Email.label == label)
    if status:
        q = q.filter(Email.status == status)
    if needs_human is not None:
        q = q.filter(Email.needs_human == needs_human)
    if lead_id:
        q = q.filter(Email.lead_id == lead_id)
    total = q.count()
    items = q.order_by(Email.received_at.desc()).offset((page - 1) * limit).limit(limit).all()
    return EmailListResponse(items=items, total=total, page=page, limit=limit)


@router.get("/{email_id}", response_model=EmailOut)
def get_email(
    email_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    email = db.query(Email).filter(Email.id == email_id).first()
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")
    return email


# ── Human-in-the-loop ─────────────────────────────────────────────────────────

@router.post("/{email_id}/resolve", response_model=EmailOut)
def resolve_email(
    email_id: UUID,
    payload: ResolveEmailRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark a Support/Grievance email as handled by a human."""
    email = db.query(Email).filter(Email.id == email_id).first()
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")
    email.needs_human = False
    email.resolved_by = payload.resolved_by or current_user.email
    email.resolved_at = datetime.now(timezone.utc)
    email.status = EmailStatus.REPLIED
    db.commit()
    db.refresh(email)
    return email


# ── Sales draft approval ──────────────────────────────────────────────────────

@router.post("/{email_id}/approve-draft", response_model=EmailOut)
def approve_draft(
    email_id: UUID,
    payload: ApproveDraftRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Approve the AI draft for a Sales email.
    - If edit_body is provided, replaces the draft content before sending.
    - Sends the Gmail draft and marks email as replied.
    """
    email = db.query(Email).filter(Email.id == email_id).first()
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")
    if email.status != EmailStatus.DRAFT_READY:
        raise HTTPException(status_code=400, detail="Email has no pending draft to approve")
    if not email.gmail_draft_id:
        raise HTTPException(status_code=400, detail="No Gmail draft ID on record")

    svc = gmail_service.get_gmail_service()

    if payload.edit_body:
        # Delete old draft, create new one with edited body, then send
        try:
            svc.users().drafts().delete(userId="me", id=email.gmail_draft_id).execute()
        except Exception:
            pass
        sender_email = gmail_service.extract_email_address(email.sender)
        reply_subject = email.subject if (email.subject or "").startswith("Re:") else f"Re: {email.subject}"
        new_draft = gmail_service.create_draft(
            svc,
            to=sender_email,
            subject=reply_subject,
            body=payload.edit_body,
            thread_id=email.gmail_thread_id,
        )
        email.ai_draft = payload.edit_body
        email.gmail_draft_id = new_draft["id"]
        db.flush()

    try:
        gmail_service.send_draft(svc, email.gmail_draft_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send draft: {e}")

    email.status = EmailStatus.REPLIED
    email.resolved_by = current_user.email
    email.resolved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(email)
    return email


@router.post("/{email_id}/discard-draft", response_model=EmailOut)
def discard_draft(
    email_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Discard the AI draft — human will reply manually. Flags for human handling."""
    email = db.query(Email).filter(Email.id == email_id).first()
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")

    if email.gmail_draft_id:
        try:
            svc = gmail_service.get_gmail_service()
            svc.users().drafts().delete(userId="me", id=email.gmail_draft_id).execute()
        except Exception:
            pass

    email.gmail_draft_id = None
    email.ai_draft = None
    email.needs_human = True
    email.status = EmailStatus.PENDING_HUMAN
    db.commit()
    db.refresh(email)
    return email


# ── Outbound send ─────────────────────────────────────────────────────────────

@router.post("/send", status_code=status.HTTP_201_CREATED, response_model=EmailOut)
def send_email(
    payload: SendEmailRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Send a new outbound email and record it."""
    svc = gmail_service.get_gmail_service()
    try:
        sent = gmail_service.send_email(
            svc,
            to=payload.to,
            subject=payload.subject,
            body=payload.body,
            thread_id=payload.thread_id,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send email: {e}")

    email_row = Email(
        gmail_message_id=sent["id"],
        gmail_thread_id=sent.get("threadId"),
        direction="outbound",
        sender=current_user.email,
        recipients=[payload.to],
        subject=payload.subject,
        body_text=payload.body,
        received_at=datetime.now(timezone.utc),
        label=EmailLabel.SALES,
        status=EmailStatus.REPLIED,
    )
    db.add(email_row)
    db.commit()
    db.refresh(email_row)
    return email_row
