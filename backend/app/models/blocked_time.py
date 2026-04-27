from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from app.database.core import Base
from app.core.utils import new_uuid


class BlockedTime(Base):
    __tablename__ = "blocked_times"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=new_uuid)
    day_of_week = Column(Integer, nullable=False)   # 0=Mon … 5=Sat (Sunday never a working day)
    start_hour = Column(Integer, nullable=False)     # 0–23
    end_hour = Column(Integer, nullable=False)       # 0–23, exclusive
    label = Column(String, nullable=True)            # e.g. "Lunch", "Team standup"
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
