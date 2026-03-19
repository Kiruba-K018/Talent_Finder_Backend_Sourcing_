"""PostJobFree sourcing pipeline orchestration."""

import hashlib
import uuid
from datetime import datetime, timezone, timedelta
from src.core.services.postfreejob.scraper import (
    search_postjobfree,
    scrape_resume_page,
    close_browser,
)
from src.core.services.postfreejob.parser import parse_postjobfree_resume
from src.core.services.postfreejob.llm_formatter import (
    format_postjobfree_resume_with_llm,
)
from src.core.services.deduplication import resolve_candidate
from src.core.services.embedding import embed_and_store
from src.handlers.http_clients.core_service_client import (
    send_candidate_to_core,
    send_source_run_report,
    mark_source_run_failed,
)
from src.utils.hashing import compute_identity_hash, compute_profile_hash
from src.config.settings import get_settings
from src.observability.logging.logger import get_logger

from src.constants import OUTCOME_SKIP, OUTCOME_INSERT, OUTCOME_UPDATE, POSTJOBFREE_PLATFORM_ID

logger = get_logger(__name__)
settings = get_settings()

# IST timezone (UTC+5:30)
IST = timezone(timedelta(hours=5, minutes=30))


def _get_ist_time(utc_time: datetime = None) -> datetime:
    """Convert UTC time to IST timezone."""
    if utc_time is None:
        return datetime.now(timezone.utc).astimezone(IST)
    return utc_time.astimezone(IST)


def _compute_resume_hash(raw_text: str) -> str:
    """Compute SHA256 hash of resume raw text."""
    return hashlib.sha256(raw_text.encode("utf-8")).hexdigest()


async def run_postjobfree_sourcing_pipeline(config) -> None:
    """
    Main PostJobFree sourcing pipeline.
    
    Flow:
    1. Create source run record with status in_progress
    2. Search PostJobFree using SerpAPI
    3. For each result:
       - Scrape resume page with Playwright
       - Parse resume text
       - Format with LLM
       - Compute hashes
       - Deduplicate
       - Embed skills
       - Send to core API
    4. Update source run record with final stats
    """
    org_id = str(config.org_id)
    
    # Build search query from config
    # search_skills is a list from database, convert to string
    search_skills_list = config.search_skills if isinstance(config.search_skills, list) else config.search_skills.split()
    job_title = search_skills_list[0] if search_skills_list else "developer"
    location = config.search_location or "India"
    query_skills = " ".join(search_skills_list) if search_skills_list else "developer"
    
    source_run_id = uuid.uuid4()
    run_start_time = _get_ist_time()
    
    # Initialize stats tracking
    stats = {
        "fetched": 0,
        "skipped": 0,
        "updated": 0,
        "errors": 0,
        "total_processed": 0,
    }
    
    logger.info(
        "postjobfree_pipeline_start",
        org_id=org_id,
        query=job_title,
        location=location,
        source_run_id=str(source_run_id),
    )
    
    # Step 1: Create source run record
    try:
        await _create_source_run_record(
            source_run_id=source_run_id,
            config_id=str(config.id),
            run_start_time=run_start_time,
        )
    except Exception as e:
        logger.error("failed_to_create_source_run_record", error=str(e))
        raise
    
    try:
        # Step 2: Search PostJobFree using SerpAPI
        logger.info("step_2_searching_postjobfree", query=query_skills, location=location)
        search_results, search_error = await search_postjobfree(str(query_skills), location)
        
        # Handle search errors (400, validation errors, etc.)
        if search_error:
            error_code = search_error.get("error_code", search_error.get("error", "UNKNOWN"))
            error_message = search_error.get("error_message", str(search_error))
            
            logger.error(
                "postjobfree_search_failed",
                error_code=error_code,
                error_detail=error_message,
                query=query_skills,
                location=location,
            )
            
            # Mark source run as FAILED in Core API
            try:
                await mark_source_run_failed(
                    source_run_id=str(source_run_id),
                    error_message=error_message,
                    error_code=error_code,
                )
            except Exception as e:
                logger.error(
                    "failed_to_mark_source_run_failed",
                    source_run_id=str(source_run_id),
                    error=str(e),
                )
            
            return
        
        if not search_results:
            logger.warning("no_results_from_postjobfree_search", query=query_skills)
            await _report_source_run(
                source_run_id=source_run_id,
                config_id=config.id,
                status="completed",
                stats=stats,
                run_start_time=run_start_time,
            )
            return
        
        logger.info("postjobfree_search_results_received", count=len(search_results))
        
        # Step 3: Extract and process resume URLs
        max_profiles = settings.postjobfree_max_profiles
        
        # Extract all valid resume URLs upfront from search results
        resume_urls = []
        for result in search_results:
            resume_url = result.get("link")
            if resume_url:
                resume_urls.append(resume_url)
        
        # Limit to max_profiles
        resume_urls = resume_urls[:max_profiles]
        
        logger.info(
            "extracted_resume_urls",
            total_urls=len(resume_urls),
            max_profiles=max_profiles,
        )
        
        # Process each resume URL one by one asynchronously
        processed_count = 0
        
        for profile_index, resume_url in enumerate(resume_urls, start=1):
            total_profiles = len(resume_urls)
            
            try:
                # Log progress
                logger.info(
                    "processing_resume_profile",
                    profile_number=profile_index,
                    total_profiles=total_profiles,
                    url=resume_url,
                )
                
                # Step 3a: Scrape individual resume page asynchronously
                logger.debug(
                    "scraping_resume",
                    profile_number=profile_index,
                    url=resume_url,
                )
                scraped_data = await scrape_resume_page(resume_url)
                
                if not scraped_data:
                    logger.warning(
                        "failed_to_scrape_resume",
                        profile_number=profile_index,
                        url=resume_url,
                    )
                    stats["errors"] += 1
                    processed_count += 1
                    continue
                
                # Handle both dict and string returns for backward compatibility
                if isinstance(scraped_data, dict):
                    raw_text = scraped_data.get("text")
                else:
                    # Legacy: string return value
                    raw_text = scraped_data
                
                if not raw_text:
                    logger.warning(
                        "no_resume_content_found",
                        profile_number=profile_index,
                        url=resume_url,
                    )
                    stats["errors"] += 1
                    processed_count += 1
                    continue
                
                # Step 3b & 3c: Parse and format resume using text-based parsing
                logger.debug(
                    "parsing_resume",
                    profile_number=profile_index,
                    url=resume_url,
                    text_length=len(raw_text) if raw_text else 0,
                )
                
                # Use text-based parsing since we have reliable text extraction
                # (HTML parsing requires specific div wrapper structure that may vary)
                parsed_candidate = parse_postjobfree_resume(raw_text)
                candidate_name = parsed_candidate.get("candidate_name") or "Unknown"
                
                logger.debug(
                    "formatting_with_llm",
                    profile_number=profile_index,
                    candidate=candidate_name,
                )
                formatted_candidate = format_postjobfree_resume_with_llm(parsed_candidate)
                
                # Note: Continue processing even if candidate_name is missing
                # Core API can match on email, location, skills, or other attributes
                if not formatted_candidate:
                    logger.warning(
                        "parse_failed_empty_result",
                        profile_number=profile_index,
                        url=resume_url,
                    )
                    stats["errors"] += 1
                    processed_count += 1
                    continue
                
                # Step 3d: Compute hashes
                resume_hash = _compute_resume_hash(raw_text)
                identity_hash = compute_identity_hash(
                    formatted_candidate.get("candidate_name", ""),
                    formatted_candidate.get("candidate_email", ""),
                    formatted_candidate.get("location", ""),
                    formatted_candidate.get("contact_linkedin_url", ""),
                )
                profile_hash = compute_profile_hash(
                    formatted_candidate.get("hard_skills", []),
                    formatted_candidate.get("education", []),
                    formatted_candidate.get("experience", []),
                    [],  # certifications
                )
                
                # Step 3e: Add metadata to candidate
                candidate_id = str(uuid.uuid4())
                resume_id = str(uuid.uuid4())
                platform_id = POSTJOBFREE_PLATFORM_ID
                
                now_iso = datetime.now(timezone.utc).isoformat()
                
                # Prepare document for MongoDB
                document = {
                    "_id": str(uuid.uuid4()).replace("-", "")[:24],
                    "candidate_id": candidate_id,
                    "resume_id": resume_id,
                    "platform_id": platform_id,
                    "sourced_at": now_iso,
                    "source_run_id": str(source_run_id),
                    "job_id": None,
                    "updated_on": now_iso,
                    "hash": resume_hash,
                    "hash_identity": identity_hash,
                    "hash_profile": profile_hash,
                    "resume_url": resume_url,
                    **formatted_candidate,
                    "parsed_resume_data": {
                        "candidate_id": candidate_id,
                        "candidate_name": formatted_candidate.get("candidate_name"),
                        "title": formatted_candidate.get("title"),
                        "hard_skills": formatted_candidate.get("hard_skills", []),
                        "soft_skills": formatted_candidate.get("soft_skills", []),
                        "experience": formatted_candidate.get("experience", []),
                        "projects": formatted_candidate.get("projects", []),
                        "education": formatted_candidate.get("education", []),
                    },
                }
                
                # Step 3f: Deduplicate
                candidate_name = formatted_candidate.get("candidate_name", "Unknown")
                logger.debug(
                    "deduplicating_candidate",
                    profile_number=profile_index,
                    candidate=candidate_name,
                )
                mongodb_id, outcome = await resolve_candidate(document)
                
                # Update stats
                dedup_outcome = "unknown"
                if outcome == OUTCOME_INSERT:
                    stats["fetched"] += 1
                    dedup_outcome = "insert"
                elif outcome == OUTCOME_UPDATE:
                    stats["updated"] += 1
                    dedup_outcome = "update"
                elif outcome == OUTCOME_SKIP:
                    stats["skipped"] += 1
                    dedup_outcome = "skip"
                
                stats["total_processed"] += 1
                
                # Step 3g: Embed skills in Chroma
                if outcome != OUTCOME_SKIP:
                    logger.debug(
                        "embedding_candidate",
                        profile_number=profile_index,
                        candidate=candidate_name,
                        outcome=dedup_outcome,
                    )
                    try:
                        await embed_and_store(mongodb_id, document)
                    except Exception as e:
                        logger.error(
                            "failed_to_embed",
                            profile_number=profile_index,
                            candidate_id=mongodb_id,
                            error=str(e),
                        )
                
                # Step 3h: Send to core API
                if outcome != OUTCOME_SKIP:
                    logger.debug(
                        "sending_to_core_service",
                        profile_number=profile_index,
                        candidate_id=mongodb_id,
                        outcome=dedup_outcome,
                    )
                    try:
                        await send_candidate_to_core(document)
                    except Exception as e:
                        logger.error(
                            "failed_to_send_to_core",
                            profile_number=profile_index,
                            candidate_id=mongodb_id,
                            error=str(e),
                        )
                
                # Log completion of this profile
                logger.info(
                    "resume_profile_completed",
                    profile_number=profile_index,
                    total_profiles=total_profiles,
                    candidate=candidate_name,
                    outcome=dedup_outcome,
                )
                
                processed_count += 1
                
            except Exception as e:
                logger.error(
                    "error_processing_resume",
                    profile_number=profile_index,
                    url=resume_url,
                    error=str(e),
                )
                stats["errors"] += 1
                processed_count += 1
        
        logger.info(
            "postjobfree_pipeline_completed",
            total_processed=stats["total_processed"],
            fetched=stats["fetched"],
            updated=stats["updated"],
            skipped=stats["skipped"],
            errors=stats["errors"],
        )
        
    finally:
        # Close browser
        await close_browser()
        
        # Step 4: Update source run record with final status
        try:
            await _report_source_run(
                source_run_id=source_run_id,
                config_id=str(config.id),
                status="completed",
                stats=stats,
                run_start_time=run_start_time,
            )
        except Exception as e:
            logger.error("failed_to_update_source_run_record", error=str(e))


async def _create_source_run_record(
    source_run_id: uuid.UUID,
    config_id: str,
    run_start_time: datetime,
) -> None:
    """Create initial source run record with status in_progress."""
    # This would typically call the core API
    # For now, we'll just log it
    logger.info(
        "source_run_record_created",
        source_run_id=str(source_run_id),
        config_id=config_id,
        status="in_progress",
    )


async def _report_source_run(
    source_run_id: uuid.UUID,
    config_id: str,
    status: str,
    stats: dict,
    run_start_time: datetime,
) -> None:
    """Report final source run status to core service."""
    run_end_time = _get_ist_time()
    
    # Build report with exact field names expected by Core API
    source_run_report = {
        "source_run_id": str(source_run_id),
        "platform_id": POSTJOBFREE_PLATFORM_ID,  # Use the platform UUID
        "status": status,
        "number_of_resume_fetched": stats["fetched"],
        "config_id": str(config_id),
        "run_at": run_start_time.isoformat(),
        "completed_at": run_end_time.isoformat(),
    }
    
    logger.info(
        "sending_source_run_report",
        source_run_id=str(source_run_id),
        stats=stats,
        report=source_run_report,
    )
    
    try:
        await send_source_run_report(source_run_report)
    except Exception as e:
        logger.error("failed_to_send_source_run_report", error=str(e))
        # Don't raise - allow pipeline to complete even if report fails
