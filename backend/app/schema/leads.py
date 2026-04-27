from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID


class LeadCreate(BaseModel):
    name: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    headline: Optional[str] = None
    location: Optional[str] = None
    current_role: Optional[str] = None
    about: Optional[str] = None
    company_id: Optional[UUID] = None
    status: Optional[str] = "Uncontacted"
    interest_level: Optional[str] = "Cold"


class LeadUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    headline: Optional[str] = None
    location: Optional[str] = None
    current_role: Optional[str] = None
    about: Optional[str] = None
    company_id: Optional[UUID] = None
    status: Optional[str] = None
    interest_level: Optional[str] = None
    overall_sentiment: Optional[str] = None
    last_contacted_at: Optional[datetime] = None
    next_followup_at: Optional[datetime] = None
    global_ai_summary: Optional[str] = None
    next_best_action: Optional[str] = None
    engagement_score: Optional[int] = None


class LeadOut(BaseModel):
    id: UUID
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    headline: Optional[str] = None
    location: Optional[str] = None
    current_role: Optional[str] = None
    about: Optional[str] = None
    company_id: Optional[UUID] = None
    company_name: Optional[str] = None
    status: str
    interest_level: str
    overall_sentiment: str
    last_contacted_at: Optional[datetime] = None
    next_followup_at: Optional[datetime] = None
    global_ai_summary: Optional[str] = None
    next_best_action: Optional[str] = None
    engagement_score: int
    classification: str
    classification_reason: Optional[str] = None
    inbound_first_contact: Optional[bool] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class LeadListResponse(BaseModel):
    items: List[LeadOut]
    total: int
    page: int
    limit: int


class LeadClassificationTierStats(BaseModel):
    count: int
    avg_score: float
    pct: float


class LeadClassificationSummary(BaseModel):
    total: int
    high: LeadClassificationTierStats
    medium: LeadClassificationTierStats
    low: LeadClassificationTierStats
    unclassified: LeadClassificationTierStats


class LeadScoreSignals(BaseModel):
    intent: Optional[str] = None
    urgency: Optional[str] = None
    sentiment: Optional[str] = None
    inbound_first_contact: bool
    total_emails: int
    inbound_emails: int
    outbound_emails: int
    total_calls: int
    inbound_calls: int
    outbound_calls: int
    total_meetings: int
    days_since_last_activity: Optional[int] = None
    active_deal_stage: Optional[str] = None
    deal_win_probability: Optional[float] = None
    has_unresolved_gaps: bool
    total_gap_count: int
    call_response_count: int      # calls where outcome != no_answer
    email_reply_count: int        # inbound emails (they replied to us)


class LeadScoreBreakdown(BaseModel):
    lead_id: UUID
    name: str
    classification: str
    engagement_score: int
    classification_reason: Optional[str]
    next_best_action: Optional[str]
    signals: LeadScoreSignals
