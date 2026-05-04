from sqlalchemy import Column, SmallInteger, Boolean
from app.database.core import Base


class OperatorAvailability(Base):
    """One row per day of week (0=Mon … 6=Sun). Configures when the sales operator accepts meetings."""
    __tablename__ = "operator_availability"

    day_of_week = Column(SmallInteger, primary_key=True)   # 0=Mon … 6=Sun
    is_available = Column(Boolean, default=True)
    start_hour = Column(SmallInteger, default=9)
    start_minute = Column(SmallInteger, default=0)
    end_hour = Column(SmallInteger, default=18)
    end_minute = Column(SmallInteger, default=0)


class SchedulingConfig(Base):
    """Singleton row (id=1) for global meeting scheduling settings."""
    __tablename__ = "scheduling_config"

    id = Column(SmallInteger, primary_key=True, default=1)
    buffer_minutes = Column(SmallInteger, default=15)       # gap required between meetings
    slot_duration_minutes = Column(SmallInteger, default=30)
    max_meetings_per_day = Column(SmallInteger, default=8)
