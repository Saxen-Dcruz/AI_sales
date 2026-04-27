"""
Email drip sequence service.

A sequence is a list of follow-up emails sent to a lead at fixed day offsets.
The poller calls process_due_steps() every cycle to send any steps whose send_at has passed.
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.email_sequence import EmailSequence, EmailSequenceStep, SequenceStatus, StepStatus

logger = logging.getLogger("rdl_app_logger")


def create_sequence(
    db: Session,
    lead_id: UUID,
    name: str,
    steps: list[dict],   # [{"day_offset": 0, "subject": "...", "body": "..."}]
    created_by: Optional[str] = None,
) -> EmailSequence:
    """Create a drip sequence with its steps. send_at is computed from now + day_offset."""
    seq = EmailSequence(lead_id=lead_id, name=name, created_by=created_by)
    db.add(seq)
    db.flush()

    now = datetime.now(timezone.utc)
    for s in steps:
        step = EmailSequenceStep(
            sequence_id=seq.id,
            day_offset=s["day_offset"],
            subject=s["subject"],
            body=s["body"],
            send_at=now + timedelta(days=s["day_offset"]),
        )
        db.add(step)

    db.commit()
    db.refresh(seq)
    logger.info(f"[SEQUENCE] Created '{name}' for lead {lead_id} with {len(steps)} steps")
    return seq


def pause_sequence(db: Session, sequence_id: UUID) -> None:
    seq = db.query(EmailSequence).filter(EmailSequence.id == sequence_id).first()
    if seq:
        seq.status = SequenceStatus.PAUSED
        db.commit()


def cancel_sequence(db: Session, sequence_id: UUID) -> None:
    seq = db.query(EmailSequence).filter(EmailSequence.id == sequence_id).first()
    if seq:
        seq.status = SequenceStatus.CANCELLED
        db.commit()


def list_sequences(db: Session, lead_id: Optional[UUID] = None) -> list[EmailSequence]:
    q = db.query(EmailSequence)
    if lead_id:
        q = q.filter(EmailSequence.lead_id == lead_id)
    return q.order_by(EmailSequence.created_at.desc()).all()


def process_due_steps(db: Session) -> int:
    """
    Send all pending steps whose send_at <= now and whose sequence is ACTIVE.
    Called by the Gmail poller every cycle.
    Returns number of steps sent.
    """
    from app.services.gmail_service import get_gmail_service, send_email
    from app.models.leads import Lead

    now = datetime.now(timezone.utc)
    due_steps = (
        db.query(EmailSequenceStep)
        .join(EmailSequence)
        .filter(
            EmailSequenceStep.status == StepStatus.PENDING,
            EmailSequenceStep.send_at <= now,
            EmailSequence.status == SequenceStatus.ACTIVE,
        )
        .all()
    )

    if not due_steps:
        return 0

    try:
        svc = get_gmail_service()
    except Exception as e:
        logger.error(f"[SEQUENCE] Gmail service unavailable: {e}")
        return 0

    sent = 0
    for step in due_steps:
        seq = step.sequence
        lead = db.query(Lead).filter(Lead.id == seq.lead_id).first()
        if not lead or not lead.email:
            step.status = StepStatus.SKIPPED
            db.commit()
            continue
        try:
            result = send_email(svc, to=lead.email, subject=step.subject, body=step.body)
            step.status = StepStatus.SENT
            step.sent_at = now
            step.gmail_message_id = result.get("id")
            sent += 1
            logger.info(f"[SEQUENCE] Step sent: '{step.subject}' → {lead.email}")
        except Exception as e:
            logger.error(f"[SEQUENCE] Failed to send step {step.id}: {e}")

        db.commit()

    # Mark sequences whose all steps are sent/skipped as completed
    for step in due_steps:
        seq = step.sequence
        if all(s.status in (StepStatus.SENT, StepStatus.SKIPPED) for s in seq.steps):
            seq.status = SequenceStatus.COMPLETED
    db.commit()

    return sent
