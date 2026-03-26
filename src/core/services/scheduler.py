import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from src.config.settings import get_settings
from src.core.services.postfreejob import run_postjobfree_sourcing_pipeline
from src.data.clients.postgres_client import get_session_factory
from src.data.repositories.sourcing_config_repo import (
    fetch_due_configs,
    update_run_timestamps,
)
from src.observability.logging.logger import get_logger
from src.observability.metrics.prometheus import (
    scrape_failures_total,
    scrape_jobs_total,
)

logger = get_logger(__name__)
settings = get_settings()


# IST = UTC+5:30 (Indian Standard Time)
IST = timezone(timedelta(hours=5, minutes=30))


def _compute_next_run(frequency: str, scheduled_time, scheduled_day: str) -> datetime:
    """Compute next run time in IST timezone."""
    now = datetime.now(IST)
    if frequency == "hourly":
        return now + timedelta(hours=1)
    if frequency == "daily":
        next_dt = now.replace(
            hour=scheduled_time.hour if scheduled_time else 0,
            minute=scheduled_time.minute if scheduled_time else 0,
            second=0,
            microsecond=0,
        )
        # If time already passed today, schedule for tomorrow
        if next_dt <= now:
            next_dt += timedelta(days=1)
        return next_dt
    if frequency == "weekly":
        days_ahead = 7
        return now + timedelta(days=days_ahead)
    return now + timedelta(hours=1)


async def _wait_for_db(max_retries: int = 30) -> None:
    """Wait for database to be ready before starting scheduler."""
    for attempt in range(max_retries):
        try:
            factory = get_session_factory()
            async with factory() as session:
                await session.execute(text("SELECT 1"))
            logger.info("database_ready", attempt=attempt)
            return
        except Exception as exc:
            wait_time = min(2**attempt, 10)
            logger.warning(
                "database_not_ready",
                attempt=attempt,
                wait_seconds=wait_time,
                error=str(exc),
            )
            await asyncio.sleep(wait_time)

    logger.error("database_connection_failed", max_retries=max_retries)
    raise Exception("Could not connect to database after retries")


async def run_scheduler_loop() -> None:
    try:
        await _wait_for_db()
    except Exception as exc:
        logger.error("scheduler_startup_failed", error=str(exc))
        return

    logger.info("scheduler_started", poll_interval=settings.scheduler_poll_interval)

    while True:
        try:
            await _tick()
        except Exception as exc:
            logger.error("scheduler_tick_error", error=str(exc))
        await asyncio.sleep(settings.scheduler_poll_interval)


async def _tick() -> None:
    """Check for due configs and execute them (all times in IST)."""
    now = datetime.now(IST)
    factory = get_session_factory()

    async with factory() as session:
        configs = await fetch_due_configs(session, now)
        logger.info("configs_due", count=len(configs))

        for config in configs:
            org_id = str(config.org_id)

            try:
                scrape_jobs_total.labels(org_id=org_id, status="started").inc()

                # Route to appropriate pipeline based on source_platform

                logger.info(
                    "routing_to_postjobfree_pipeline",
                    org_id=org_id,
                    config_id=str(config.id),
                )
                await run_postjobfree_sourcing_pipeline(config)

                scrape_jobs_total.labels(org_id=org_id, status="completed").inc()

                next_run = _compute_next_run(
                    config.frequency,
                    config.scheduled_time,
                    config.scheduled_day,
                )
                await update_run_timestamps(session, config.id, now, next_run)

            except Exception as exc:
                scrape_failures_total.labels(
                    org_id=org_id, reason=type(exc).__name__
                ).inc()
                logger.error(
                    "pipeline_error",
                    org_id=org_id,
                    config_id=str(config.id),
                    error=str(exc),
                )
