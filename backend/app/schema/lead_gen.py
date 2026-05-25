from datetime import datetime
from typing import Any, Optional
from uuid import UUID
from pydantic import BaseModel


# ── Prospect Company ───────────────────────────────────────────────────────────

class ProspectCompanyOut(BaseModel):
    id: UUID
    name: str
    industry: Optional[str]
    website: Optional[str]
    location: Optional[str]
    company_size: Optional[str]
    linkedin_url: Optional[str]
    description: Optional[str]
    technologies: Optional[list]
    source: Optional[str]
    ai_score: Optional[int]
    ai_score_reasoning: Optional[str]
    interest_level: Optional[str]
    created_at: datetime
    model_config = {"from_attributes": True}


class ProspectCompanyCreate(BaseModel):
    name: str
    industry: Optional[str] = None
    website: Optional[str] = None
    location: Optional[str] = None
    company_size: Optional[str] = None
    linkedin_url: Optional[str] = None
    description: Optional[str] = None
    technologies: Optional[list] = None


# ── Prospect Contact ───────────────────────────────────────────────────────────

class ProspectContactOut(BaseModel):
    id: UUID
    company_id: UUID
    name: str
    email: Optional[str]
    job_title: Optional[str]
    linkedin_url: Optional[str]
    created_at: datetime
    company: Optional[ProspectCompanyOut] = None
    model_config = {"from_attributes": True}


class ProspectContactCreate(BaseModel):
    company_id: UUID
    name: str
    email: Optional[str] = None
    job_title: Optional[str] = None
    linkedin_url: Optional[str] = None


# ── Outreach Campaign ──────────────────────────────────────────────────────────

class OutreachCampaignOut(BaseModel):
    id: UUID
    name: str
    target_industry: Optional[str]
    target_roles: Optional[list]
    status: str
    auto_send: bool
    email_template_prompt: Optional[str]
    product_context: Optional[str]
    email_subject: Optional[str]
    assigned_account_id: Optional[UUID]
    created_at: datetime
    updated_at: datetime
    contact_count: int = 0
    sent_count: int = 0
    replied_count: int = 0
    model_config = {"from_attributes": True}


class OutreachCampaignCreate(BaseModel):
    name: str
    target_industry: Optional[str] = None
    target_roles: Optional[list] = None
    auto_send: bool = False
    email_template_prompt: Optional[str] = None
    product_context: Optional[str] = None
    email_subject: Optional[str] = None
    assigned_account_id: Optional[UUID] = None


class OutreachCampaignUpdate(BaseModel):
    name: Optional[str] = None
    target_industry: Optional[str] = None
    target_roles: Optional[list] = None
    status: Optional[str] = None
    auto_send: Optional[bool] = None
    email_template_prompt: Optional[str] = None
    product_context: Optional[str] = None
    email_subject: Optional[str] = None
    assigned_account_id: Optional[UUID] = None


# ── Campaign Contact ───────────────────────────────────────────────────────────

class CampaignContactOut(BaseModel):
    id: UUID
    campaign_id: UUID
    contact_id: UUID
    status: str
    ai_draft: Optional[str]
    created_at: datetime
    contact: Optional[ProspectContactOut] = None
    model_config = {"from_attributes": True}


# ── Outreach Thread & Messages ─────────────────────────────────────────────────

class OutreachMessageOut(BaseModel):
    id: UUID
    thread_id: UUID
    direction: str
    content: str
    ai_generated: bool
    sent_at: Optional[datetime]
    created_at: datetime
    model_config = {"from_attributes": True}


class OutreachThreadOut(BaseModel):
    id: UUID
    campaign_contact_id: UUID
    gmail_thread_id: Optional[str]
    ai_summary: Optional[str]
    last_message_at: Optional[datetime]
    created_at: datetime
    messages: list[OutreachMessageOut] = []
    model_config = {"from_attributes": True}


# ── Discovery ─────────────────────────────────────────────────────────────────

class DiscoverySearchRequest(BaseModel):
    industry: Optional[str] = None
    keywords: Optional[str] = None
    location: Optional[str] = None
    target_roles: list[str] = []
    company_size: Optional[str] = None
    max_results: int = 10


class DiscoverySearchResponse(BaseModel):
    companies_found: int
    contacts_found: int
    search_query: str
    companies: list[ProspectCompanyOut]
    contacts: list[ProspectContactOut]


# ── Outreach Actions ───────────────────────────────────────────────────────────

class ApproveOutreachRequest(BaseModel):
    edit_body: Optional[str] = None


class AddContactsToCampaignRequest(BaseModel):
    contact_ids: list[UUID]


class SetInterestRequest(BaseModel):
    status: str   # "interested" | "not_interested"


# ── Analytics ─────────────────────────────────────────────────────────────────

class LeadGenAnalyticsOut(BaseModel):
    total_companies: int
    total_contacts: int
    active_campaigns: int
    messages_sent: int
    replies_received: int
    interested_leads: int
    reply_rate_pct: float
    interest_rate_pct: float
    funnel: list[dict]
    top_campaigns: list[dict]
