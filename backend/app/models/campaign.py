from sqlalchemy import Column, String, DateTime, Boolean
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database.core import Base
from app.core.utils import new_uuid


class SearchCampaign(Base):
    __tablename__ = "search_campaigns"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=new_uuid)
    name = Column(String, index=True)
    target_industry = Column(String)
    target_size = Column(String, nullable=True)
    target_location = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    companies = relationship("Company", back_populates="campaign")
