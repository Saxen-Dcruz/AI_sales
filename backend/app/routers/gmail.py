import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

logger = logging.getLogger("rdl_app_logger")

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.models.communication import Email, EmailLabel, EmailStatus
from app.models.user import User
from app.schema.gmail import (
    ApproveDraftRequest,
    EmailListResponse,
    EmailOut,
    EmailSLAAnalytics,
    GapNotificationListResponse,
    GapNotificationOut,
    GapResolveRequest,
    GenerateDraftRequest,
    GenerateDraftResponse,
    ResolveEmailRequest,
    SendEmailRequest,
    SequenceCreate,
    SequenceOut,
)
from app.services import gmail_service, product_knowledge_service
from app.services import email_sequence_service
from app.services.email_router_service import process_inbound_email, _generate_sales_draft

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


@router.get("/gaps", response_model=GapNotificationListResponse)
def list_rag_gaps(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """
    Returns all draft-ready Sales emails where the RAG pipeline could not answer
    at least one customer question. Used by the dashboard to show the sales team
    what information needs to be manually filled in before sending.
    """
    rows = (
        db.query(Email)
        .filter(
            Email.label == EmailLabel.SALES,
            Email.followup_gaps.isnot(None),
            Email.status == EmailStatus.DRAFT_READY,
        )
        .order_by(Email.received_at.desc())
        .all()
    )
    items = [
        GapNotificationOut(
            email_id=r.id,
            gmail_draft_id=r.gmail_draft_id,
            customer_email=r.sender,
            subject=r.subject,
            received_at=r.received_at,
            gaps=r.followup_gaps or [],
        )
        for r in rows
    ]
    return GapNotificationListResponse(items=items, total=len(items))


@router.get("/analytics", response_model=EmailSLAAnalytics)
def get_email_analytics(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Email pipeline analytics: SLA compliance, auto-send rate, competitor mentions."""
    from sqlalchemy import case, extract

    all_emails = db.query(Email).all()
    sales = [e for e in all_emails if e.label == EmailLabel.SALES]

    auto_sent = sum(1 for e in sales if e.status == EmailStatus.REPLIED and not e.needs_human)
    drafted = sum(1 for e in sales if e.followup_gaps and e.status == EmailStatus.REPLIED)
    pending = sum(1 for e in all_emails if e.needs_human and e.status == EmailStatus.PENDING_HUMAN)
    auto_sent_rate = round(auto_sent / len(sales) * 100, 1) if sales else 0.0

    # Avg reply time for replied Sales emails
    replied = [
        e for e in sales
        if e.status == EmailStatus.REPLIED and e.received_at
    ]
    # Use updated_at as proxy for reply time (when status changed to replied)
    reply_minutes = []
    for e in replied:
        if hasattr(e, 'updated_at') and e.updated_at and e.received_at:
            diff = (e.updated_at - e.received_at).total_seconds() / 60
            if 0 < diff < 1440:  # ignore if >24h (likely manual)
                reply_minutes.append(diff)
    avg_reply = round(sum(reply_minutes) / len(reply_minutes), 1) if reply_minutes else 0.0

    # SLA breach: Sales emails not replied within 2 hours
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    sla_breached = sum(
        1 for e in sales
        if e.status in (EmailStatus.DRAFT_READY, EmailStatus.PENDING_HUMAN, EmailStatus.CLASSIFIED)
        and e.received_at
        and (now - e.received_at).total_seconds() > 7200
    )

    competitor_mentions = sum(1 for e in all_emails if e.competitor_mention)

    by_label = {}
    by_status = {}
    by_direction = {}
    for e in all_emails:
        lbl = e.label.value if e.label else "Unclassified"
        by_label[lbl] = by_label.get(lbl, 0) + 1

        st = e.status.value if e.status else "unknown"
        by_status[st] = by_status.get(st, 0) + 1

        d = e.direction or "unknown"
        by_direction[d] = by_direction.get(d, 0) + 1

    return EmailSLAAnalytics(
        total_emails=len(all_emails),
        total_inbound=by_direction.get("inbound", 0),
        total_outbound=by_direction.get("outbound", 0),
        total_sales_emails=len(sales),
        auto_sent=auto_sent,
        drafted_for_review=drafted,
        pending_human=pending,
        auto_sent_rate_pct=auto_sent_rate,
        avg_reply_minutes=avg_reply,
        sla_breached=sla_breached,
        competitor_mentions=competitor_mentions,
        by_label=by_label,
        by_status=by_status,
        by_direction=by_direction,
    )


@router.post("/sequences", response_model=SequenceOut, status_code=status.HTTP_201_CREATED)
def create_sequence(
    payload: SequenceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a drip email sequence for a lead. Steps are sent automatically at day_offset intervals."""
    steps = [s.model_dump() for s in payload.steps]
    seq = email_sequence_service.create_sequence(
        db=db,
        lead_id=payload.lead_id,
        name=payload.name,
        steps=steps,
        created_by=current_user.email,
    )
    return seq


@router.get("/sequences", response_model=list[SequenceOut])
def list_sequences(
    lead_id: Optional[UUID] = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return email_sequence_service.list_sequences(db, lead_id=lead_id)


@router.post("/sequences/{sequence_id}/pause", status_code=status.HTTP_204_NO_CONTENT)
def pause_sequence(
    sequence_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    email_sequence_service.pause_sequence(db, sequence_id)


@router.post("/sequences/{sequence_id}/cancel", status_code=status.HTTP_204_NO_CONTENT)
def cancel_sequence(
    sequence_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    email_sequence_service.cancel_sequence(db, sequence_id)


@router.post("/{email_id}/gaps/resolve", response_model=EmailOut)
def resolve_gap(
    email_id: UUID,
    payload: GapResolveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Sales person fills in the answer for a specific RAG gap.
    The answer is embedded into the RAG vector store immediately so future
    emails about the same product get a complete answer.
    The gap is marked resolved in the email record.
    """
    email = db.query(Email).filter(Email.id == email_id).first()
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")

    gaps: list[dict] = list(email.followup_gaps or [])
    if payload.gap_index < 0 or payload.gap_index >= len(gaps):
        raise HTTPException(status_code=400, detail=f"gap_index {payload.gap_index} out of range (0–{len(gaps)-1})")

    gap = gaps[payload.gap_index]
    if gap.get("resolved"):
        raise HTTPException(status_code=400, detail="Gap already resolved")

    # Embed the answer into the product knowledge base
    product_id_str = gap.get("product_id")
    category = payload.category or gap.get("topic", "general")

    if product_id_str:
        try:
            from uuid import UUID as _UUID
            product_knowledge_service.add_entry(
                db=db,
                product_id=_UUID(product_id_str),
                category=category,
                content=f"Q: {gap['question']}\nA: {payload.answer}",
                added_by=current_user.email,
            )
            product_knowledge_service.update_coverage_score(db, product_id_str)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to embed knowledge: {e}")

    # Mark gap resolved
    gaps[payload.gap_index] = {
        **gap,
        "resolved": True,
        "answer": payload.answer,
        "resolved_by": current_user.email,
    }
    email.followup_gaps = gaps
    db.commit()
    db.refresh(email)
    return email


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

    # Send resolution confirmation to the customer
    try:
        sender_email_addr = gmail_service.extract_email_address(email.sender)
        display_name = email.sender.split("<")[0].strip() or sender_email_addr.split("@")[0]
        first_name = display_name.split()[0].title() if display_name else "Customer"
        resolution_subject = email.subject if email.subject.startswith("Re:") else f"Re: {email.subject}"
        resolution_body = (
            f"Dear {first_name},\n\n"
            "Thank you for your patience. Your query has been reviewed and addressed by our team.\n\n"
        )
        if payload.note:
            resolution_body += f"{payload.note}\n\n"
        resolution_body += (
            "If you have any further questions, please don't hesitate to reach out.\n\n"
            "Best regards,\nRDL Technologies Support Team"
        )
        gmail_svc = gmail_service.get_gmail_service()
        gmail_service.send_email(
            gmail_svc,
            to=sender_email_addr,
            subject=resolution_subject,
            body=resolution_body,
            thread_id=email.gmail_thread_id,
        )
    except Exception as e:
        logger.warning(f"[GMAIL] Failed to send resolution confirmation: {e}")

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

@router.post("/generate-draft", response_model=GenerateDraftResponse)
def generate_draft(
    payload: GenerateDraftRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Generate an AI draft reply using the RAG pipeline.
    Returns the draft text only — does NOT send or save anything.
    The caller edits the draft in the UI, then calls /send when ready.
    """
    draft = _generate_sales_draft(
        sender=payload.to,
        subject=payload.subject,
        body=payload.body,
    )
    if not draft:
        raise HTTPException(status_code=503, detail="AI draft generation failed — check Vertex AI connectivity")
    return GenerateDraftResponse(draft=draft)


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
