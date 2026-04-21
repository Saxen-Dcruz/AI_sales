from typing import List, Optional, Tuple
from uuid import UUID
from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.deal import Deal
from app.schema.deal import DealCreate, DealUpdate


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
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(deal, field, value)
    db.commit()
    db.refresh(deal)
    return deal


def delete_deal(db: Session, deal_id: UUID) -> bool:
    deal = db.query(Deal).filter(Deal.id == deal_id).first()
    if not deal:
        return False
    db.delete(deal)
    db.commit()
    return True
