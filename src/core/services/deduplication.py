from datetime import datetime, timezone
from src.data.repositories.candidate_repo import (
    find_by_identity_hash,
    insert_candidate,
    update_candidate,
)
from src.constants import OUTCOME_INSERT, OUTCOME_UPDATE, OUTCOME_SKIP
from src.observability.logging.logger import get_logger
from src.observability.metrics.prometheus import duplicates_detected_total

logger = get_logger(__name__)


async def resolve_candidate(document: dict) -> tuple[str, str]:
    """
    Returns (mongodb_id, outcome) where outcome is one of:
    OUTCOME_INSERT | OUTCOME_UPDATE | OUTCOME_SKIP
    Note: The UUID candidate_id is embedded in the document, mongodb_id is for internal reference
    """
    existing = await find_by_identity_hash(document["hash_identity"])
    candidate_uuid = document.get("candidate_id", "")

    if existing is None:
        mongodb_id = await insert_candidate(document)
        logger.info("candidate_inserted", candidate_id=candidate_uuid)
        return mongodb_id, OUTCOME_INSERT

    mongodb_id = str(existing["_id"])
    candidate_uuid = str(existing.get("candidate_id", mongodb_id))

    if existing["hash_profile"] != document["hash_profile"]:
        updates = {
            **{k: document[k] for k in document if k not in ("_id", "created_at")},
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        await update_candidate(mongodb_id, updates)
        duplicates_detected_total.labels(outcome=OUTCOME_UPDATE).inc()
        logger.info("candidate_updated", candidate_id=candidate_uuid)
        return mongodb_id, OUTCOME_UPDATE

    duplicates_detected_total.labels(outcome=OUTCOME_SKIP).inc()
    logger.info("candidate_skipped_no_change", candidate_id=candidate_uuid)
    return mongodb_id, OUTCOME_SKIP