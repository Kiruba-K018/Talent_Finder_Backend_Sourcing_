from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from uuid import UUID
from src.data.clients.postgres_client import get_session_factory
from src.data.repositories.sourcing_config_repo import fetch_config_by_id
from src.core.services.pipeline import run_sourcing_pipeline
from src.observability.logging.logger import get_logger
from src.observability.metrics.prometheus import scrape_jobs_total, scrape_failures_total

router = APIRouter(prefix="/sourcing", tags=["sourcing"])
logger = get_logger(__name__)


class ManualTriggerRequest(BaseModel):
    config_id: UUID
    max_profiles: int | None = None   # optional override


class TriggerResponse(BaseModel):
    message: str
    config_id: str
    status: str


@router.post("/trigger", response_model=TriggerResponse)
async def trigger_sourcing_job(
    payload: ManualTriggerRequest,
    background_tasks: BackgroundTasks,
):
    """
    Manually trigger a sourcing job for a given config_id.
    Job runs in the background — returns immediately.
    """
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


@router.post("/trigger/dry-run", response_model=dict)
async def dry_run_sourcing_job(payload: ManualTriggerRequest):
    """
    Returns what query would be built and what config would be used
    without actually running the scraper.
    """
    from src.utils.query_builder import build_google_search_query

    factory = get_session_factory()
    async with factory() as session:
        config = await fetch_config_by_id(session, payload.config_id)

    if not config:
        raise HTTPException(status_code=404, detail="Config not found")

    query = build_google_search_query(config.search_skills, config.search_location)

    return {
        "config_id":       str(config.id),
        "org_id":          str(config.org_id),
        "query":           query,
        "search_skills":   config.search_skills,
        "search_location": config.search_location,
        "max_profiles":    payload.max_profiles or config.max_profiles,
        "frequency":       config.frequency,
        "is_active":       config.is_active,
    }


async def _run_job(config) -> None:
    org_id = str(config.org_id)
    try:
        scrape_jobs_total.labels(org_id=org_id, status="manual").inc()
        await run_sourcing_pipeline(config)
        scrape_jobs_total.labels(org_id=org_id, status="completed").inc()
        logger.info("manual_job_completed", org_id=org_id, config_id=str(config.id))
    except Exception as exc:
        scrape_failures_total.labels(org_id=org_id, reason=type(exc).__name__).inc()
        logger.error("manual_job_failed", org_id=org_id, error=str(exc))