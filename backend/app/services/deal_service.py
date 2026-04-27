import logging
from typing import List, Optional, Tuple
from uuid import UUID
from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.deal import Deal
from app.schema.deal import DealCreate, DealUpdate

logger = logging.getLogger("rdl_app_logger")


def create_deal(db: Session, payload: DealCreate) -> Deal:
    if not db.query(Company).filter(Company.id == payload.company_id).first():
        raise ValueError("Company not found")
    deal = Deal(**payload.model_dump(exclude_none=True))
    db.add(deal)
    db.commit()
    db.refresh(deal)
    return deal


def get_deal(db: Session, deal_id: UUID) -> Optional[Deal]:
    return db.query(Deal).filter(Deal.id == deal_id).first()


def list_deals(
    db: Session,
    page: int = 1,
    limit: int = 20,
    stage: Optional[str] = None,
    company_id: Optional[UUID] = None,
) -> Tuple[List[Deal], int]:
    q = db.query(Deal)
    if stage:
        q = q.filter(Deal.stage == stage)
    if company_id:
        q = q.filter(Deal.company_id == company_id)
    total = q.count()
    items = q.order_by(Deal.created_at.desc()).offset((page - 1) * limit).limit(limit).all()
    return items, total


def update_deal(db: Session, deal_id: UUID, payload: DealUpdate) -> Optional[Deal]:
    deal = db.query(Deal).filter(Deal.id == deal_id).first()
    if not deal:
        return None

    prev_stage = deal.stage
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(deal, field, value)
    db.commit()
    db.refresh(deal)

    stage_changed = payload.stage is not None and payload.stage != prev_stage

    # Recalculate lead score when stage or probability changes
    if deal.lead_id and (stage_changed or payload.win_probability is not None):
        try:
            from app.services.lead_scoring_service import update_lead_score
            update_lead_score(db, deal.lead_id)
        except Exception as e:
            logger.warning(f"[DEAL] Lead score update failed: {e}")

    # Auto-schedule meeting when stage moves into a positive signal
    if stage_changed and deal.lead_id:
        try:
            from app.services.deal_signal_service import evaluate_deal_signal
            from app.models.leads import Lead
            lead = db.query(Lead).filter(Lead.id == deal.lead_id).first()
            if lead and lead.email and evaluate_deal_signal(db, deal):
                from app.services.calendar_service import create_meeting, find_next_free_slot
                from app.models.calendar_event import EventTrigger
                slot = find_next_free_slot(hours_from_now=24)
                create_meeting(
                    db=db,
                    attendee_email=lead.email,
                    title=f"Sales Discussion — {deal.deal_name}",
                    description=(
                        f"Deal stage updated to '{deal.stage}'.\n"
                        f"Win probability: {deal.win_probability}%\n"
                        f"Deal value: ₹{deal.deal_value}"
                    ),
                    start_time=slot,
                    duration_minutes=30,
                    trigger=EventTrigger.DEAL_SIGNAL,
                    lead_id=deal.lead_id,
                    deal_id=deal.id,
                )
                logger.info(f"[DEAL] Auto-scheduled meeting for deal '{deal.deal_name}' (stage → {deal.stage})")
        except Exception as e:
            logger.warning(f"[DEAL] Auto-schedule on stage change failed: {e}")

    return deal


def delete_deal(db: Session, deal_id: UUID) -> bool:
    deal = db.query(Deal).filter(Deal.id == deal_id).first()
    if not deal:
        return False
    db.delete(deal)
    db.commit()
    return True
