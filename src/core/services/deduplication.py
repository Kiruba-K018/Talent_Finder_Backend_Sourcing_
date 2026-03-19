from datetime import datetime, timezone
from src.data.repositories.candidate_repo import (
    find_by_name_and_title,
    insert_candidate,
    update_candidate,
)
from src.constants import OUTCOME_INSERT, OUTCOME_UPDATE, OUTCOME_SKIP
from src.observability.logging.logger import get_logger
from src.observability.metrics.prometheus import duplicates_detected_total

logger = get_logger(__name__)


async def resolve_candidate(document: dict) -> tuple[str, str]:
    """
    Deduplicate candidates by name and title.
    Returns (mongodb_id, outcome) where outcome is one of:
    OUTCOME_INSERT | OUTCOME_UPDATE | OUTCOME_SKIP
    
    Logic:
    - Find candidate with same name and title
    - If not found: INSERT new candidate
    - If found: Compare hash field
      - If hash differs: UPDATE candidate (it's a different resume)
      - If hash matches: SKIP (it's the same candidate)
    """
    candidate_name = document.get("candidate_name", "")
    title = document.get("title", "")
    new_hash = document.get("hash", "")
    candidate_uuid = document.get("candidate_id", "")
    
    try:
        # Find existing candidate with same name and title
        existing = await find_by_name_and_title(candidate_name, title)
        
        if existing is None:
            # No candidate with this name+title found, insert new
            try:
                mongodb_id = await insert_candidate(document)
                logger.info("candidate_inserted", candidate_id=candidate_uuid, name=candidate_name)
                return mongodb_id, OUTCOME_INSERT
            except Exception as e:
                logger.error("failed_to_insert_candidate", candidate_id=candidate_uuid, error=str(e))
                raise
        
        # Found candidate with same name+title, compare hash
        mongodb_id = str(existing["_id"])
        existing_hash = existing.get("hash", "")
        
        if existing_hash != new_hash:
            # Different resume content, update the candidate
            try:
                updates = {
                    **{k: document[k] for k in document if k not in ("_id", "created_at")},
                    "updated_on": datetime.now(timezone.utc).isoformat(),
                }
                await update_candidate(mongodb_id, updates)
                duplicates_detected_total.labels(outcome=OUTCOME_UPDATE).inc()
                logger.info("candidate_updated", candidate_id=candidate_uuid, name=candidate_name)
                return mongodb_id, OUTCOME_UPDATE
            except Exception as e:
                logger.error("failed_to_update_candidate", candidate_id=candidate_uuid, mongodb_id=mongodb_id, error=str(e))
                raise
        else:
            # Same hash, same resume, skip to avoid duplicate
            duplicates_detected_total.labels(outcome=OUTCOME_SKIP).inc()
            logger.info("candidate_skipped_duplicate", candidate_id=candidate_uuid, name=candidate_name, hash=new_hash)
            return mongodb_id, OUTCOME_SKIP
    
    except Exception as e:
        logger.error("deduplication_error", candidate_name=candidate_name, title=title, error=str(e))
        raise