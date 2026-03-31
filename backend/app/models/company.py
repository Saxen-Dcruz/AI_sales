from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database.core import Base

class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("search_campaigns.id"), nullable=True)

    name = Column(String, index=True)
    linkedin_url = Column(String, unique=True, index=True)
    website = Column(String, nullable=True)    
    industry = Column(String)
    company_size = Column(String)
    headquarters = Column(String)
    about = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # String references to other classes
    campaign = relationship("SearchCampaign", back_populates="companies")
    leads = relationship("Lead", back_populates="company")
    deals = relationship("Deal", back_populates="company")