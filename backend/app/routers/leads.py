from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import Optional
from uuid import UUID

from app.api.dependencies import get_current_user
from app.database.core import get_db
from app.models.user import User
from app.schema.leads import LeadCreate, LeadListResponse, LeadOut, LeadUpdate
from app.services import leads_service

router = APIRouter(prefix="/leads", tags=["Leads"])


@router.post("/", response_model=LeadOut, status_code=status.HTTP_201_CREATED)
def create_lead(
    payload: LeadCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return leads_service.create_lead(db, payload)


@router.get("/", response_model=LeadListResponse)
def list_leads(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    items, total = leads_service.list_leads(db, page=page, limit=limit, status=status, search=search)
    return LeadListResponse(items=items, total=total, page=page, limit=limit)


@router.get("/{lead_id}", response_model=LeadOut)
def get_lead(
    lead_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    lead = leads_service.get_lead(db, lead_id)
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
    return lead


@router.patch("/{lead_id}", response_model=LeadOut)
def update_lead(
    lead_id: UUID,
    payload: LeadUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    lead = leads_service.update_lead(db, lead_id, payload)
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
    return lead


@router.delete("/{lead_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_lead(
    lead_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    if not leads_service.delete_lead(db, lead_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
