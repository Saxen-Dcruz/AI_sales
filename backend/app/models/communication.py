from sqlalchemy import JSON, Column, Integer, String, Text, ForeignKey, DateTime, Boolean, Enum
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import enum
from app.database.core import Base
from app.core.utils import new_uuid


class EmailLabel(str, enum.Enum):
    SALES = "Sales"
    SUPPORT = "Support"
    GRIEVANCE = "Grievance"
    TRANSACTIONAL = "Transactional"
    PROMOTIONAL = "Promotional"
    PERSONAL = "Personal"
    UNCLASSIFIED = "Unclassified"


class EmailStatus(str, enum.Enum):
    NEW = "new"
    CLASSIFIED = "classified"
    DRAFT_READY = "draft_ready"       # AI drafted a reply, awaiting human approval
    PENDING_HUMAN = "pending_human"   # Support/Grievance — flagged for human
    REPLIED = "replied"
    ARCHIVED = "archived"
    IGNORED = "ignored"


class Email(Base):
    __tablename__ = "emails"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=new_uuid)
    gmail_message_id = Column(String, unique=True, index=True, nullable=False)
    gmail_thread_id = Column(String, index=True, nullable=True)

    lead_id = Column(PGUUID(as_uuid=True), ForeignKey("leads.id", ondelete="SET NULL"), nullable=True, index=True)

    direction = Column(String, nullable=False)          # "inbound" | "outbound"
    sender = Column(String, nullable=False)
    recipients = Column(JSON, nullable=False)           # list of email addresses
    subject = Column(String, nullable=True)
    body_text = Column(Text, nullable=True)
    body_html = Column(Text, nullable=True)
    received_at = Column(DateTime(timezone=True), nullable=False)

    label = Column(Enum(EmailLabel), default=EmailLabel.UNCLASSIFIED, index=True)
    status = Column(Enum(EmailStatus), default=EmailStatus.NEW, index=True)

    classifier_reasoning = Column(Text, nullable=True)
    classifier_confidence = Column(String, nullable=True)

    # Transactional email parsed fields
    transactional_type = Column(String, nullable=True)  # invoice | receipt | order | shipping | account
    transactional_data = Column(JSON, nullable=True)    # extracted amount, ref number, etc.

    # AI draft reply (for Sales emails)
    ai_draft = Column(Text, nullable=True)
    gmail_draft_id = Column(String, nullable=True)      # Gmail draft ID if saved to Gmail Drafts
    followup_gaps = Column(JSON, nullable=True)         # list of follow-up items RAG couldn't answer

    competitor_mention = Column(String, nullable=True)   # competitor name if detected in email

    needs_human = Column(Boolean, default=False, index=True)
    resolved_by = Column(String, nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    # Multi-account Gmail — which account received/sent this email
    account_id    = Column(PGUUID(as_uuid=True), ForeignKey("email_accounts.id", ondelete="SET NULL"), nullable=True, index=True)
    account_email = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    lead = relationship("Lead", backref="emails")


class Interaction(Base):
    __tablename__ = "interactions"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=new_uuid)
    lead_id = Column(PGUUID(as_uuid=True), ForeignKey("leads.id"))

    channel = Column(String)
    direction = Column(String)
    raw_content = Column(Text, nullable=True)

    ai_summary = Column(Text, nullable=True)
    interaction_sentiment = Column(String, nullable=True)

    duration_seconds = Column(Integer, default=0)
    recording_url = Column(String, nullable=True)
    transcript_url = Column(String, nullable=True)

    extracted_features = Column(JSON, nullable=True)

    timestamp = Column(DateTime, default=datetime.utcnow)

    lead = relationship("Lead", back_populates="interactions")


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=new_uuid)
    session_id = Column(String, unique=True, index=True)

    lead_id = Column(PGUUID(as_uuid=True), ForeignKey("leads.id"), nullable=True)

    started_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)

    chat_summary = Column(Text, nullable=True)
    user_intent = Column(String, nullable=True)
    is_converted = Column(Boolean, default=False)

    lead = relationship("Lead", back_populates="chat_sessions")
