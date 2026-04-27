from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, field_validator
from app.models.call import CallDirection, CallStatus, CallOutcome
from app.schema.gmail import GapItem


class CallCreate(BaseModel):
    direction: CallDirection
    phone_number: Optional[str] = None
    lead_id: Optional[UUID] = None
    livekit_room: Optional[str] = None
    handled_by: Optional[str] = None


class CallUpdate(BaseModel):
    status: Optional[CallStatus] = None
    outcome: Optional[CallOutcome] = None
    ended_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    recording_url: Optional[str] = None
    notes: Optional[str] = None
    handled_by: Optional[str] = None


class TranscriptSubmit(BaseModel):
    transcript: str


class CallOut(BaseModel):
    id: UUID
    lead_id: Optional[UUID]
    direction: CallDirection
    status: CallStatus
    outcome: Optional[CallOutcome]
    phone_number: Optional[str]
    livekit_room: Optional[str]
    recording_url: Optional[str]
    started_at: Optional[datetime]
    ended_at: Optional[datetime]
    duration_seconds: int
    transcript: Optional[str]
    ai_summary: Optional[str]
    sentiment: Optional[str]
    detected_product_id: Optional[str]
    detected_product_name: Optional[str]
    followup_gaps: Optional[list[GapItem]]
    intent: Optional[str]
    urgency: Optional[str]
    product_interest: Optional[str]
    handled_by: Optional[str]
    notes: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("followup_gaps", mode="before")
    @classmethod
    def coerce_gaps(cls, v):
        if not v:
            return v
        result = []
        for item in v:
            if isinstance(item, str):
                result.append(GapItem(question=item, topic="general", product_name=None, product_id=None))
            else:
                result.append(item)
        return result


class CallListResponse(BaseModel):
    items: list[CallOut]
    total: int
    page: int
    limit: int


class CallGapNotificationOut(BaseModel):
    call_id: UUID
    phone_number: Optional[str]
    detected_product_name: Optional[str]
    started_at: Optional[datetime]
    gaps: list[GapItem]

    model_config = {"from_attributes": True}


class CallGapNotificationListResponse(BaseModel):
    items: list[CallGapNotificationOut]
    total: int


class CallAnalyticsResponse(BaseModel):
    total_calls: int
    by_direction: dict
    by_status: dict
    by_outcome: dict
    by_sentiment: dict
    by_intent: dict
    avg_duration_seconds: float
    avg_duration_minutes: float
