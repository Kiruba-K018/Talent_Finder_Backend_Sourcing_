from fastapi import APIRouter, HTTPException, BackgroundTasks
from src.data.clients.postgres_client import get_session_factory
from src.data.repositories.sourcing_config_repo import fetch_config_by_id
from src.observability.logging.logger import get_logger
from src.core.services.sourcing.sourcing_service import manual_trigger_sourcing_job
from src.schema.sourcing_schema import ManualTriggerRequest, TriggerResponse

router = APIRouter(prefix="/sourcing", tags=["sourcing"])
logger = get_logger(__name__)



@router.post("/trigger", response_model=TriggerResponse)
async def trigger_sourcing_job(
    payload: ManualTriggerRequest,
    background_tasks: BackgroundTasks,
):
    """
    Manually trigger a sourcing job for a given config_id.
    By default, uses PostJobFree scraping pipeline.
    """
    return await manual_trigger_sourcing_job(payload, background_tasks)
    

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
        "config_id":           str(config.id),
        "org_id":              str(config.org_id),
        "query":               query,
        "search_skills":       config.search_skills,
        "search_location":     config.search_location,
        "max_profiles":        payload.max_profiles or config.max_profiles,
        "frequency":           config.frequency
    }

