from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.models.calendar_event import CalendarEvent, EventStatus, EventTrigger
from app.models.user import User
from app.schema.calendar import CalendarEventListResponse, CalendarEventOut, ScheduleMeetingRequest
from app.services.calendar_service import cancel_event, create_meeting

router = APIRouter(prefix="/calendar", tags=["Calendar"])


@router.post("/schedule", response_model=CalendarEventOut, status_code=status.HTTP_201_CREATED)
def schedule_meeting(
    payload: ScheduleMeetingRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Manually schedule a Google Meet call and send an invite email."""
    try:
        event = create_meeting(
            db=db,
            attendee_email=payload.attendee_email,
            title=payload.title,
            description=payload.description or "",
            start_time=payload.start_time,
            duration_minutes=payload.duration_minutes,
            trigger=EventTrigger.MANUAL,
            lead_id=payload.lead_id,
            deal_id=payload.deal_id,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create calendar event: {e}")
    return event


@router.get("/", response_model=CalendarEventListResponse)
def list_events(
    status: Optional[EventStatus] = Query(default=None),
    trigger: Optional[EventTrigger] = Query(default=None),
    lead_id: Optional[UUID] = Query(default=None),
    deal_id: Optional[UUID] = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = db.query(CalendarEvent)
    if status:
        q = q.filter(CalendarEvent.status == status)
    if trigger:
        q = q.filter(CalendarEvent.trigger == trigger)
    if lead_id:
        q = q.filter(CalendarEvent.lead_id == lead_id)
    if deal_id:
        q = q.filter(CalendarEvent.deal_id == deal_id)
    total = q.count()
    items = q.order_by(CalendarEvent.created_at.desc()).offset((page - 1) * limit).limit(limit).all()
    return CalendarEventListResponse(items=items, total=total, page=page, limit=limit)


@router.get("/{event_id}", response_model=CalendarEventOut)
def get_event(
    event_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    event = db.query(CalendarEvent).filter(CalendarEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_meeting(
    event_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    event = db.query(CalendarEvent).filter(CalendarEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.status == EventStatus.CANCELLED:
        raise HTTPException(status_code=400, detail="Event already cancelled")
    cancel_event(db, event)
