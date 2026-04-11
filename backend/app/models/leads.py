from sqlalchemy import JSON, Column, Integer, Numeric, String, Text, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database.core import Base


class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"))
    
    name = Column(String, index=True)
    linkedin_url = Column(String, unique=True, index=True)
    email = Column(String, nullable=True)      
    phone = Column(String, nullable=True)      
    headline = Column(String)
    location = Column(String)
    current_role = Column(String) 
    about = Column(Text)

    chat_sessions = relationship("ChatSession", back_populates="lead")
    
    # 🆕 CRM Tracking Columns
    status = Column(String, default="Uncontacted") # Uncontacted, In Sequence, Meeting Booked, Closed/Won, Dead
    interest_level = Column(String, default="Cold") # Cold, Warm, Hot
    overall_sentiment = Column(String, default="Neutral") # Positive, Neutral, Negative
    last_contacted_at = Column(DateTime, nullable=True)
    next_followup_at = Column(DateTime, nullable=True)
    # The "Living Document": AI updates this after EVERY new interaction
    global_ai_summary = Column(Text, nullable=True) 
    
    # AI decides what the human sales rep should do next
    next_best_action = Column(String, nullable=True) 
    
    # Engagement Score (1-100) calculated by how often they reply/talk to the bot
    engagement_score = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    company = relationship("Company", back_populates="leads")
    
    # 🆕 One Lead has MANY Interactions
    interactions = relationship("Interaction", back_populates="lead", cascade="all, delete-orphan")



