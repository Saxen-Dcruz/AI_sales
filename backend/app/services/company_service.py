from typing import List, Optional, Tuple
from uuid import UUID
from sqlalchemy.orm import Session

from app.models.company import Company
from app.schema.company import CompanyCreate, CompanyUpdate


def create_company(db: Session, payload: CompanyCreate) -> Company:
    company = Company(**payload.model_dump(exclude_none=True))
    db.add(company)
    db.commit()
    db.refresh(company)
    return company


def get_company(db: Session, company_id: UUID) -> Optional[Company]:
    return db.query(Company).filter(Company.id == company_id).first()


def list_companies(
    db: Session,
    page: int = 1,
    limit: int = 20,
    search: Optional[str] = None,
    industry: Optional[str] = None,
) -> Tuple[List[Company], int]:
    q = db.query(Company)
    if industry:
        q = q.filter(Company.industry == industry)
    if search:
        q = q.filter(Company.name.ilike(f"%{search}%"))
    total = q.count()
    items = q.order_by(Company.created_at.desc()).offset((page - 1) * limit).limit(limit).all()
    return items, total


def update_company(db: Session, company_id: UUID, payload: CompanyUpdate) -> Optional[Company]:
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        return None
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(company, field, value)
    db.commit()
    db.refresh(company)
    return company


def delete_company(db: Session, company_id: UUID) -> bool:
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        return False
    db.delete(company)
    db.commit()
    return True
