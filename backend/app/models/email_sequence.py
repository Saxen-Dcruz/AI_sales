from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Text, Boolean, DateTime, Enum, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship
import enum
from app.database.core import Base
from app.core.utils import new_uuid


class SequenceStatus(str, enum.Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class StepStatus(str, enum.Enum):
    PENDING = "pending"
    SENT = "sent"
    SKIPPED = "skipped"


class EmailSequence(Base):
    __tablename__ = "email_sequences"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=new_uuid)
    lead_id = Column(PGUUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    status = Column(Enum(SequenceStatus), default=SequenceStatus.ACTIVE, index=True)
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    steps = relationship("EmailSequenceStep", back_populates="sequence", cascade="all, delete-orphan", order_by="EmailSequenceStep.day_offset")
    lead = relationship("Lead", backref="sequences")


class EmailSequenceStep(Base):
    __tablename__ = "email_sequence_steps"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=new_uuid)
    sequence_id = Column(PGUUID(as_uuid=True), ForeignKey("email_sequences.id", ondelete="CASCADE"), nullable=False, index=True)
    day_offset = Column(Integer, nullable=False)   # days after sequence creation
    subject = Column(String, nullable=False)
    body = Column(Text, nullable=False)
    status = Column(Enum(StepStatus), default=StepStatus.PENDING)
    send_at = Column(DateTime(timezone=True), nullable=False)   # computed on creation
    sent_at = Column(DateTime(timezone=True), nullable=True)
    gmail_message_id = Column(String, nullable=True)

    sequence = relationship("EmailSequence", back_populates="steps")
