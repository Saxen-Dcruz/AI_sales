from sqlalchemy import JSON, Column, Integer, String, Text, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database.core import Base


# 🆕 The New Interaction Table (Your AI's Memory)
class Interaction(Base):
    __tablename__ = "interactions"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"))
    
    # What type of contact was this? (Email, LinkedIn, LiveKit Voice Call)
    channel = Column(String) 
    
    # Was it inbound (they replied) or outbound (we reached out)?
    direction = Column(String) 
    
    # The actual email body or the LiveKit call transcript
    raw_content = Column(Text, nullable=True) 
    
    # 🤖 AI GENERATED COLUMNS
    ai_summary = Column(Text, nullable=True)       # A 2-sentence summary of the 10-minute call
    interaction_sentiment = Column(String)  
    
    # For LiveKit / Voice Calls
    duration_seconds = Column(Integer, default=0)
    recording_url = Column(String, nullable=True)
    transcript_url = Column(String, nullable=True) # Link to full VAD/STT text
    
    # AI Feature Extraction (JSON)
    # e.g., {"budget": "$5000", "timeline": "Q3", "objections": ["too expensive"]}
    extracted_features = Column(JSON, nullable=True)       # Sentiment of THIS specific message/call
    
    timestamp = Column(DateTime, default=datetime.utcnow)

    # Relationship back to the Lead
    lead = relationship("Lead", back_populates="interactions")


class ChatSession(Base):
    """Links an anonymous website session to an eventual Lead."""
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, unique=True, index=True) # Matches the Langchain session_id
    
    # If the AI successfully gets their email, we link them here!
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=True) 
    
    started_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)
    
    # AI Summaries of the entire chat
    chat_summary = Column(Text, nullable=True) # "User asked about pricing for the Adhaan clock. Needs 50 units."
    user_intent = Column(String) # "Pricing Request", "Technical Support", "General Browse"
    
    # Was this chat converted into a meeting/lead?
    is_converted = Column(Boolean, default=False) 

    lead = relationship("Lead", back_populates="chat_sessions")