from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import Optional
from uuid import UUID

from app.api.dependencies import get_current_user
from app.database.core import get_db
from app.models.user import User
from app.schema.deal import DealCreate, DealListResponse, DealOut, DealUpdate
from app.services import deal_service

router = APIRouter(prefix="/deals", tags=["Deals"])


@router.post("/", response_model=DealOut, status_code=status.HTTP_201_CREATED)
def create_deal(
    payload: DealCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    try:
        return deal_service.create_deal(db, payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/", response_model=DealListResponse)
def list_deals(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    stage: Optional[str] = Query(None),
    company_id: Optional[UUID] = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    items, total = deal_service.list_deals(db, page=page, limit=limit, stage=stage, company_id=company_id)
    return DealListResponse(items=items, total=total, page=page, limit=limit)


@router.get("/{deal_id}", response_model=DealOut)
def get_deal(
    deal_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    deal = deal_service.get_deal(db, deal_id)
    if not deal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")
    return deal


@router.patch("/{deal_id}", response_model=DealOut)
def update_deal(
    deal_id: UUID,
    payload: DealUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    deal = deal_service.update_deal(db, deal_id, payload)
    if not deal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")
    return deal


@router.delete("/{deal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_deal(
    deal_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    if not deal_service.delete_deal(db, deal_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")
