import enum
from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, Enum, ForeignKey, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from app.database.core import Base
from app.core.utils import new_uuid


class WATemplateStatus(str, enum.Enum):
    PENDING   = "PENDING"
    APPROVED  = "APPROVED"
    REJECTED  = "REJECTED"
    PAUSED    = "PAUSED"
    DISABLED  = "DISABLED"
    IN_APPEAL = "IN_APPEAL"


class WATemplateCategory(str, enum.Enum):
    MARKETING      = "MARKETING"
    UTILITY        = "UTILITY"
    AUTHENTICATION = "AUTHENTICATION"


class WhatsAppTemplate(Base):
    __tablename__ = "whatsapp_templates"

    id               = Column(PGUUID(as_uuid=True), primary_key=True, default=new_uuid)
    owner_id         = Column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    waba_id          = Column(String, nullable=False, index=True)
    account_id       = Column(PGUUID(as_uuid=True), ForeignKey("whatsapp_accounts.id", ondelete="SET NULL"), nullable=True)

    meta_template_id = Column(String, nullable=True)
    name             = Column(String, nullable=False)
    language         = Column(String, nullable=False, default="en")
    category         = Column(Enum(WATemplateCategory), nullable=False, default=WATemplateCategory.UTILITY)
    status           = Column(Enum(WATemplateStatus),   nullable=False, default=WATemplateStatus.PENDING)
    rejection_reason = Column(Text, nullable=True)

    components       = Column(JSON, nullable=False)     # component array as submitted to Meta

    created_at       = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at       = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                              onupdate=lambda: datetime.now(timezone.utc))
