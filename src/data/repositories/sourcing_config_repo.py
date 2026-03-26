from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.models.postgres.sourcing_config import SourcingConfig


async def fetch_active_configs(session: AsyncSession) -> list[SourcingConfig]:
    result = await session.execute(
        select(SourcingConfig).where(SourcingConfig.is_active == True)
    )
    return list(result.scalars().all())


async def fetch_due_configs(
    session: AsyncSession, now: datetime
) -> list[SourcingConfig]:
    """Return configs whose next_run_at is due."""
    result = await session.execute(
        select(SourcingConfig).where(
            SourcingConfig.is_active == True,
            SourcingConfig.next_run_at <= now,
        )
    )
    return list(result.scalars().all())


async def update_run_timestamps(
    session: AsyncSession,
    config_id: UUID,
    last_run_at: datetime,
    next_run_at: datetime,
) -> None:
    await session.execute(
        update(SourcingConfig)
        .where(SourcingConfig.id == config_id)
        .values(last_run_at=last_run_at, next_run_at=next_run_at)
    )
    await session.commit()


async def fetch_config_by_id(
    session: AsyncSession, config_id: UUID
) -> SourcingConfig | None:
    result = await session.execute(
        select(SourcingConfig).where(SourcingConfig.id == config_id)
    )
    return result.scalar_one_or_none()
