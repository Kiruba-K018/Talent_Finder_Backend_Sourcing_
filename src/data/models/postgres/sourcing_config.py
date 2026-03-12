import uuid
from datetime import datetime, time
from sqlalchemy import Boolean, Column, DateTime, Integer, String, Time
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class SourcingConfig(Base):
    __tablename__ = "sourcing_configs"

    id             = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id         = Column(UUID(as_uuid=True), nullable=False)
    is_active      = Column(Boolean, default=True, nullable=False)
    frequency      = Column(String, nullable=False)        # "daily" | "weekly" | "hourly"
    scheduled_time = Column(Time, nullable=True)
    scheduled_day  = Column(String, nullable=True)         # "monday" | ...
    search_skills  = Column(ARRAY(String), nullable=False)
    search_location= Column(String, nullable=False)
    max_profiles   = Column(Integer, default=10)
    last_run_at    = Column(DateTime(timezone=True), nullable=True)
    next_run_at    = Column(DateTime(timezone=True), nullable=True)
    created_by     = Column(UUID(as_uuid=True), nullable=True)
    created_at     = Column(DateTime(timezone=True), default=datetime.utcnow)