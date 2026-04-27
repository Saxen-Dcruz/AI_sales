from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime, Boolean, Enum
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship
from sqlalchemy import ForeignKey
import enum
from app.database.core import Base
from app.core.utils import new_uuid


class EventTrigger(str, enum.Enum):
    DEAL_SIGNAL = "deal_signal"       # positive deal metrics crossed threshold
    RAG_INSUFFICIENT = "rag_insufficient"  # knowledge base couldn't answer
    MANUAL = "manual"                 # human-triggered via API


class EventStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class CalendarEvent(Base):
    __tablename__ = "calendar_events"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=new_uuid)
    google_event_id = Column(String, unique=True, index=True, nullable=True)

    lead_id = Column(PGUUID(as_uuid=True), ForeignKey("leads.id", ondelete="SET NULL"), nullable=True, index=True)
    deal_id = Column(PGUUID(as_uuid=True), ForeignKey("deals.id", ondelete="SET NULL"), nullable=True, index=True)

    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    attendee_email = Column(String, nullable=False)

    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=False)

    meet_link = Column(String, nullable=True)       # Google Meet URL
    calendar_link = Column(String, nullable=True)   # HTML link to view event

    trigger = Column(Enum(EventTrigger), nullable=False)
    status = Column(Enum(EventStatus), default=EventStatus.SCHEDULED, index=True)

    invite_email_sent = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
