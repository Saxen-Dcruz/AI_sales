from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, field_validator
from app.models.calendar_event import EventTrigger, EventStatus


class ScheduleMeetingRequest(BaseModel):
    attendee_email: str
    title: str
    description: Optional[str] = ""
    start_time: datetime
    duration_minutes: int = 30
    lead_id: Optional[UUID] = None
    deal_id: Optional[UUID] = None

    @field_validator("duration_minutes")
    @classmethod
    def validate_duration(cls, v: int) -> int:
        if v < 15 or v > 120:
            raise ValueError("duration_minutes must be between 15 and 120")
        return v


class CalendarEventOut(BaseModel):
    id: UUID
    google_event_id: Optional[str]
    lead_id: Optional[UUID]
    deal_id: Optional[UUID]
    title: str
    description: Optional[str]
    attendee_email: str
    start_time: datetime
    end_time: datetime
    meet_link: Optional[str]
    calendar_link: Optional[str]
    trigger: EventTrigger
    status: EventStatus
    invite_email_sent: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class RescheduleMeetingRequest(BaseModel):
    new_start_time: Optional[datetime] = None  # None = auto-find next free slot


class BlockedTimeCreate(BaseModel):
    day_of_week: int   # 0=Mon … 5=Sat
    start_hour: int    # 0–23
    end_hour: int      # 0–23 exclusive
    label: Optional[str] = None

    @field_validator("day_of_week")
    @classmethod
    def validate_day(cls, v):
        if v < 0 or v > 5:
            raise ValueError("day_of_week must be 0 (Mon) to 5 (Sat)")
        return v

    @field_validator("start_hour", "end_hour")
    @classmethod
    def validate_hour(cls, v):
        if v < 0 or v > 23:
            raise ValueError("hour must be 0–23")
        return v


class BlockedTimeOut(BaseModel):
    id: UUID
    day_of_week: int
    start_hour: int
    end_hour: int
    label: Optional[str]
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class CalendarEventListResponse(BaseModel):
    items: list[CalendarEventOut]
    total: int
    page: int
    limit: int
