from sqlalchemy import Column, Integer, Numeric, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database.core import Base

class Deal(Base):
    __tablename__ = "deals"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"))
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=True) # The champion
    
    # What are they buying?
    deal_name = Column(String) # e.g., "100x STM32 Controllers"
    deal_value = Column(Numeric(12, 2), default=0.00) # Dollar amount
    
    # Conversion Tracking
    stage = Column(String) # e.g., "Discovery", "Demo", "Proposal", "Won", "Lost"
    win_probability = Column(Integer, default=10) # 0 to 100%
    loss_reason = Column(String, nullable=True) # Crucial for AI to learn why deals fail
    
    expected_close_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)

    # Relationships
    company = relationship("Company", back_populates="deals")
    lead = relationship("Lead")
