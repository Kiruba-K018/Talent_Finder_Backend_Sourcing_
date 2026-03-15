import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from src.config.settings import get_settings
from src.constants import INTERNAL_CANDIDATES_PATH, INTERNAL_SOURCE_RUNS_PATH
from src.observability.logging.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


def _build_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=settings.core_service_url,
        timeout=settings.core_service_timeout,
        headers={"Content-Type": "application/json", "X-Internal": "sourcing"},
    )


@retry(
    stop=stop_after_attempt(settings.core_service_max_retries),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(httpx.HTTPError),
    reraise=True,
)
async def send_candidate_to_core(candidate: dict) -> dict:
    async with _build_client() as client:
        response = await client.post(INTERNAL_CANDIDATES_PATH, json=candidate)
        response.raise_for_status()
        logger.info(
            "candidate_sent_to_core",
            status=response.status_code,
            candidate_id=candidate.get("_id"),
        )
        return response.json()


@retry(
    stop=stop_after_attempt(settings.core_service_max_retries),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(httpx.HTTPError),
    reraise=True,
)
async def send_source_run_report(source_run: dict) -> dict:
    """Send source run completion report to core service."""
    async with _build_client() as client:
        response = await client.post(INTERNAL_SOURCE_RUNS_PATH, json=source_run)
        response.raise_for_status()
        logger.info(
            "source_run_report_sent_to_core",
            status=response.status_code,
            source_run_id=source_run.get("source_run_id"),
            count=source_run.get("number_of_resume_fetched"),
        )
        return response.json()