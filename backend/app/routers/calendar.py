from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.models.blocked_time import BlockedTime
from app.models.calendar_event import CalendarEvent, EventStatus, EventTrigger
from app.models.user import User
from app.models.operator_availability import OperatorAvailability, SchedulingConfig
from app.schema.calendar import (
    DAYS,
    AvailabilityDayOut, AvailabilityDayUpdate,
    BlockedTimeCreate, BlockedTimeOut,
    CalendarEventListResponse, CalendarEventOut,
    RescheduleMeetingRequest, ScheduleMeetingRequest,
    SchedulingConfigOut, SchedulingConfigUpdate,
)
from app.services.calendar_service import cancel_event, create_meeting, reschedule_event

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


# ── Recurring availability blocks (must be before /{event_id} to avoid shadowing) ──

@router.post("/blocked-times", response_model=BlockedTimeOut, status_code=status.HTTP_201_CREATED)
def add_blocked_time(
    payload: BlockedTimeCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    if payload.start_hour >= payload.end_hour:
        raise HTTPException(status_code=422, detail="start_hour must be less than end_hour")
    block = BlockedTime(**payload.model_dump())
    db.add(block)
    db.commit()
    db.refresh(block)
    return block


@router.get("/blocked-times", response_model=list[BlockedTimeOut])
def list_blocked_times(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return db.query(BlockedTime).filter(BlockedTime.is_active == True).order_by(
        BlockedTime.day_of_week, BlockedTime.start_hour
    ).all()


@router.delete("/blocked-times/{block_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_blocked_time(
    block_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    block = db.query(BlockedTime).filter(BlockedTime.id == block_id).first()
    if not block:
        raise HTTPException(status_code=404, detail="Blocked time not found")
    db.delete(block)
    db.commit()


# ── Operator availability ─────────────────────────────────────────────────────

def _avail_row_to_out(r: OperatorAvailability) -> AvailabilityDayOut:
    return AvailabilityDayOut(
        day_of_week=r.day_of_week,
        day_name=DAYS[r.day_of_week],
        is_available=r.is_available,
        start_hour=r.start_hour,
        start_minute=r.start_minute,
        end_hour=r.end_hour,
        end_minute=r.end_minute,
    )


# Default schedule: Mon–Fri 9–18, Sat 9–14, Sun off
_DEFAULT_AVAIL = {
    0: (True,  9, 18),   # Mon
    1: (True,  9, 18),   # Tue
    2: (True,  9, 18),   # Wed
    3: (True,  9, 18),   # Thu
    4: (True,  9, 18),   # Fri
    5: (True,  9, 14),   # Sat
    6: (False, 9, 18),   # Sun
}


@router.get("/availability", response_model=list[AvailabilityDayOut])
def get_availability(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    existing = {r.day_of_week: r for r in db.query(OperatorAvailability).all()}
    result = []
    seeded = False
    for day in range(7):
        if day not in existing:
            avail, sh, eh = _DEFAULT_AVAIL[day]
            row = OperatorAvailability(
                day_of_week=day, is_available=avail,
                start_hour=sh, start_minute=0, end_hour=eh, end_minute=0,
            )
            db.add(row)
            existing[day] = row
            seeded = True
    if seeded:
        db.commit()
        for row in existing.values():
            db.refresh(row)
    return [_avail_row_to_out(existing[d]) for d in range(7)]


@router.put("/availability/{day_of_week}", response_model=AvailabilityDayOut)
def update_availability_day(
    day_of_week: int,
    payload: AvailabilityDayUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    if day_of_week < 0 or day_of_week > 6:
        raise HTTPException(status_code=422, detail="day_of_week must be 0–6")
    row = db.query(OperatorAvailability).filter(
        OperatorAvailability.day_of_week == day_of_week
    ).first()
    if not row:
        row = OperatorAvailability(day_of_week=day_of_week)
        db.add(row)
    row.is_available = payload.is_available
    row.start_hour = payload.start_hour
    row.start_minute = payload.start_minute
    row.end_hour = payload.end_hour
    row.end_minute = payload.end_minute
    db.commit()
    db.refresh(row)
    return _avail_row_to_out(row)


@router.get("/scheduling-config", response_model=SchedulingConfigOut)
def get_scheduling_config(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    cfg = db.query(SchedulingConfig).filter(SchedulingConfig.id == 1).first()
    if not cfg:
        cfg = SchedulingConfig(id=1)
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
    return cfg


@router.patch("/scheduling-config", response_model=SchedulingConfigOut)
def update_scheduling_config(
    payload: SchedulingConfigUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    cfg = db.query(SchedulingConfig).filter(SchedulingConfig.id == 1).first()
    if not cfg:
        cfg = SchedulingConfig(id=1)
        db.add(cfg)
    if payload.buffer_minutes is not None:
        cfg.buffer_minutes = payload.buffer_minutes
    if payload.slot_duration_minutes is not None:
        cfg.slot_duration_minutes = payload.slot_duration_minutes
    if payload.max_meetings_per_day is not None:
        cfg.max_meetings_per_day = payload.max_meetings_per_day
    db.commit()
    db.refresh(cfg)
    return cfg


# ── Single event CRUD (parameterized — must be AFTER all literal paths) ───────

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


@router.patch("/{event_id}/reschedule", response_model=CalendarEventOut)
def reschedule_meeting(
    event_id: UUID,
    payload: RescheduleMeetingRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """
    Reschedule an existing event.
    - Pass new_start_time to set a specific time.
    - Leave new_start_time null to auto-find the next free slot on the calendar.
    Updates Google Calendar (attendees get notified), meet_link preserved, DB updated.
    """
    event = db.query(CalendarEvent).filter(CalendarEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.status == EventStatus.CANCELLED:
        raise HTTPException(status_code=400, detail="Cannot reschedule a cancelled event")
    try:
        return reschedule_event(db, event, payload.new_start_time)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Reschedule failed: {e}")


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_meeting(  # noqa: E302
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


