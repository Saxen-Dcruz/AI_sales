from sqlalchemy import JSON, Column, Integer, String, Text, ForeignKey, DateTime, Boolean
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database.core import Base
from app.core.utils import new_uuid


class Interaction(Base):
    __tablename__ = "interactions"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=new_uuid)
    lead_id = Column(PGUUID(as_uuid=True), ForeignKey("leads.id"))

    channel = Column(String)
    direction = Column(String)
    raw_content = Column(Text, nullable=True)

    ai_summary = Column(Text, nullable=True)
    interaction_sentiment = Column(String, nullable=True)

    duration_seconds = Column(Integer, default=0)
    recording_url = Column(String, nullable=True)
    transcript_url = Column(String, nullable=True)

    extracted_features = Column(JSON, nullable=True)

    timestamp = Column(DateTime, default=datetime.utcnow)

    lead = relationship("Lead", back_populates="interactions")


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=new_uuid)
    session_id = Column(String, unique=True, index=True)

    lead_id = Column(PGUUID(as_uuid=True), ForeignKey("leads.id"), nullable=True)

    started_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)

    chat_summary = Column(Text, nullable=True)
    user_intent = Column(String, nullable=True)
    is_converted = Column(Boolean, default=False)

    lead = relationship("Lead", back_populates="chat_sessions")
