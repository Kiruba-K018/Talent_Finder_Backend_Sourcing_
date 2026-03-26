from motor.motor_asyncio import AsyncIOMotorDatabase

from src.config.settings import get_settings
from src.data.clients.mongo_client import get_mongo_db
from src.observability.logging.logger import get_logger

logger = get_logger(__name__)


def _collection():
    db: AsyncIOMotorDatabase = get_mongo_db()
    return db[get_settings().mongo_candidates_collection]


async def ensure_indexes() -> None:
    """Create required indexes for deduplication queries."""
    collection = _collection()
    try:
        await collection.create_index([("candidate_name", 1), ("title", 1)])
        await collection.create_index("hash")
        await collection.create_index("source_run_id")
        await collection.create_index("candidate_id")
        logger.info("mongodb_indexes_created_successfully")
    except Exception as e:
        logger.error("failed_to_create_mongodb_indexes", error=str(e))


async def find_by_name_and_title(candidate_name: str, title: str) -> dict | None:
    """Find candidate by name and title for deduplication."""
    try:
        return await _collection().find_one(
            {"candidate_name": candidate_name, "title": title}
        )
    except Exception as e:
        logger.error(
            "failed_to_query_by_name_title",
            name=candidate_name,
            title=title,
            error=str(e),
        )
        return None


async def insert_candidate(document: dict) -> str:
    result = await _collection().insert_one(document)
    return str(result.inserted_id)


async def update_candidate(mongodb_id: str, updates: dict) -> None:
    """Update existing candidate by MongoDB _id."""
    try:
        result = await _collection().update_one(
            {"_id": mongodb_id},
            {"$set": updates},
        )

        if result.matched_count == 0:
            logger.warning(
                "candidate_update_no_match",
                mongodb_id=mongodb_id,
            )
    except Exception as e:
        logger.error("candidate_update_failed", mongodb_id=mongodb_id, error=str(e))
        raise
