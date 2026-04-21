from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import List, Optional
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
    status: str
    interest_level: str
    overall_sentiment: str
    last_contacted_at: Optional[datetime] = None
    next_followup_at: Optional[datetime] = None
    global_ai_summary: Optional[str] = None
    next_best_action: Optional[str] = None
    engagement_score: int
    created_at: datetime

    model_config = {"from_attributes": True}


class LeadListResponse(BaseModel):
    items: List[LeadOut]
    total: int
    page: int
    limit: int
