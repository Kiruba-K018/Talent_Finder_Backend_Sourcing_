from fastapi import BackgroundTasks, HTTPException

from src.core.services.postfreejob import run_postjobfree_sourcing_pipeline
from src.data.clients.postgres_client import get_session_factory
from src.data.repositories.sourcing_config_repo import fetch_config_by_id
from src.observability.logging.logger import get_logger
from src.observability.metrics.prometheus import (
    scrape_failures_total,
    scrape_jobs_total,
)
from src.schema.sourcing_schema import ManualTriggerRequest, TriggerResponse

logger = get_logger(__name__)


async def manual_trigger_sourcing_job(
    payload: ManualTriggerRequest, background_tasks: BackgroundTasks
) -> TriggerResponse:
    factory = get_session_factory()
    async with factory() as session:
        config = await fetch_config_by_id(session, payload.config_id)

    if not config:
        raise HTTPException(
            status_code=404,
            detail=f"Sourcing config {payload.config_id} not found",
        )

    if not config.is_active:
        raise HTTPException(
            status_code=400,
            detail=f"Sourcing config {payload.config_id} is inactive",
        )

    # Override max_profiles if provided in request
    if payload.max_profiles:
        config.max_profiles = payload.max_profiles

    background_tasks.add_task(_run_job, config)

    return TriggerResponse(
        message="Sourcing job triggered successfully",
        config_id=str(payload.config_id),
        status="queued",
    )


async def _run_job(config, source_platform: str = "postjobfree") -> None:
    """
    Background task to run the sourcing pipeline.
    Routes to PostJobFree (default) or LinkedIn based on source_platform.
    """
    org_id = str(config.org_id)
    try:
        scrape_jobs_total.labels(org_id=org_id, status="manual").inc()
        logger.info(
            "manual_trigger_postjobfree",
            org_id=org_id,
            config_id=str(config.id),
        )
        await run_postjobfree_sourcing_pipeline(config)

    except Exception as exc:
        scrape_failures_total.labels(org_id=org_id, reason=type(exc).__name__).inc()
        logger.error(
            "manual_job_failed",
            org_id=org_id,
            config_id=str(config.id),
            error=str(exc),
            source_platform=source_platform,
        )
