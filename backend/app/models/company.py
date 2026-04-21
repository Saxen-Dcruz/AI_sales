from sqlalchemy import Column, String, Text, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database.core import Base
from app.core.utils import new_uuid


class Company(Base):
    __tablename__ = "companies"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=new_uuid)
    campaign_id = Column(PGUUID(as_uuid=True), ForeignKey("search_campaigns.id"), nullable=True)

    name = Column(String, index=True)
    linkedin_url = Column(String, unique=True, index=True)
    website = Column(String, nullable=True)
    industry = Column(String)
    company_size = Column(String)
    headquarters = Column(String)
    about = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    campaign = relationship("SearchCampaign", back_populates="companies")
    leads = relationship("Lead", back_populates="company")
    deals = relationship("Deal", back_populates="company")
