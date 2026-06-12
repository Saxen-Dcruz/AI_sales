from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import Optional
from uuid import UUID

from app.api.dependencies import get_current_user
from app.api.scoping import assert_can_access
from app.database.core import get_db
from app.models.deal import Deal
from app.models.user import User
from app.schema.deal import DealAnalyticsResponse, DealCreate, DealListResponse, DealOut, DealUpdate
from app.services import deal_service

router = APIRouter(prefix="/deals", tags=["Deals"])


def _effective_owner(current_user: User, requested: Optional[UUID]) -> Optional[UUID]:
    """Regular user → always own id; super-admin → requested (or None for all)."""
    if not current_user.is_superuser:
        return current_user.id
    return requested


@router.post("/", response_model=DealOut, status_code=status.HTTP_201_CREATED)
def create_deal(
    payload: DealCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return deal_service.create_deal(db, payload, owner_id=current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/", response_model=DealListResponse)
def list_deals(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    stage: Optional[str] = Query(None),
    company_id: Optional[UUID] = Query(None),
    at_risk: bool = Query(False, description="Return only open deals with no activity in 7+ days"),
    owner_id: Optional[UUID] = Query(default=None, description="Super-admin: scope to one user"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    effective = _effective_owner(current_user, owner_id)

    if at_risk:
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        q = (
            db.query(Deal)
            .filter(
                Deal.stage.notin_(["Closed Won", "Closed Lost"]),
                Deal.created_at < cutoff,
            )
            .order_by(Deal.created_at.asc())
        )
        if effective is not None:
            q = q.filter(Deal.owner_id == effective)
        total = q.count()
        items = q.offset((page - 1) * limit).limit(limit).all()
        return DealListResponse(items=items, total=total, page=page, limit=limit)

    items, total = deal_service.list_deals(
        db, page=page, limit=limit, stage=stage, company_id=company_id,
        owner_id_filter=effective,
    )
    return DealListResponse(items=items, total=total, page=page, limit=limit)


@router.get("/analytics", response_model=DealAnalyticsResponse)
def get_analytics(
    owner_id: Optional[UUID] = Query(default=None, description="Super-admin: scope to one user"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return deal_service.get_analytics(db, owner_id_filter=_effective_owner(current_user, owner_id))


@router.get("/{deal_id}", response_model=DealOut)
def get_deal(
    deal_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deal = deal_service.get_deal(db, deal_id)
    if not deal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")
    assert_can_access(deal, current_user)
    return deal


@router.patch("/{deal_id}", response_model=DealOut)
def update_deal(
    deal_id: UUID,
    payload: DealUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    existing = deal_service.get_deal(db, deal_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")
    assert_can_access(existing, current_user)
    return deal_service.update_deal(db, deal_id, payload)


@router.delete("/{deal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_deal(
    deal_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    existing = deal_service.get_deal(db, deal_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")
    assert_can_access(existing, current_user)
    deal_service.delete_deal(db, deal_id)
