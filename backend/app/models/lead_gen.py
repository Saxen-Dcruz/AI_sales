from datetime import datetime, timezone
from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship
from app.database.core import Base
from app.core.utils import new_uuid


class ProspectCompany(Base):
    __tablename__ = "prospect_companies"

    id           = Column(PGUUID(as_uuid=True), primary_key=True, default=new_uuid)
    name         = Column(String, nullable=False, index=True)
    industry     = Column(String, nullable=True, index=True)
    website      = Column(String, nullable=True)
    location     = Column(String, nullable=True)
    company_size = Column(String, nullable=True)   # "1-10", "11-50", "51-200", "201-500", "500+"
    linkedin_url = Column(String, nullable=True)
    description  = Column(Text, nullable=True)
    technologies = Column(JSON, nullable=True)      # list of strings
    source       = Column(String, default="serpapi")

    ai_score           = Column(Integer, nullable=True)   # 0-100
    ai_score_reasoning = Column(Text, nullable=True)
    interest_level     = Column(String, nullable=True)    # "hot" | "warm" | "cold"

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    contacts = relationship("ProspectContact", back_populates="company", cascade="all, delete-orphan")


class ProspectContact(Base):
    __tablename__ = "prospect_contacts"

    id           = Column(PGUUID(as_uuid=True), primary_key=True, default=new_uuid)
    company_id   = Column(PGUUID(as_uuid=True), ForeignKey("prospect_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    name         = Column(String, nullable=False)
    email        = Column(String, nullable=True, index=True)
    job_title    = Column(String, nullable=True)
    linkedin_url = Column(String, nullable=True)
    created_at   = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    company  = relationship("ProspectCompany", back_populates="contacts")
    campaign_contacts = relationship("CampaignContact", back_populates="contact", cascade="all, delete-orphan")


class OutreachCampaign(Base):
    __tablename__ = "outreach_campaigns"

    id                    = Column(PGUUID(as_uuid=True), primary_key=True, default=new_uuid)
    name                  = Column(String, nullable=False)
    target_industry       = Column(String, nullable=True)
    target_roles          = Column(JSON, nullable=True)          # list of role strings
    status                = Column(String, default="draft")      # draft | active | paused | completed
    auto_send             = Column(Boolean, default=False)
    email_template_prompt = Column(Text, nullable=True)
    product_context       = Column(Text, nullable=True)
    email_subject         = Column(String, nullable=True)
    assigned_account_id   = Column(PGUUID(as_uuid=True), ForeignKey("email_accounts.id", ondelete="SET NULL"), nullable=True)
    created_at            = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at            = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    contacts = relationship("CampaignContact", back_populates="campaign", cascade="all, delete-orphan")


class CampaignContact(Base):
    __tablename__ = "campaign_contacts"

    id          = Column(PGUUID(as_uuid=True), primary_key=True, default=new_uuid)
    campaign_id = Column(PGUUID(as_uuid=True), ForeignKey("outreach_campaigns.id", ondelete="CASCADE"), nullable=False, index=True)
    contact_id  = Column(PGUUID(as_uuid=True), ForeignKey("prospect_contacts.id", ondelete="CASCADE"), nullable=False, index=True)
    status      = Column(String, default="pending", index=True)  # pending | approved | sent | replied | interested | not_interested
    ai_draft    = Column(Text, nullable=True)                    # AI-generated outreach message
    created_at  = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (UniqueConstraint("campaign_id", "contact_id", name="uq_campaign_contact"),)

    campaign = relationship("OutreachCampaign", back_populates="contacts")
    contact  = relationship("ProspectContact", back_populates="campaign_contacts")
    threads  = relationship("OutreachThread", back_populates="campaign_contact", cascade="all, delete-orphan")


class OutreachThread(Base):
    __tablename__ = "outreach_threads"

    id                  = Column(PGUUID(as_uuid=True), primary_key=True, default=new_uuid)
    campaign_contact_id = Column(PGUUID(as_uuid=True), ForeignKey("campaign_contacts.id", ondelete="CASCADE"), nullable=False, index=True)
    gmail_thread_id     = Column(String, nullable=True, index=True)
    rfc_message_id      = Column(String, nullable=True)   # last sent message RFC ID for reply threading
    ai_summary          = Column(Text, nullable=True)
    last_message_at     = Column(DateTime(timezone=True), nullable=True)
    created_at          = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    campaign_contact = relationship("CampaignContact", back_populates="threads")
    messages = relationship("OutreachMessage", back_populates="thread", cascade="all, delete-orphan", order_by="OutreachMessage.created_at")


class OutreachMessage(Base):
    __tablename__ = "outreach_messages"

    id              = Column(PGUUID(as_uuid=True), primary_key=True, default=new_uuid)
    thread_id       = Column(PGUUID(as_uuid=True), ForeignKey("outreach_threads.id", ondelete="CASCADE"), nullable=False, index=True)
    direction       = Column(String, nullable=False)   # outbound | inbound
    content         = Column(Text, nullable=False)
    ai_generated    = Column(Boolean, default=False)
    gmail_message_id = Column(String, nullable=True)
    sent_at         = Column(DateTime(timezone=True), nullable=True)
    created_at      = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    thread = relationship("OutreachThread", back_populates="messages")
