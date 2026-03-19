import uuid
from datetime import datetime, timezone, timedelta
from src.core.services.scraper import search_profiles, fetch_profile_html, get_authenticated_driver
from src.core.services.parser import parse_profile
from src.core.services.llm import format_candidate_with_llm
from src.core.services.deduplication import resolve_candidate
from src.core.services.embedding import embed_and_store
from src.core.services.candidate_transformer import transform_candidate_to_schema
from src.handlers.http_clients.core_service_client import send_candidate_to_core, send_source_run_report
from src.utils.query_builder import build_google_search_query
import hashlib
import json
from src.config.settings import get_settings
from src.observability.logging.logger import get_logger
from src.observability.metrics.prometheus import candidates_extracted_total
from src.constants import OUTCOME_SKIP, LINKEDIN_PLATFORM_ID

logger = get_logger(__name__)
settings = get_settings()

# IST timezone (UTC+5:30)
IST = timezone(timedelta(hours=5, minutes=30))


def _get_ist_time(utc_time: datetime = None) -> datetime:
    """Convert UTC time to IST timezone."""
    if utc_time is None:
        # Get current UTC time and convert to IST
        return datetime.now(timezone.utc).astimezone(IST)
    return utc_time.astimezone(IST)


def _compute_resume_hash(parsed_candidate: dict) -> str:
    """
    Compute a hash of the resume content for deduplication.
    Uses experience, education, skills, and other key profile data.
    """
    try:
        hash_data = {
            "experience": parsed_candidate.get("experience", []),
            "education": parsed_candidate.get("education", []),
            "hard_skills": sorted(parsed_candidate.get("hard_skills", [])),
            "certifications": parsed_candidate.get("certifications", []),
            "projects": parsed_candidate.get("projects", []),
        }
        hash_string = json.dumps(hash_data, sort_keys=True, default=str)
        return hashlib.md5(hash_string.encode()).hexdigest()
    except Exception as e:
        logger.warning("failed_to_compute_resume_hash", error=str(e))
        # Return a hash of just the profile URL as fallback
        profile_url = parsed_candidate.get("profile_url", "")
        return hashlib.md5(profile_url.encode()).hexdigest()


async def run_sourcing_pipeline(config) -> None:
    org_id = str(config.org_id)
    query  = build_google_search_query(config.search_skills, config.search_location)
    source_run_id = uuid.uuid4()
    profiles_fetched = 0
    run_start_time = _get_ist_time()

    logger.info("pipeline_start", org_id=org_id, query=query, source_run_id=str(source_run_id))

    # Step 0: Create source run record with in_progress status
    try:
        await _create_source_run_record(
            source_run_id=source_run_id,
            config_id=config.id,
            run_start_time=run_start_time,
        )
    except Exception as e:
        logger.error("Failed to create source run record", error=str(e))
        raise

    # Step 1: Get authenticated driver with cookie-first strategy
    logger.info("Step 1: Authenticating to LinkedIn...")
    try:
        driver = get_authenticated_driver()  # Tries cookie first, then password login
    except Exception as e:
        logger.error("Failed to initialize driver", error=str(e))
        # Report failed run
        await _report_source_run(
            source_run_id=source_run_id,
            config_id=config.id,
            status="failed",
            profiles_fetched=0,
            run_start_time=run_start_time,
        )
        raise
    
    try:
        # Verify we're authenticated
        try:
            driver.get("https://www.linkedin.com/feed")
            import time
            time.sleep(2)
            if "login" in driver.current_url.lower():
                logger.error("Authentication failed - not able to access LinkedIn feed")
                await _report_source_run(
                    source_run_id=source_run_id,
                    config_id=config.id,
                    status="failed",
                    profiles_fetched=0,
                    run_start_time=run_start_time,
                )
                return
        except Exception as auth_error:
            logger.error("Failed to verify authentication", error=str(auth_error))
            await _report_source_run(
                source_run_id=source_run_id,
                config_id=config.id,
                status="failed",
                profiles_fetched=0,
                run_start_time=run_start_time,
            )
            raise
        
        logger.info("Step 2: Successfully authenticated - proceeding with search")
        
        # Step 3: Extract location from config
        location = config.search_location if config.search_location else "India"
        
        # Step 4: Search directly on LinkedIn (now authenticated)
        logger.info("Step 3: Searching LinkedIn...")
        profile_urls = search_profiles(driver, query, config.max_profiles, location)

        # Step 5: Process each profile (while authenticated)
        logger.info("Step 4: Processing profiles...")
        for url in profile_urls:
            profiles_count = await _process_profile(driver, url, org_id)
            if profiles_count > 0:
                profiles_fetched += profiles_count

    finally:
        driver.quit()

    # Report successful run completion
    await _report_source_run(
        source_run_id=source_run_id,
        config_id=config.id,
        status="completed",
        profiles_fetched=profiles_fetched,
        run_start_time=run_start_time,
    )

    logger.info("pipeline_complete", org_id=org_id, source_run_id=str(source_run_id), profiles_fetched=profiles_fetched)


async def _process_profile(driver, url: str, org_id: str) -> int:
    """
    Process a LinkedIn profile and return 1 if successfully fetched, 0 if skipped.
    """
    try:
        html = fetch_profile_html(driver, url)
        parsed_candidate = parse_profile(html, url)

        if not parsed_candidate["name"]:
            logger.warning("skipping_unnamed_profile", url=url)
            return 0

        # Format candidate data with LLM for standardization and cleanup
        logger.debug(f"Formatting candidate with LLM: {parsed_candidate.get('name', 'Unknown')}")
        try:
            formatted_candidate = format_candidate_with_llm(parsed_candidate)
            # Normalize keys: LLM returns different keys than parser
            if "candidate_name" in formatted_candidate and "name" not in formatted_candidate:
                formatted_candidate["name"] = formatted_candidate["candidate_name"]
            if "candidate_email" in formatted_candidate and "email" not in formatted_candidate:
                formatted_candidate["email"] = formatted_candidate["candidate_email"]
            if "contact_phone" in formatted_candidate and "phone" not in formatted_candidate:
                formatted_candidate["phone"] = formatted_candidate["contact_phone"]
            # Preserve profile_url from original parse (LinkedIn URL is authoritative)
            formatted_candidate["profile_url"] = parsed_candidate.get("profile_url", url)
            formatted_candidate["source_platform"] = parsed_candidate.get("source_platform", "linkedin")
            parsed_candidate = formatted_candidate
        except Exception as e:
            logger.warning(f"LLM formatting failed, using raw parsed data: {str(e)}")
            # Continue with raw parsed data if LLM fails

        # Generate resume hash for deduplication
        try:
            resume_hash = _compute_resume_hash(parsed_candidate)
        except Exception as e:
            logger.error("failed_to_generate_resume_hash", url=url, error=str(e))
            return 0
        
        # Generate UUID candidate_id for external reference
        candidate_id = str(uuid.uuid4())
        
        # Prepare candidate for deduplication
        # The hash field will be compared to detect if the same person has a different resume
        candidate_for_dedup = {
            **parsed_candidate,
            "candidate_id": candidate_id,
            "hash": resume_hash,  # Resume content hash for deduplication
        }
        
        # Resolve candidate (check for duplicates by name+title)
        try:
            resolved_id, outcome = await resolve_candidate(candidate_for_dedup)
        except Exception as e:
            logger.error("deduplication_failed", url=url, error=str(e), exc_info=True)
            return 0
        
        # Use the UUID candidate_id, not the MongoDB _id
        # Transform to MongoDB schema with all required fields
        candidate = transform_candidate_to_schema(
            parsed_candidate,
            candidate_id=candidate_id,
            hash_value=resume_hash,
            org_id=org_id,
        )
        
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
            return 1  # Successfully fetched and sent
        else:
            logger.info("profile_skipped", url=url, outcome=outcome)
            return 0

    except Exception as exc:
        logger.error("profile_processing_error", url=url, error=str(exc))
        return 0


async def _create_source_run_record(
    source_run_id: uuid.UUID,
    config_id: uuid.UUID,
    run_start_time: datetime,
) -> None:
    """Create a source run record with in_progress status when sourcing starts."""
    try:
        # Ensure time is in IST timezone
        ist_start_time = run_start_time if run_start_time.tzinfo else _get_ist_time(run_start_time)
        source_run_data = {
            "source_run_id": str(source_run_id),
            "platform_id": LINKEDIN_PLATFORM_ID,
            "status": "in_progress",
            "config_id": str(config_id),
            "run_at": ist_start_time.isoformat(),
        }
        
        await send_source_run_report(source_run_data)
        logger.info(
            "source_run_record_created",
            source_run_id=str(source_run_id),
            status="in_progress",
        )
    except Exception as e:
        logger.error(
            "failed_to_create_source_run_record",
            source_run_id=str(source_run_id),
            error=str(e),
        )
        raise


async def _report_source_run(
    source_run_id: uuid.UUID,
    config_id: uuid.UUID,
    status: str,
    profiles_fetched: int,
    run_start_time: datetime,
) -> None:
    """Update source run record with completion status and profile count."""
    try:
        # Ensure times are in IST timezone
        ist_start_time = run_start_time if run_start_time.tzinfo else _get_ist_time(run_start_time)
        ist_end_time = _get_ist_time()
        source_run_data = {
            "source_run_id": str(source_run_id),
            "platform_id": LINKEDIN_PLATFORM_ID,
            "status": status,
            "number_of_resume_fetched": profiles_fetched,
            "config_id": str(config_id),
            "run_at": ist_start_time.isoformat(),
            "completed_at": ist_end_time.isoformat(),
        }
        
        await send_source_run_report(source_run_data)
        logger.info(
            "source_run_updated",
            source_run_id=str(source_run_id),
            status=status,
            profiles_fetched=profiles_fetched,
        )
    except Exception as e:
        logger.error(
            "failed_to_update_source_run",
            source_run_id=str(source_run_id),
            error=str(e),
        )