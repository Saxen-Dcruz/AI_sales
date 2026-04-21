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


class CalendarEventListResponse(BaseModel):
    items: list[CalendarEventOut]
    total: int
    page: int
    limit: int
