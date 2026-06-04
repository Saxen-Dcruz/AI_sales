from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.api.scoping import assert_can_access
from app.models.call import Call, CallDirection, CallOutcome, CallStatus
from app.models.user import User
from app.schema.call import (
    CallAnalyticsResponse,
    CallCreate,
    CallGapNotificationListResponse,
    CallGapNotificationOut,
    CallListResponse,
    CallOut,
    CallUpdate,
    TranscriptSubmit,
)
from app.schema.gmail import GapItem, GapResolveRequest
from app.services import call_service

router = APIRouter(prefix="/calls", tags=["Calls"])


def _effective_owner(current_user: User, requested: Optional[UUID]) -> Optional[UUID]:
    """Regular user → own id; super-admin → requested or None for all."""
    if not current_user.is_superuser:
        return current_user.id
    return requested


# ── CRUD ──────────────────────────────────────────────────────────────────────

@router.post("/", response_model=CallOut, status_code=status.HTTP_201_CREATED)
def log_call(
    payload: CallCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Log a new inbound or outbound call."""
    return call_service.create_call(
        db=db,
        direction=payload.direction,
        owner_id=current_user.id,
        phone_number=payload.phone_number,
        lead_id=payload.lead_id,
        livekit_room=payload.livekit_room,
        handled_by=payload.handled_by or current_user.email,
    )


@router.get("/", response_model=CallListResponse)
def list_calls(
    lead_id: Optional[UUID] = Query(default=None),
    status: Optional[CallStatus] = Query(default=None),
    direction: Optional[CallDirection] = Query(default=None),
    outcome: Optional[CallOutcome] = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    owner_id: Optional[UUID] = Query(default=None, description="Super-admin: scope to one user"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items, total = call_service.list_calls(
        db, lead_id, status, direction, outcome, page, limit,
        owner_id_filter=_effective_owner(current_user, owner_id),
    )
    return CallListResponse(items=items, total=total, page=page, limit=limit)


@router.get("/analytics", response_model=CallAnalyticsResponse)
def call_analytics(
    owner_id: Optional[UUID] = Query(default=None, description="Super-admin: scope to one user"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Aggregate call metrics: volume, direction, outcome, sentiment, intent, avg duration."""
    return call_service.get_call_analytics(db, owner_id_filter=_effective_owner(current_user, owner_id))


@router.get("/gaps", response_model=CallGapNotificationListResponse)
def list_call_gaps(
    owner_id: Optional[UUID] = Query(default=None, description="Super-admin: scope to one user"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """All completed calls with unresolved RAG knowledge gaps."""
    q = (
        db.query(Call)
        .filter(
            Call.followup_gaps.isnot(None),
            Call.status == CallStatus.COMPLETED,
        )
    )
    effective = _effective_owner(current_user, owner_id)
    if effective is not None:
        q = q.filter(Call.owner_id == effective)
    rows = q.order_by(Call.created_at.desc()).all()
    items = [
        CallGapNotificationOut(
            call_id=r.id,
            phone_number=r.phone_number,
            detected_product_name=r.detected_product_name,
            started_at=r.started_at,
            gaps=[
                GapItem(**g) if isinstance(g, dict) else GapItem(question=g, topic="general", product_name=None, product_id=None)
                for g in (r.followup_gaps or [])
                if not (g.get("resolved") if isinstance(g, dict) else False)
            ],
        )
        for r in rows
        if any(
            not (g.get("resolved") if isinstance(g, dict) else False)
            for g in (r.followup_gaps or [])
        )
    ]
    return CallGapNotificationListResponse(items=items, total=len(items))


@router.get("/{call_id}", response_model=CallOut)
def get_call(
    call_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    call = call_service.get_call(db, call_id)
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    assert_can_access(call, current_user)
    return call


@router.patch("/{call_id}", response_model=CallOut)
def update_call(
    call_id: UUID,
    payload: CallUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    call = call_service.get_call(db, call_id)
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    assert_can_access(call, current_user)
    return call_service.update_call(db, call, **payload.model_dump(exclude_none=True))


# ── Transcript processing ─────────────────────────────────────────────────────

@router.post("/{call_id}/transcript", response_model=CallOut)
def submit_transcript(
    call_id: UUID,
    payload: TranscriptSubmit,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Submit a call transcript after the call ends.
    Triggers: product detection, AI summary, sentiment analysis, gap extraction.
    """
    call = call_service.get_call(db, call_id)
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    assert_can_access(call, current_user)
    if not payload.transcript.strip():
        raise HTTPException(status_code=422, detail="Transcript cannot be empty")
    return call_service.process_transcript(db, call, payload.transcript)


# ── Gap resolution ────────────────────────────────────────────────────────────

@router.post("/{call_id}/gaps/resolve", response_model=CallOut)
def resolve_call_gap(
    call_id: UUID,
    payload: GapResolveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Sales person fills in the answer for a gap from a call.
    Embeds the answer into the RAG knowledge base immediately.
    """
    call = call_service.get_call(db, call_id)
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    assert_can_access(call, current_user)
    try:
        return call_service.resolve_gap(
            db=db,
            call=call,
            gap_index=payload.gap_index,
            answer=payload.answer,
            category=payload.category,
            product_id=payload.product_id,
            resolved_by=current_user.email,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
