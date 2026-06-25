from sqlalchemy import Column, String, Text, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from datetime import datetime, timezone
from app.database.core import Base
from app.core.utils import new_uuid


class EmailTemplate(Base):
    __tablename__ = "email_templates"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=new_uuid)
    owner_id = Column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
                      nullable=True, index=True)

    name = Column(String, nullable=False)
    subject = Column(String, nullable=False)
    body = Column(Text, nullable=False)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))
