from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database.core import Base

class SearchCampaign(Base):
    __tablename__ = "search_campaigns"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)               
    target_industry = Column(String)                
    target_size = Column(String, nullable=True)     
    target_location = Column(String)                
    is_active = Column(Boolean, default=True)       
    created_at = Column(DateTime, default=datetime.utcnow)

    # String reference to "Company"
    companies = relationship("Company", back_populates="campaign")