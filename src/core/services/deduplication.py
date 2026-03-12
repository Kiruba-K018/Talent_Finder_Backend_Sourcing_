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
    Returns (candidate_id, outcome) where outcome is one of:
    OUTCOME_INSERT | OUTCOME_UPDATE | OUTCOME_SKIP
    """
    existing = await find_by_identity_hash(document["hash_identity"])

    if existing is None:
        candidate_id = await insert_candidate(document)
        logger.info("candidate_inserted", candidate_id=candidate_id)
        return candidate_id, OUTCOME_INSERT

    candidate_id = str(existing["_id"])

    if existing["hash_profile"] != document["hash_profile"]:
        updates = {
            **{k: document[k] for k in document if k not in ("_id", "created_at")},
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        await update_candidate(candidate_id, updates)
        duplicates_detected_total.labels(outcome=OUTCOME_UPDATE).inc()
        logger.info("candidate_updated", candidate_id=candidate_id)
        return candidate_id, OUTCOME_UPDATE

    duplicates_detected_total.labels(outcome=OUTCOME_SKIP).inc()
    logger.info("candidate_skipped_no_change", candidate_id=candidate_id)
    return candidate_id, OUTCOME_SKIP