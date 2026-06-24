from sqlalchemy import Column, Numeric, String, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database.core import Base
from app.core.utils import new_uuid


class Deal(Base):
    __tablename__ = "deals"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=new_uuid)
    # RBAC owner — the user who owns this deal. NOT NULL enforced (migration 022).
    owner_id = Column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    company_id = Column(PGUUID(as_uuid=True), ForeignKey("companies.id"))
    lead_id = Column(PGUUID(as_uuid=True), ForeignKey("leads.id"), nullable=True)

    deal_name = Column(String)
    deal_value = Column(Numeric(12, 2), default=0.00)

    stage = Column(String, default="Prospect")
    win_probability = Column(Numeric(5, 2), default=10)
    loss_reason = Column(String, nullable=True)

    expected_close_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)

    company = relationship("Company", back_populates="deals")
    lead = relationship("Lead")

    @property
    def company_name(self):
        return self.company.name if self.company else None

    @property
    def contact_name(self):
        return self.lead.name if self.lead else None

    @property
    def lead_email(self):
        return self.lead.email if self.lead else None
