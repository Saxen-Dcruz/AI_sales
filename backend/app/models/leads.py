from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database.core import Base
from app.core.utils import new_uuid


class Lead(Base):
    __tablename__ = "leads"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=new_uuid)
    company_id = Column(PGUUID(as_uuid=True), ForeignKey("companies.id"), nullable=True)

    name = Column(String, index=True)
    linkedin_url = Column(String, unique=True, index=True, nullable=True)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    headline = Column(String, nullable=True)
    location = Column(String, nullable=True)
    current_role = Column(String, nullable=True)
    about = Column(Text, nullable=True)

    chat_sessions = relationship("ChatSession", back_populates="lead")

    status = Column(String, default="Uncontacted")
    interest_level = Column(String, default="Cold")
    overall_sentiment = Column(String, default="Neutral")
    last_contacted_at = Column(DateTime, nullable=True)
    next_followup_at = Column(DateTime, nullable=True)
    global_ai_summary = Column(Text, nullable=True)
    next_best_action = Column(String, nullable=True)
    engagement_score = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)

    company = relationship("Company", back_populates="leads")
    interactions = relationship("Interaction", back_populates="lead", cascade="all, delete-orphan")
