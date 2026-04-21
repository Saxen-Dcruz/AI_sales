from typing import List, Optional, Tuple
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models.leads import Lead
from app.schema.leads import LeadCreate, LeadUpdate


def create_lead(db: Session, payload: LeadCreate) -> Lead:
    lead = Lead(**payload.model_dump(exclude_none=True))
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead


def get_lead(db: Session, lead_id: UUID) -> Optional[Lead]:
    return db.query(Lead).filter(Lead.id == lead_id).first()


def list_leads(
    db: Session,
    page: int = 1,
    limit: int = 20,
    status: Optional[str] = None,
    search: Optional[str] = None,
) -> Tuple[List[Lead], int]:
    q = db.query(Lead)
    if status:
        q = q.filter(Lead.status == status)
    if search:
        pattern = f"%{search}%"
        q = q.filter(
            or_(Lead.name.ilike(pattern), Lead.email.ilike(pattern), Lead.current_role.ilike(pattern))
        )
    total = q.count()
    items = q.order_by(Lead.created_at.desc()).offset((page - 1) * limit).limit(limit).all()
    return items, total


def update_lead(db: Session, lead_id: UUID, payload: LeadUpdate) -> Optional[Lead]:
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        return None
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(lead, field, value)
    db.commit()
    db.refresh(lead)
    return lead


def delete_lead(db: Session, lead_id: UUID) -> bool:
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        return False
    db.delete(lead)
    db.commit()
    return True
