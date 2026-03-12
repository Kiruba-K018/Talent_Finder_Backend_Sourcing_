import uuid
from datetime import datetime, timezone
from src.core.services.scraper import build_driver, inject_session_cookie, search_profiles, fetch_profile_html
from src.core.services.parser import parse_profile
from src.core.services.deduplication import resolve_candidate
from src.core.services.embedding import embed_and_store
from src.handlers.http_clients.core_service_client import send_candidate_to_core
from src.utils.hashing import compute_identity_hash, compute_profile_hash
from src.utils.query_builder import build_google_search_query
from src.config.settings import get_settings
from src.observability.logging.logger import get_logger
from src.observability.metrics.prometheus import candidates_extracted_total
from src.constants import OUTCOME_SKIP

logger = get_logger(__name__)
settings = get_settings()


async def run_sourcing_pipeline(config) -> None:
    org_id = str(config.org_id)
    query  = build_google_search_query(config.search_skills, config.search_location)

    logger.info("pipeline_start", org_id=org_id, query=query)

    driver = build_driver()
    try:
        if settings.linkedin_session_cookie:
            inject_session_cookie(driver, settings.linkedin_session_cookie)

        profile_urls = search_profiles(driver, query, config.max_profiles)

        for url in profile_urls:
            await _process_profile(driver, url, org_id)

    finally:
        driver.quit()

    logger.info("pipeline_complete", org_id=org_id)


async def _process_profile(driver, url: str, org_id: str) -> None:
    try:
        html = fetch_profile_html(driver, url)
        candidate = parse_profile(html, url)

        if not candidate["name"]:
            logger.warning("skipping_unnamed_profile", url=url)
            return

        candidate["_id"]          = str(uuid.uuid4())
        candidate["hash_identity"] = compute_identity_hash(
            candidate["name"], candidate["email"], candidate["location"]
        )
        candidate["hash_profile"]  = compute_profile_hash(
            candidate["hard_skills"],
            candidate["education"],
            candidate["experience"],
            candidate["certifications"],
        )
        now = datetime.now(timezone.utc).isoformat()
        candidate["created_at"] = now
        candidate["updated_at"] = now

        candidate_id, outcome = await resolve_candidate(candidate)
        candidates_extracted_total.labels(org_id=org_id).inc()

        if outcome != OUTCOME_SKIP:
            await send_candidate_to_core(candidate)
            await embed_and_store(candidate_id, candidate)

        logger.info(
            "profile_processed",
            candidate_id=candidate_id,
            outcome=outcome,
            url=url,
        )

    except Exception as exc:
        logger.error("profile_processing_error", url=url, error=str(exc))