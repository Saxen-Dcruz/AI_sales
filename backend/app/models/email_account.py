from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, String, Text, JSON
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from app.database.core import Base
from app.core.utils import new_uuid


class EmailAccount(Base):
    __tablename__ = "email_accounts"

    id            = Column(PGUUID(as_uuid=True), primary_key=True, default=new_uuid)
    email_address = Column(String, unique=True, nullable=False, index=True)
    display_name  = Column(String, nullable=True)
    token_data    = Column(Text, nullable=False)          # base64-pickled Google OAuth2 credentials
    is_active     = Column(Boolean, default=True, nullable=False)
    is_primary    = Column(Boolean, default=False, nullable=False)
    # When False, all Sales emails for this account go to draft_ready instead of auto-sending
    auto_send_enabled = Column(Boolean, default=True, nullable=False)
    scopes        = Column(JSON, nullable=True)
    added_by      = Column(String, nullable=True)
    created_at    = Column(String, default=lambda: datetime.now(timezone.utc).isoformat())
    updated_at    = Column(String, default=lambda: datetime.now(timezone.utc).isoformat(),
                           onupdate=lambda: datetime.now(timezone.utc).isoformat())
