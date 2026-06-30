from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text, JSON
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from app.database.core import Base
from app.core.utils import new_uuid


class EmailAccount(Base):
    __tablename__ = "email_accounts"

    id            = Column(PGUUID(as_uuid=True), primary_key=True, default=new_uuid)
    # RBAC owner — which app user "owns" this Gmail account. Regular users only see
    # accounts/emails they own; is_superuser sees all. Enforced NOT NULL (migration 022).
    owner_id      = Column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    email_address = Column(String, unique=True, nullable=False, index=True)
    display_name  = Column(String, nullable=True)
    token_data    = Column(Text, nullable=False)          # base64-pickled Google OAuth2 credentials
    is_active     = Column(Boolean, default=True, nullable=False)
    is_primary    = Column(Boolean, default=False, nullable=False)
    # When False, all Sales emails for this account go to draft_ready instead of auto-sending
    auto_send_enabled = Column(Boolean, default=True, nullable=False)
    scopes        = Column(JSON, nullable=True)
    added_by      = Column(String, nullable=True)
    # Gmail Pub/Sub watch state (migration 025)
    watch_history_id = Column(String, nullable=True)          # historyId from last users.watch()
    watch_expiry     = Column(DateTime(timezone=True), nullable=True)  # watch expiry (7 days)
    created_at    = Column(String, default=lambda: datetime.now(timezone.utc).isoformat())
    updated_at    = Column(String, default=lambda: datetime.now(timezone.utc).isoformat(),
                           onupdate=lambda: datetime.now(timezone.utc).isoformat())
