from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database.core import Base


class SearchCampaign(Base):
    __tablename__ = "search_campaigns"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)               # e.g., "Texas Auto Manufacturers"
    target_industry = Column(String)                # e.g., "Motor Vehicle Manufacturing"
    target_size = Column(String, nullable=True)     # e.g., "10K+" or "51-200"
    target_location = Column(String)                # e.g., "Texas, United States"
    is_active = Column(Boolean, default=True)       # Toggle to pause/start scraping
    created_at = Column(DateTime, default=datetime.utcnow)

    # One Campaign links to Many Companies
    companies = relationship("Company", back_populates="campaign")


class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    
    # 🆕 2. The Foreign Key linking this company to the campaign that found it
    campaign_id = Column(Integer, ForeignKey("search_campaigns.id"), nullable=True)

    name = Column(String, index=True)
    linkedin_url = Column(String, unique=True, index=True)
    website = Column(String, nullable=True)    
    industry = Column(String)
    company_size = Column(String)
    headquarters = Column(String)
    about = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 🆕 3. Relationships
    campaign = relationship("SearchCampaign", back_populates="companies")
    leads = relationship("Lead", back_populates="company")


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
    
    # 🆕 CRM Tracking Columns
    status = Column(String, default="Uncontacted") # Uncontacted, In Sequence, Meeting Booked, Closed/Won, Dead
    interest_level = Column(String, default="Cold") # Cold, Warm, Hot
    overall_sentiment = Column(String, default="Neutral") # Positive, Neutral, Negative
    last_contacted_at = Column(DateTime, nullable=True)
    next_followup_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    company = relationship("Company", back_populates="leads")
    
    # 🆕 One Lead has MANY Interactions
    interactions = relationship("Interaction", back_populates="lead", cascade="all, delete-orphan")


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
    interaction_sentiment = Column(String)         # Sentiment of THIS specific message/call
    
    timestamp = Column(DateTime, default=datetime.utcnow)

    # Relationship back to the Lead
    lead = relationship("Lead", back_populates="interactions")