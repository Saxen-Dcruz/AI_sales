from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Text, DateTime, Enum, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship
from app.database.core import Base
from app.core.utils import new_uuid
import enum


class CallDirection(str, enum.Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class CallStatus(str, enum.Enum):
    NEW = "new"
    ACTIVE = "active"
    COMPLETED = "completed"
    MISSED = "missed"
    FAILED = "failed"
    VOICEMAIL = "voicemail"


class CallOutcome(str, enum.Enum):
    INTERESTED = "interested"
    NOT_INTERESTED = "not_interested"
    FOLLOW_UP = "follow_up"
    CONVERTED = "converted"
    NO_ANSWER = "no_answer"
    UNKNOWN = "unknown"


class Call(Base):
    __tablename__ = "calls"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=new_uuid)
    # RBAC owner — the user who owns/handled this call. NOT NULL enforced (migration 022).
    owner_id = Column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    lead_id = Column(PGUUID(as_uuid=True), ForeignKey("leads.id", ondelete="SET NULL"), nullable=True, index=True)

    direction = Column(Enum(CallDirection), nullable=False)
    status = Column(Enum(CallStatus), default=CallStatus.NEW, index=True)
    outcome = Column(Enum(CallOutcome), nullable=True)

    phone_number = Column(String, nullable=True)
    livekit_room = Column(String, nullable=True)
    recording_url = Column(String, nullable=True)

    started_at = Column(DateTime(timezone=True), nullable=True)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Integer, default=0)

    transcript = Column(Text, nullable=True)
    ai_summary = Column(Text, nullable=True)
    sentiment = Column(String, nullable=True)    # POSITIVE | NEUTRAL | FRUSTRATED

    # Detected product and knowledge gaps (same structure as emails)
    detected_product_id = Column(String, nullable=True)
    detected_product_name = Column(String, nullable=True)
    followup_gaps = Column(JSON, nullable=True)  # list[{question, topic, product_name, product_id, resolved, answer}]

    # Structured extraction from transcript
    intent = Column(String, nullable=True)           # ready_to_buy | exploring | not_interested
    urgency = Column(String, nullable=True)          # immediate | 1-3_months | 6+_months | unknown
    product_interest = Column(String, nullable=True) # product name the customer expressed interest in

    handled_by = Column(String, nullable=True)   # user email of the rep who took the call
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    lead = relationship("Lead", backref="calls")
