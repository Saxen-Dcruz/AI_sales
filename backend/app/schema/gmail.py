from datetime import datetime
from typing import Optional, Any, Union
from uuid import UUID
from pydantic import BaseModel, field_validator
from app.models.communication import EmailLabel, EmailStatus


class GapItem(BaseModel):
    question: str
    topic: str           # warranty | pricing | compatibility | availability | technical | general
    product_name: Optional[str]
    product_id: Optional[str]
    resolved: bool = False
    answer: Optional[str] = None
    resolved_by: Optional[str] = None


class EmailOut(BaseModel):
    id: UUID
    gmail_message_id: str
    gmail_thread_id: Optional[str]
    lead_id: Optional[UUID]
    direction: str
    sender: str
    recipients: list[str]
    subject: Optional[str]
    body_text: Optional[str]
    received_at: datetime
    label: EmailLabel
    status: EmailStatus
    classifier_reasoning: Optional[str]
    classifier_confidence: Optional[str]
    transactional_type: Optional[str]
    transactional_data: Optional[dict[str, Any]]
    ai_draft: Optional[str]
    gmail_draft_id: Optional[str]
    followup_gaps: Optional[list[Union[GapItem, str]]]
    competitor_mention: Optional[str]
    detected_product_id: Optional[str] = None
    detected_product_name: Optional[str] = None
    needs_human: bool
    resolved_by: Optional[str]
    resolved_at: Optional[datetime]
    account_id: Optional[UUID] = None
    account_email: Optional[str] = None
    updated_at: Optional[datetime] = None
    created_at: datetime
    thread_count: int = 1

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
            elif isinstance(item, dict):
                # Backfill missing fields from older gap rows that predate the structured schema
                result.append(GapItem(
                    question=item.get("question", ""),
                    topic=item.get("topic", "general"),
                    product_name=item.get("product_name"),
                    product_id=item.get("product_id"),
                    resolved=item.get("resolved", False),
                    answer=item.get("answer"),
                    resolved_by=item.get("resolved_by"),
                ))
            else:
                result.append(item)
        return result


class EmailListResponse(BaseModel):
    items: list[EmailOut]
    total: int
    page: int
    limit: int


class GapNotificationOut(BaseModel):
    email_id: UUID
    gmail_draft_id: Optional[str]
    customer_email: str
    subject: Optional[str]
    received_at: datetime
    gaps: list[GapItem]

    model_config = {"from_attributes": True}


class GapNotificationListResponse(BaseModel):
    items: list[GapNotificationOut]
    total: int


class GapResolveRequest(BaseModel):
    gap_index: int
    answer: str
    category: Optional[str] = None     # overrides inferred topic if provided
    product_id: Optional[str] = None   # overrides gap's product_id if provided


class EmailSLAAnalytics(BaseModel):
    total_emails: int
    total_inbound: int
    total_outbound: int
    # Breakdown to make "All" vs per-account transparent
    total_attributed: int = 0   # emails linked to an active account
    total_legacy: int = 0       # emails with no account info (pre-multi-account)
    total_sales_emails: int
    auto_sent: int
    drafted_for_review: int
    pending_human: int
    auto_sent_rate_pct: float
    avg_reply_minutes: float
    sla_breached: int
    sla_met: int = 0
    competitor_mentions: int
    grievance_total: int = 0
    grievance_resolved: int = 0
    grievance_pending: int = 0
    support_total: int = 0
    support_resolved: int = 0
    support_pending: int = 0
    daily_stats: list = []
    by_label: dict
    by_status: dict
    by_direction: dict
    by_account: dict = {}  # gmail_address → count
    by_owner: dict = {}   # super-admin only: user_email → {gmail_accounts: [...], email_count: int}
    # Product & revenue analytics
    by_product: dict = {}           # product_name → inquiry count
    top_products_purchased: list = []  # [{name, inquiries, converted, conversion_pct}]
    revenue_total: float = 0.0      # sum of amounts from transactional order/invoice emails
    order_count: int = 0            # confirmed orders / order_confirmation emails
    po_count: int = 0               # PO-related transactional emails
    conversion_rate_pct: float = 0.0  # Sales replied / total Sales * 100
    lead_pipeline: dict = {}        # interest_level → count (from leads linked to emails)
    by_company_source: dict = {}    # source name → email count (IndiaMart, TradeIndia, direct, etc.)
    total_volume_breakdown: dict = {}  # inbound/outbound/sales/support/grievance counts
    product_source_rows: list = []  # [{product, source, count, converted}] — product × source matrix
    product_company_rows: list = []  # [{company, source, email, products:[{name,count}]}] — company details


class GenerateDraftRequest(BaseModel):
    to: str
    subject: str
    body: str  # customer's message / context for the AI to reply to


class GenerateDraftResponse(BaseModel):
    draft: str


class SendEmailRequest(BaseModel):
    to: str
    subject: str
    body: str
    thread_id: Optional[str] = None
    # Optional: reply in-thread from the account that received the original email.
    account_id: Optional[UUID] = None
    reply_to_email_id: Optional[UUID] = None  # the inbound email being replied to


class ResolveEmailRequest(BaseModel):
    resolved_by: str
    note: Optional[str] = None


class ApproveDraftRequest(BaseModel):
    edit_body: Optional[str] = None  # if set, replaces the ai_draft before sending


class SequenceStepCreate(BaseModel):
    day_offset: int
    subject: str
    body: str


class SequenceCreate(BaseModel):
    lead_id: UUID
    name: str
    steps: list[SequenceStepCreate]


class SequenceStepOut(BaseModel):
    id: UUID
    day_offset: int
    subject: str
    status: str
    send_at: datetime
    sent_at: Optional[datetime]

    model_config = {"from_attributes": True}


class SequenceOut(BaseModel):
    id: UUID
    lead_id: UUID
    name: str
    status: str
    created_by: Optional[str]
    created_at: datetime
    steps: list[SequenceStepOut]

    model_config = {"from_attributes": True}
