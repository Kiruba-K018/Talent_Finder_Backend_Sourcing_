import uuid
from datetime import datetime, time

from sqlalchemy import ARRAY, Boolean, DateTime, Integer, String, Time
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class SourcingConfig(Base):
    __tablename__ = "sourcing_configs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    frequency: Mapped[str] = mapped_column(String, nullable=False)
    scheduled_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    scheduled_day: Mapped[str | None] = mapped_column(String, nullable=True)
    search_skills: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False)
    search_location: Mapped[str] = mapped_column(String, nullable=False)
    max_profiles: Mapped[int] = mapped_column(Integer, default=10)
    last_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    next_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
