from datetime import datetime
from typing import Optional, Any
from uuid import UUID
from pydantic import BaseModel
from app.models.communication import EmailLabel, EmailStatus


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
    needs_human: bool
    resolved_by: Optional[str]
    resolved_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


class EmailListResponse(BaseModel):
    items: list[EmailOut]
    total: int
    page: int
    limit: int


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
