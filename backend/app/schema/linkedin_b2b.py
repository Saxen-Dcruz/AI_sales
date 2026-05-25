"""
Pydantic schemas for LinkedIn B2B Lead Generation API

Handles request/response validation for:
- Lead discovery
- Lead qualification
- Outreach campaigns
- Conversations
- Analytics
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, EmailStr, validator
from enum import Enum


# ── Enums ──────────────────────────────────────────────────────────────────

class EmployeeRoleEnum(str, Enum):
    C_SUITE = "c_suite"
    DIRECTOR = "director"
    MANAGER = "manager"
    ENGINEER = "engineer"
    OPERATIONS = "operations"
    SALES = "sales"
    FINANCE = "finance"
    HR = "hr"
    MARKETING = "marketing"
    OTHER = "other"


class LeadStatusEnum(str, Enum):
    DISCOVERED = "discovered"
    QUALIFIED = "qualified"
    OUTREACH_QUEUED = "outreach_queued"
    MESSAGE_SENT = "message_sent"
    REPLIED = "replied"
    INTERESTED = "interested"
    REJECTED = "rejected"
    MEETING_SCHEDULED = "meeting_scheduled"


# ── Lead Discovery ─────────────────────────────────────────────────────────

class LeadDiscoveryRequest(BaseModel):
    """Request to discover leads from companies"""

    search_query: Optional[str] = Field(None, description="Free text search: 'Tata', 'manufacturing companies'")
    company_names: Optional[List[str]] = Field(None, description="Specific companies to search")
    industries: Optional[List[str]] = Field(None, description="Industries: manufacturing, logistics, software, etc.")
    locations: Optional[List[str]] = Field(None, description="Locations to filter")
    company_sizes: Optional[List[str]] = Field(None, description="Company sizes: 'Startup', '1000-5000', etc.")
    job_titles: Optional[List[str]] = Field(None, description="Target job titles")
    keywords: Optional[List[str]] = Field(None, description="Additional keywords")

    # Limits
    max_results: int = Field(100, ge=1, le=1000, description="Max employees to discover")

    # Source
    data_source: str = Field("linkedin", description="Data source: linkedin, manual, csv_upload")

    class Config:
        schema_extra = {
            "example": {
                "search_query": "Tata manufacturing",
                "industries": ["manufacturing", "logistics"],
                "locations": ["India"],
                "max_results": 100
            }
        }


class LinkedInEmployeeSchema(BaseModel):
    """Employee information from LinkedIn"""

    id: Optional[str] = Field(None, description="Employee UUID")
    company_id: Optional[str] = Field(None, description="Company UUID")
    full_name: str
    headline: Optional[str] = None
    location: Optional[str] = None
    linkedin_url: Optional[str] = None
    linkedin_id: Optional[str] = None
    role_category: EmployeeRoleEnum = EmployeeRoleEnum.OTHER
    job_title: Optional[str] = None
    department: Optional[str] = None
    email: Optional[str] = None
    email_confidence: float = Field(0.0, ge=0.0, le=1.0)
    skills: List[str] = []
    about: Optional[str] = None
    discovered_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CompanyWithEmployeesSchema(BaseModel):
    """Company with its discovered employees"""

    company_id: Optional[str] = None
    company_name: str
    website: Optional[str] = None
    industry: Optional[str] = None
    company_size: Optional[str] = None
    location: Optional[str] = None
    linkedin_url: Optional[str] = None
    employees: List[LinkedInEmployeeSchema] = []
    total_employees_discovered: int = 0

    class Config:
        schema_extra = {
            "example": {
                "company_name": "Tata Motors",
                "industry": "manufacturing",
                "company_size": "10000+",
                "employees": [
                    {
                        "full_name": "Rajesh Kumar",
                        "job_title": "Head of Logistics",
                        "role_category": "director",
                        "email": "rajesh.kumar@tatamotors.com"
                    }
                ],
                "total_employees_discovered": 1
            }
        }


# ── Lead Qualification ─────────────────────────────────────────────────────

class QualificationScoresSchema(BaseModel):
    """Breakdown of AI qualification scores"""

    overall_score: float = Field(..., ge=0, le=100, description="Overall qualification score")
    interest_probability: float = Field(..., ge=0, le=1, description="0-1 probability of interest")
    product_relevance: float = Field(..., ge=0, le=1, description="How relevant our products are")
    budget_authority: float = Field(..., ge=0, le=1, description="Likely has budget/authority")
    timing: float = Field(..., ge=0, le=1, description="Likely to buy soon")
    reasoning: str = Field(..., description="Human-readable explanation")
    factors: Dict[str, Any] = Field(default_factory=dict, description="Detailed scoring factors")


class LinkedInLeadSchema(BaseModel):
    """Qualified LinkedIn lead"""

    id: Optional[str] = None
    company_id: Optional[str] = None
    employee_id: Optional[str] = None
    employee: Optional[LinkedInEmployeeSchema] = None

    # Status
    status: LeadStatusEnum = LeadStatusEnum.DISCOVERED
    priority: str = "medium"

    # Scores
    qualification_score: float = 0.0
    interest_probability: float = 0.0
    product_relevance: float = 0.0

    # Outreach
    message_sent_at: Optional[datetime] = None
    reply_received_at: Optional[datetime] = None
    reply_count: int = 0

    # Interest & Engagement
    interested_at: Optional[datetime] = None
    meeting_scheduled: bool = False

    # Metadata
    tags: List[str] = []
    notes: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class LeadQualificationResponse(LinkedInLeadSchema):
    """Response after AI qualification"""

    qualification_reasoning: Optional[str] = None
    qualification_factors: Dict[str, Any] = {}
    qualified_at: Optional[datetime] = None


# ── Campaign Management ────────────────────────────────────────────────────

class CreateCampaignRequest(BaseModel):
    """Create a new outreach campaign"""

    name: str = Field(..., description="Campaign name")
    description: Optional[str] = None

    # Search Criteria
    search_query: Optional[str] = None
    industries: List[str] = []
    locations: List[str] = []
    company_sizes: List[str] = []
    job_titles: List[str] = []
    keywords: List[str] = []

    # Campaign Settings
    auto_message: bool = False  # Auto send to qualified leads
    auto_reply: bool = False    # Auto reply to responses
    require_approval: bool = True  # Require human approval before sending
    qualification_threshold: float = Field(70.0, ge=0, le=100)
    daily_message_limit: int = Field(50, ge=1, le=500)

    class Config:
        schema_extra = {
            "example": {
                "name": "Tata Manufacturing Outreach",
                "industries": ["manufacturing", "logistics"],
                "locations": ["India"],
                "auto_message": False,
                "require_approval": True,
                "qualification_threshold": 70.0
            }
        }


class CampaignSchema(BaseModel):
    """Campaign details"""

    id: Optional[str] = None
    name: str
    description: Optional[str] = None
    is_active: bool = True

    # Criteria
    search_query: Optional[str] = None
    industries: List[str] = []
    locations: List[str] = []
    job_titles: List[str] = []

    # Settings
    auto_message: bool = False
    auto_reply: bool = False
    require_approval: bool = True
    qualification_threshold: float = 70.0

    # Results
    total_discovered: int = 0
    total_qualified: int = 0
    total_messaged: int = 0
    total_replied: int = 0

    # Tracking
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_run_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ── Messaging ──────────────────────────────────────────────────────────────

class OutreachMessageRequest(BaseModel):
    """Request to send message to a lead"""

    linkedin_lead_id: str = Field(..., description="ID of the lead to message")
    message_content: Optional[str] = Field(None, description="Custom message (if not using template)")
    use_template: bool = True
    template_name: Optional[str] = None  # Auto-generate based on employee role + company industry
    require_approval: bool = True  # Require human approval before sending

    class Config:
        schema_extra = {
            "example": {
                "linkedin_lead_id": "uuid",
                "use_template": True,
                "require_approval": True
            }
        }


class LinkedInMessageSchema(BaseModel):
    """Message in a conversation"""

    id: Optional[str] = None
    direction: str  # "outbound" or "inbound"
    message_type: str = "text"
    content: str

    # AI Info
    ai_generated: bool = False
    ai_model: Optional[str] = None
    ai_confidence: Optional[float] = None

    # Status
    status: str = "pending"

    # Classification (for inbound)
    sentiment: Optional[str] = None
    intent: Optional[str] = None
    requires_human_review: bool = False

    # Timestamps
    created_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ConversationSchema(BaseModel):
    """Conversation thread with a lead"""

    id: Optional[str] = None
    linkedin_lead_id: str
    linkedin_conversation_id: Optional[str] = None

    # Status
    is_active: bool = True
    last_message_type: Optional[str] = None
    reply_pending: bool = False

    # Message Counts
    message_count_outbound: int = 0
    message_count_inbound: int = 0

    # Messages
    messages: List[LinkedInMessageSchema] = []

    # Topics
    topics_discussed: List[str] = []

    # Timestamps
    created_at: Optional[datetime] = None
    last_message_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ReplyHandlerRequest(BaseModel):
    """Incoming reply from LinkedIn (webhook)"""

    linkedin_conversation_id: str = Field(..., description="LinkedIn's conversation ID")
    linkedin_lead_id: str = Field(..., description="Our internal lead ID")
    message_content: str = Field(..., description="The message content from lead")
    received_at: Optional[datetime] = None

    class Config:
        schema_extra = {
            "example": {
                "linkedin_conversation_id": "some-linkedin-id",
                "linkedin_lead_id": "our-lead-uuid",
                "message_content": "Hi, can you tell me more about your pricing?"
            }
        }


# ── Analytics ──────────────────────────────────────────────────────────────

class LeadAnalyticsSchema(BaseModel):
    """Analytics for a lead"""

    linkedin_lead_id: str
    messages_sent: int = 0
    messages_received: int = 0
    response_rate: float = 0.0
    avg_response_time_hours: Optional[float] = None

    # Timeline
    first_outreach_at: Optional[datetime] = None
    first_reply_at: Optional[datetime] = None
    days_since_first_outreach: Optional[int] = None
    days_since_last_interaction: Optional[int] = None

    # Engagement
    email_opened: bool = False
    linkedin_message_viewed: bool = False
    profile_visited_us: bool = False
    content_engaged: bool = False

    # Conversion
    sql_qualified: bool = False
    demo_scheduled: bool = False
    proposal_sent: bool = False
    deal_created: bool = False

    class Config:
        from_attributes = True


class DashboardMetricsSchema(BaseModel):
    """Overall dashboard metrics"""

    total_leads_discovered: int = 0
    total_leads_qualified: int = 0
    total_messages_sent: int = 0
    total_replies_received: int = 0
    overall_reply_rate: float = 0.0

    leads_interested: int = 0
    meetings_scheduled: int = 0
    sql_qualified: int = 0
    deals_created: int = 0

    # By status
    by_status: Dict[str, int] = {}

    # By priority
    by_priority: Dict[str, int] = {}

    # Recent activity
    messages_sent_today: int = 0
    replies_received_today: int = 0

    created_at: datetime = Field(default_factory=datetime.utcnow)


class CampaignAnalyticsSchema(BaseModel):
    """Analytics for a specific campaign"""

    campaign_id: str
    campaign_name: str

    total_discovered: int
    total_qualified: int
    total_messaged: int
    total_replied: int

    reply_rate: float
    interested_count: int
    interested_rate: float

    # Top performing job titles
    top_job_titles: Dict[str, int] = {}

    # Top performing industries
    top_industries: Dict[str, int] = {}


# ── Listing & Filtering ────────────────────────────────────────────────────

class LeadFilterRequest(BaseModel):
    """Filters for querying leads"""

    status: Optional[List[str]] = None
    priority: Optional[List[str]] = None
    qualification_score_min: Optional[float] = None
    interest_probability_min: Optional[float] = None

    # Date ranges
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None

    # Lead info
    industries: Optional[List[str]] = None
    locations: Optional[List[str]] = None
    job_titles: Optional[List[str]] = None
    role_categories: Optional[List[str]] = None

    # Pagination
    page: int = Field(1, ge=1)
    limit: int = Field(20, ge=1, le=100)
    sort_by: str = Field("created_at", description="Field to sort by")
    sort_order: str = Field("desc", description="'asc' or 'desc'")


class LeadListResponse(BaseModel):
    """Paginated list of leads"""

    items: List[LinkedInLeadSchema]
    total: int
    page: int
    limit: int
    total_pages: int

    class Config:
        schema_extra = {
            "example": {
                "items": [],
                "total": 100,
                "page": 1,
                "limit": 20,
                "total_pages": 5
            }
        }


# ── Bulk Operations ────────────────────────────────────────────────────────

class BulkMessageRequest(BaseModel):
    """Send messages to multiple leads"""

    lead_ids: List[str] = Field(..., description="List of lead UUIDs")
    message_content: Optional[str] = None
    use_template: bool = True
    require_approval: bool = True


class BulkQualifyRequest(BaseModel):
    """Qualify multiple leads with AI"""

    lead_ids: List[str] = Field(..., description="List of lead UUIDs to qualify")
    requalify_existing: bool = False  # Re-qualify even if already qualified
