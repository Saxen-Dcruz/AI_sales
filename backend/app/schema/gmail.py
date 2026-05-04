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
    needs_human: bool
    resolved_by: Optional[str]
    resolved_at: Optional[datetime]
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
    category: Optional[str] = None   # overrides inferred topic if provided


class EmailSLAAnalytics(BaseModel):
    total_sales_emails: int
    auto_sent: int                 # replied without human touch
    drafted_for_review: int        # had gaps, sent after saving
    pending_human: int             # support/grievance awaiting resolution
    auto_sent_rate_pct: float
    avg_reply_minutes: float       # avg time from received_at to replied
    sla_breached: int              # Sales emails not replied within 2 hours
    competitor_mentions: int       # emails where a competitor was mentioned
    by_label: dict                 # count per EmailLabel


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
