from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from app.database.core import Base
from app.core.utils import new_uuid


class WhatsAppAccount(Base):
    __tablename__ = "whatsapp_accounts"

    id               = Column(PGUUID(as_uuid=True), primary_key=True, default=new_uuid)
    owner_id         = Column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)

    # Meta Cloud API credentials
    phone_number_id  = Column(String, nullable=False, unique=True, index=True)  # Meta phone number ID
    waba_id          = Column(String, nullable=False)                            # WhatsApp Business Account ID
    access_token     = Column(Text, nullable=False)                              # Permanent system-user token
    verify_token     = Column(String, nullable=False)                            # Webhook verify token (user-set)

    # Display fields
    display_phone    = Column(String, nullable=False)    # e.g. "+919876543210"
    display_name     = Column(String, nullable=True)     # e.g. "RDL Technologies Sales"

    is_active        = Column(Boolean, default=True, nullable=False)
    is_primary       = Column(Boolean, default=False, nullable=False)
    auto_send        = Column(Boolean, default=False, nullable=False)  # default OFF — require human approval

    created_at       = Column(String, default=lambda: datetime.now(timezone.utc).isoformat())
    updated_at       = Column(String, default=lambda: datetime.now(timezone.utc).isoformat(),
                              onupdate=lambda: datetime.now(timezone.utc).isoformat())
