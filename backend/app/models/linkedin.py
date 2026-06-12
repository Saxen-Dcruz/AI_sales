from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship
from app.database.core import Base
from app.core.utils import new_uuid


class LinkedInOAuthAccount(Base):
    """Stores a user's LinkedIn OAuth connection (access token + profile info)."""
    __tablename__ = "linkedin_oauth_accounts"

    id                = Column(PGUUID(as_uuid=True), primary_key=True, default=new_uuid)
    linkedin_member_id = Column(String, unique=True, nullable=False, index=True)
    name              = Column(String, nullable=True)
    email             = Column(String, nullable=True)
    picture_url       = Column(String, nullable=True)
    access_token      = Column(Text, nullable=False)
    # Stored LinkedIn account password used to auto-refresh the session when the
    # OAuth access token expires (no headless re-login flow otherwise).
    li_password       = Column(Text, nullable=True)
    is_active         = Column(Boolean, default=True, nullable=False)
    connected_at      = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at        = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                               onupdate=lambda: datetime.now(timezone.utc))


class LinkedInOutreach(Base):
    __tablename__ = "linkedin_outreach"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=new_uuid)
    lead_id    = Column(PGUUID(as_uuid=True), ForeignKey("leads.id",    ondelete="SET NULL"), nullable=True, index=True)
    company_id = Column(PGUUID(as_uuid=True), ForeignKey("companies.id", ondelete="SET NULL"), nullable=True)

    # Profile snapshot at discovery time
    linkedin_url   = Column(String, unique=True, nullable=True)
    full_name      = Column(String, nullable=True)
    headline       = Column(String, nullable=True)
    location       = Column(String, nullable=True)
    company_name   = Column(String, nullable=True)
    role_category  = Column(String, nullable=True)   # c_suite | cto | operations | procurement | engineering
    industry_tag   = Column(String, nullable=True)
    city_tag       = Column(String, nullable=True)

    # Connection
    connection_status   = Column(String, default="not_sent")   # not_sent | pending | connected | rejected | withdrawn
    connection_sent_at  = Column(DateTime(timezone=True), nullable=True)

    # Message
    message_status       = Column(String, default="not_sent")  # not_sent | sent | replied | bounced
    message_sent_at      = Column(DateTime(timezone=True), nullable=True)
    message_body         = Column(Text, nullable=True)
    message_template_key = Column(String, nullable=True)
    reply_received_at    = Column(DateTime(timezone=True), nullable=True)
    reply_preview        = Column(String, nullable=True)

    source     = Column(String, default="linkedin_scrape")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    lead    = relationship("Lead",    foreign_keys=[lead_id])
    company = relationship("Company", foreign_keys=[company_id])
