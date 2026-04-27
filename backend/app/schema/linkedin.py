from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel


class LinkedInOutreachOut(BaseModel):
    id: UUID
    lead_id: Optional[UUID]
    company_id: Optional[UUID]
    linkedin_url: Optional[str]
    full_name: Optional[str]
    headline: Optional[str]
    location: Optional[str]
    company_name: Optional[str]
    role_category: Optional[str]
    industry_tag: Optional[str]
    city_tag: Optional[str]
    connection_status: str
    connection_sent_at: Optional[datetime]
    message_status: str
    message_sent_at: Optional[datetime]
    message_body: Optional[str]
    message_template_key: Optional[str]
    reply_received_at: Optional[datetime]
    reply_preview: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class LinkedInOutreachListResponse(BaseModel):
    items: list[LinkedInOutreachOut]
    total: int
    page: int
    limit: int


class LinkedInOutreachCreate(BaseModel):
    linkedin_url: str
    full_name: Optional[str] = None
    headline: Optional[str] = None
    location: Optional[str] = None
    company_name: Optional[str] = None
    industry_tag: Optional[str] = None
    city_tag: Optional[str] = None
    lead_id: Optional[UUID] = None
    company_id: Optional[UUID] = None


class ReplyUpdate(BaseModel):
    reply_preview: str


class DiscoveryJobRequest(BaseModel):
    city_batch: Optional[list[str]] = None       # subset of cities; None = all
    industry_batch: Optional[list[str]] = None   # subset of industries; None = all
    max_results_per_query: int = 100
    delay_min: float = 3.0
    delay_max: float = 7.0


class OutreachStatsResponse(BaseModel):
    total_discovered: int
    connection_not_sent: int
    connection_pending: int
    connection_accepted: int
    connection_rate_pct: float
    messages_sent: int
    messages_replied: int
    reply_rate_pct: float
    daily_budget: dict
