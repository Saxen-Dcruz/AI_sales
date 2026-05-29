"""
LinkedIn B2B Lead Generation Models

Handles:
- Employee discovery from companies
- Lead qualification and scoring
- Message threading and conversation history
- Analytics and tracking
"""

from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, Float, Integer, Boolean, DateTime, ForeignKey, Enum, JSON
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import relationship
import enum

from app.database.core import Base
from app.core.utils import new_uuid


# ── Enums ──────────────────────────────────────────────────────────────────

class LinkedInLeadStatus(str, enum.Enum):
    """Lead status through the pipeline"""
    DISCOVERED = "discovered"        # Initial discovery
    QUALIFIED = "qualified"          # AI qualified as potential buyer
    OUTREACH_QUEUED = "outreach_queued"  # Message queued to send
    MESSAGE_SENT = "message_sent"    # Message sent on LinkedIn
    REPLIED = "replied"              # Lead replied to message
    INTERESTED = "interested"        # AI determined interested
    REJECTED = "rejected"            # Not interested / unsubscribe
    MEETING_SCHEDULED = "meeting_scheduled"


class LinkedInEmployeeRole(str, enum.Enum):
    """Employee role categories for targeting"""
    C_SUITE = "c_suite"              # CEO, CFO, CTO, COO
    DIRECTOR = "director"            # Director, VP
    MANAGER = "manager"              # Manager, Senior Manager
    ENGINEER = "engineer"            # Engineering roles
    OPERATIONS = "operations"        # Operations, Supply Chain, Procurement
    SALES = "sales"                  # Sales, Business Development
    FINANCE = "finance"              # Finance, Accounting
    HR = "hr"                        # HR, Talent
    MARKETING = "marketing"          # Marketing, Communications
    OTHER = "other"                  # Other roles


# ── Models ─────────────────────────────────────────────────────────────────

class LinkedInEmployee(Base):
    """Employee data collected from LinkedIn"""
    __tablename__ = "linkedin_employees"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=new_uuid)
    company_id = Column(PGUUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)

    # Profile Info
    full_name = Column(String(255), nullable=False, index=True)
    headline = Column(String(500), nullable=True)  # Current role/title
    location = Column(String(255), nullable=True)
    linkedin_url = Column(String(500), nullable=True, unique=True, index=True)
    linkedin_id = Column(String(100), nullable=True, unique=True, index=True)  # LinkedIn's numeric ID

    # Role Classification
    role_category = Column(Enum(LinkedInEmployeeRole), default=LinkedInEmployeeRole.OTHER, index=True)
    job_title = Column(String(255), nullable=True)
    department = Column(String(100), nullable=True)
    seniority_level = Column(String(50), nullable=True)  # Entry, Associate, Senior, Lead, Manager, Executive

    # Contact & Business Email
    email = Column(String(255), nullable=True, index=True)
    email_confidence = Column(Float, default=0.0)  # 0.0-1.0 confidence that email is accurate
    phone = Column(String(20), nullable=True)

    # Profile Summary
    about = Column(Text, nullable=True)  # Short bio from LinkedIn
    skills = Column(JSONB, default=[])  # List of skills from LinkedIn

    # Sourcing Info
    source = Column(String(50), default="linkedin_scrape")  # Where we got this data
    source_metadata = Column(JSONB, nullable=True)  # Extra data from scrape (engagement metrics, etc.)

    # Tracking
    discovered_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    company = relationship("Company", foreign_keys=[company_id])
    leads = relationship("LinkedInLead", back_populates="employee", cascade="all, delete-orphan")



class LinkedInLead(Base):
    """Qualified leads from LinkedIn employee discovery"""
    __tablename__ = "linkedin_leads"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=new_uuid)
    company_id = Column(PGUUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    employee_id = Column(PGUUID(as_uuid=True), ForeignKey("linkedin_employees.id", ondelete="CASCADE"), nullable=False, index=True)
    lead_id = Column(PGUUID(as_uuid=True), ForeignKey("leads.id", ondelete="SET NULL"), nullable=True, index=True)  # Link to main Lead table

    # AI Qualification Scores
    qualification_score = Column(Float, default=0.0)  # 0-100 overall fit
    interest_probability = Column(Float, default=0.0)  # 0-1.0 probability of interest
    product_relevance = Column(Float, default=0.0)    # 0-1.0 relevance to our products
    budget_authority = Column(Float, default=0.0)     # 0-1.0 likely has budget/authority
    timing = Column(Float, default=0.0)               # 0-1.0 likely to buy soon

    # Qualification Details
    qualification_reasoning = Column(Text, nullable=True)  # Why AI qualified this lead
    qualification_factors = Column(JSONB, default={})      # Breakdown of scoring factors
    qualified_at = Column(DateTime(timezone=True), nullable=True)
    qualified_by = Column(String(50), default="ai")  # "ai" or "manual"

    # Pipeline Status
    status = Column(Enum(LinkedInLeadStatus), default=LinkedInLeadStatus.DISCOVERED, index=True)
    priority = Column(String(20), default="medium")  # "high", "medium", "low"

    # Outreach Tracking
    message_sent_at = Column(DateTime(timezone=True), nullable=True)
    message_attempt_count = Column(Integer, default=0)
    last_message_content = Column(Text, nullable=True)

    reply_received_at = Column(DateTime(timezone=True), nullable=True)
    reply_count = Column(Integer, default=0)
    last_reply_preview = Column(String(500), nullable=True)

    # Interest & Engagement
    interested_at = Column(DateTime(timezone=True), nullable=True)
    interest_signals = Column(JSONB, default=[])  # List of signals that showed interest

    # Meeting
    meeting_scheduled = Column(Boolean, default=False)
    meeting_date = Column(DateTime(timezone=True), nullable=True)

    # Tags & Notes
    tags = Column(JSONB, default=[])  # Custom tags for organization
    notes = Column(Text, nullable=True)  # Human notes

    # Tracking
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    last_action_at = Column(DateTime(timezone=True), nullable=True)  # Last interaction with this lead

    # Relationships
    company = relationship("Company", foreign_keys=[company_id])
    employee = relationship("LinkedInEmployee", back_populates="leads", foreign_keys=[employee_id])
    lead = relationship("Lead", foreign_keys=[lead_id])  # Link to main Lead table
    conversations = relationship("LinkedInConversation", back_populates="linkedin_lead", cascade="all, delete-orphan")
    analytics = relationship("LinkedInLeadAnalytics", back_populates="linkedin_lead", uselist=False, cascade="all, delete-orphan")


class LinkedInConversation(Base):
    """Message thread with a lead (same pattern as email threading)"""
    __tablename__ = "linkedin_conversations"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=new_uuid)
    linkedin_lead_id = Column(PGUUID(as_uuid=True), ForeignKey("linkedin_leads.id", ondelete="CASCADE"), nullable=False, index=True)

    # Thread Tracking
    linkedin_conversation_id = Column(String(255), nullable=True, unique=True, index=True)  # LinkedIn's thread ID
    thread_id = Column(String(255), nullable=True)  # Internal thread ID for tracking

    # Conversation Context (for AI continuity)
    conversation_context = Column(JSONB, default={})  # Structured context about the conversation
    ai_memory = Column(Text, nullable=True)          # Summary/memory for Claude to use
    full_history = Column(JSONB, default=[])         # Full message history for context

    # Status
    is_active = Column(Boolean, default=True, index=True)
    last_message_type = Column(String(20))  # "outbound" or "inbound"
    last_message_at = Column(DateTime(timezone=True), nullable=True, index=True)
    reply_pending = Column(Boolean, default=False)   # Waiting for lead to reply

    # Message Counts
    message_count_outbound = Column(Integer, default=0)
    message_count_inbound = Column(Integer, default=0)

    # Topics Discussed
    topics_discussed = Column(JSONB, default=[])  # ["pricing", "features", "timeline", etc.]

    # Tracking
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    closed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    linkedin_lead = relationship("LinkedInLead", back_populates="conversations", foreign_keys=[linkedin_lead_id])
    messages = relationship("LinkedInMessage", back_populates="conversation", cascade="all, delete-orphan")


class LinkedInMessage(Base):
    """Individual message in a conversation"""
    __tablename__ = "linkedin_messages"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=new_uuid)
    conversation_id = Column(PGUUID(as_uuid=True), ForeignKey("linkedin_conversations.id", ondelete="CASCADE"), nullable=False, index=True)

    # Message Content
    direction = Column(String(20), nullable=False)  # "outbound" (from us) or "inbound" (from lead)
    message_type = Column(String(50), default="text")  # "text", "connection_request", etc.
    content = Column(Text, nullable=False)

    # LinkedIn IDs
    linkedin_message_id = Column(String(255), nullable=True, unique=True, index=True)

    # AI Generation Info
    ai_generated = Column(Boolean, default=False)
    ai_model = Column(String(50), nullable=True)  # "claude-3.5-sonnet", etc.
    ai_prompt_used = Column(Text, nullable=True)  # For debugging
    ai_confidence = Column(Float, nullable=True)  # How confident is the AI response

    # Status
    status = Column(String(50), default="pending")  # "pending", "sent", "delivered", "failed"
    send_attempt_count = Column(Integer, default=0)
    last_send_attempt_at = Column(DateTime(timezone=True), nullable=True)

    # Sentiment & Classification (for inbound messages)
    sentiment = Column(String(50), nullable=True)  # "positive", "neutral", "negative"
    intent = Column(String(100), nullable=True)    # "question", "objection", "interest", "rejection", etc.
    requires_human_review = Column(Boolean, default=False)

    # Tracking
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    received_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    conversation = relationship("LinkedInConversation", back_populates="messages", foreign_keys=[conversation_id])


class LinkedInLeadAnalytics(Base):
    """Analytics tracking for each lead"""
    __tablename__ = "linkedin_lead_analytics"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=new_uuid)
    linkedin_lead_id = Column(PGUUID(as_uuid=True), ForeignKey("linkedin_leads.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)

    # Engagement Metrics
    messages_sent = Column(Integer, default=0)
    messages_received = Column(Integer, default=0)
    response_rate = Column(Float, default=0.0)  # 0-1.0
    avg_response_time_hours = Column(Float, nullable=True)

    # Interaction Timeline
    first_outreach_at = Column(DateTime(timezone=True), nullable=True)
    first_reply_at = Column(DateTime(timezone=True), nullable=True)
    most_recent_interaction_at = Column(DateTime(timezone=True), nullable=True)
    days_since_first_outreach = Column(Integer, nullable=True)
    days_since_last_interaction = Column(Integer, nullable=True)

    # Engagement Signals
    email_opened = Column(Boolean, default=False)
    linkedin_message_viewed = Column(Boolean, default=False)
    profile_visited_us = Column(Boolean, default=False)
    content_engaged = Column(Boolean, default=False)

    # Conversion Metrics
    sql_qualified = Column(Boolean, default=False)  # Sales Qualified Lead
    demo_scheduled = Column(Boolean, default=False)
    proposal_sent = Column(Boolean, default=False)
    deal_created = Column(Boolean, default=False)

    # Tracking
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    linkedin_lead = relationship("LinkedInLead", back_populates="analytics", foreign_keys=[linkedin_lead_id])


class LinkedInSearchCampaign(Base):
    """Track search campaigns for lead discovery"""
    __tablename__ = "linkedin_search_campaigns"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=new_uuid)

    # Campaign Info
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Search Criteria
    search_query = Column(String(500), nullable=True)  # Free-text search: "Tata", "manufacturing companies", etc.
    industries = Column(JSONB, default=[])  # Industry filters
    locations = Column(JSONB, default=[])   # Location filters
    company_sizes = Column(JSONB, default=[])  # Company size filters
    job_titles = Column(JSONB, default=[])  # Target job titles/roles
    keywords = Column(JSONB, default=[])    # Additional keywords

    # Campaign Configuration
    auto_message = Column(Boolean, default=False)  # Auto-send messages to qualified leads
    auto_reply = Column(Boolean, default=False)    # Auto-reply to responses
    require_approval = Column(Boolean, default=True)  # Require human approval before sending

    # AI Configuration
    qualification_threshold = Column(Float, default=70.0)  # Min score (0-100) to qualify
    use_ai_for_qualification = Column(Boolean, default=True)
    use_ai_for_messaging = Column(Boolean, default=True)

    # Results
    total_discovered = Column(Integer, default=0)
    total_qualified = Column(Integer, default=0)
    total_messaged = Column(Integer, default=0)
    total_replied = Column(Integer, default=0)

    # Rate Limiting
    daily_message_limit = Column(Integer, default=50)  # Max messages per day
    messages_sent_today = Column(Integer, default=0)

    # Status
    is_active = Column(Boolean, default=True, index=True)

    # Tracking
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
