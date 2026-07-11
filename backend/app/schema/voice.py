from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


# ── Request schemas ──────────────────────────────────────────────────────────

class CreateVoiceRoomRequest(BaseModel):
    channel_origin: str = Field(..., description="'whatsapp' | 'gmail' | 'direct'")
    channel_ref_id: Optional[UUID] = Field(None, description="WA message ID or email ID")
    lead_id: Optional[UUID] = None
    owner_id: Optional[UUID] = None  # injected from token if not provided


class EscalateRequest(BaseModel):
    escalation_type: str = Field(..., description="'gmeet' | 'office_call'")
    # Force-trigger escalation from UI or agent; normally auto-triggered by unanswered count


class SubmitFeedbackRequest(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = None

    @field_validator("rating")
    @classmethod
    def rating_in_range(cls, v: int) -> int:
        if not 1 <= v <= 5:
            raise ValueError("rating must be between 1 and 5")
        return v


class VoiceWebhookRequest(BaseModel):
    """LiveKit server-side webhook payload (minimal — we inspect event field)."""
    event: str
    room: Optional[dict] = None
    participant: Optional[dict] = None
    egress_info: Optional[dict] = None
    # Allow extra fields LiveKit may send
    model_config = {"extra": "allow"}


# ── Response schemas ─────────────────────────────────────────────────────────

class VoiceSessionOut(BaseModel):
    id: UUID
    room_name: str
    channel_origin: str
    channel_ref_id: Optional[UUID]
    lead_id: Optional[UUID]
    status: str
    join_url: str                       # Full URL customer opens in browser
    token_expires_at: datetime
    joined_at: Optional[datetime]
    ended_at: Optional[datetime]
    duration_seconds: Optional[int]
    unanswered_count: int
    escalation_type: str
    escalation_ref: Optional[str]
    feedback_sent: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class CreateVoiceRoomResponse(BaseModel):
    session: VoiceSessionOut
    join_url: str
    office_phone: str           # Always included so UI can show both options
    message: str = "Voice room ready"


class FreshTokenResponse(BaseModel):
    room_name: str
    token: str
    expires_at: datetime


class EscalationResponse(BaseModel):
    escalation_type: str
    escalation_ref: str         # GMeet URL or office phone
    message: str


class FeedbackOut(BaseModel):
    id: UUID
    session_id: UUID
    rating: int
    comment: Optional[str]
    channel_used: str
    submitted_at: datetime

    model_config = {"from_attributes": True}


# ── Analytics ────────────────────────────────────────────────────────────────

class VoiceChannelBreakdown(BaseModel):
    whatsapp: int = 0
    gmail: int = 0
    direct: int = 0


class VoiceEscalationBreakdown(BaseModel):
    none: int = 0
    gmeet: int = 0
    office_call: int = 0


class VoiceAnalyticsResponse(BaseModel):
    total_sessions: int
    active_now: int
    completed: int
    escalated: int
    expired: int                    # Never joined
    avg_duration_seconds: Optional[float]
    avg_unanswered_questions: float
    escalation_rate: float          # % of sessions that escalated
    avg_feedback_score: Optional[float]
    feedback_response_rate: float   # % of completed calls that got feedback
    by_channel: VoiceChannelBreakdown
    by_escalation: VoiceEscalationBreakdown
    knowledge_gaps_captured: int    # Gaps stored from voice calls
