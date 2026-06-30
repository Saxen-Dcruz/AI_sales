import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    Boolean, Column, ForeignKey, Integer, SmallInteger,
    Text, DateTime, String,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from app.database.core import Base
from app.core.utils import new_uuid


class ChannelOrigin(str, PyEnum):
    WHATSAPP = "whatsapp"
    GMAIL    = "gmail"
    DIRECT   = "direct"


class VoiceSessionStatus(str, PyEnum):
    PENDING   = "pending"    # Room created; customer has not yet joined
    ACTIVE    = "active"     # Customer is in the room
    ESCALATED = "escalated"  # AI handed off to human path
    COMPLETED = "completed"  # Call ended normally
    EXPIRED   = "expired"    # Customer never joined within token TTL


class EscalationType(str, PyEnum):
    NONE        = "none"
    GMEET       = "gmeet"
    OFFICE_CALL = "office_call"


class VoiceSession(Base):
    __tablename__ = "voice_sessions"

    id                = Column(PGUUID(as_uuid=True), primary_key=True, default=new_uuid)
    room_name         = Column(String(128), nullable=False, unique=True, index=True)
    channel_origin    = Column(String(16),  nullable=False)
    channel_ref_id    = Column(PGUUID(as_uuid=True), nullable=True)  # WA msg or email ID
    lead_id           = Column(PGUUID(as_uuid=True), ForeignKey("leads.id", ondelete="SET NULL"), nullable=True)
    owner_id          = Column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    status            = Column(String(16), nullable=False, default=VoiceSessionStatus.PENDING)
    participant_token = Column(Text, nullable=False)          # short-lived JWT for browser client
    token_expires_at  = Column(DateTime(timezone=True), nullable=False)
    joined_at         = Column(DateTime(timezone=True), nullable=True)
    ended_at          = Column(DateTime(timezone=True), nullable=True)
    duration_seconds  = Column(Integer, nullable=True)
    transcript        = Column(Text, nullable=True)
    ai_summary        = Column(Text, nullable=True)
    unanswered_count  = Column(Integer, nullable=False, default=0)
    escalation_type   = Column(String(16), nullable=False, default=EscalationType.NONE)
    escalation_ref    = Column(Text, nullable=True)           # GMeet URL or office number
    feedback_sent     = Column(Boolean, nullable=False, default=False)
    created_at        = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


class VoiceCallFeedback(Base):
    __tablename__ = "voice_call_feedbacks"

    id           = Column(PGUUID(as_uuid=True), primary_key=True, default=new_uuid)
    session_id   = Column(PGUUID(as_uuid=True), ForeignKey("voice_sessions.id", ondelete="CASCADE"), nullable=False, unique=True)
    lead_id      = Column(PGUUID(as_uuid=True), ForeignKey("leads.id", ondelete="SET NULL"), nullable=True)
    rating       = Column(SmallInteger, nullable=False)   # 1–5
    comment      = Column(Text, nullable=True)
    channel_used = Column(String(16), nullable=False)     # 'whatsapp' | 'gmail'
    submitted_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
