from datetime import datetime, timezone, timedelta
from typing import List, Optional, Tuple
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models.leads import Lead
from app.schema.leads import LeadCreate, LeadUpdate


def create_lead(db: Session, payload: LeadCreate, owner_id: UUID) -> Lead:
    lead = Lead(owner_id=owner_id, **payload.model_dump(exclude_none=True))
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
    at_risk: Optional[bool] = None,
    classification: Optional[str] = None,
    owner_id_filter: Optional[UUID] = None,
) -> Tuple[List[Lead], int]:
    q = db.query(Lead)
    if owner_id_filter is not None:
        q = q.filter(Lead.owner_id == owner_id_filter)
    if status:
        q = q.filter(Lead.status == status)
    if search:
        pattern = f"%{search}%"
        q = q.filter(
            or_(Lead.name.ilike(pattern), Lead.email.ilike(pattern), Lead.current_role.ilike(pattern))
        )
    if at_risk is True:
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        q = q.filter(
            Lead.engagement_score < 40,
            or_(Lead.last_contacted_at < cutoff, Lead.last_contacted_at.is_(None)),
        )
    if classification:
        q = q.filter(Lead.classification == classification.upper())
    total = q.count()
    items = q.order_by(Lead.created_at.desc()).offset((page - 1) * limit).limit(limit).all()
    return items, total


def get_classification_summary(db: Session, owner_id_filter: Optional[UUID] = None) -> dict:
    """Count and average score per classification tier."""
    q = db.query(Lead)
    if owner_id_filter is not None:
        q = q.filter(Lead.owner_id == owner_id_filter)
    leads = q.all()
    total = len(leads)

    tiers: dict = {"HIGH": [], "MEDIUM": [], "LOW": [], "UNCLASSIFIED": []}
    for lead in leads:
        tier = (lead.classification or "UNCLASSIFIED").upper()
        tiers.setdefault(tier, []).append(lead.engagement_score or 0)

    def _stats(scores: list) -> dict:
        count = len(scores)
        avg   = round(sum(scores) / count, 1) if count else 0.0
        pct   = round(count / total * 100, 1) if total else 0.0
        return {"count": count, "avg_score": avg, "pct": pct}

    return {
        "total":        total,
        "high":         _stats(tiers["HIGH"]),
        "medium":       _stats(tiers["MEDIUM"]),
        "low":          _stats(tiers["LOW"]),
        "unclassified": _stats(tiers["UNCLASSIFIED"]),
    }


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
