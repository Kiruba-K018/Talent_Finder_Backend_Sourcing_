from motor.motor_asyncio import AsyncIOMotorDatabase
from src.data.clients.mongo_client import get_mongo_db
from src.config.settings import get_settings


def _collection():
    db: AsyncIOMotorDatabase = get_mongo_db()
    return db[get_settings().mongo_candidates_collection]


async def find_by_identity_hash(hash_identity: str) -> dict | None:
    return await _collection().find_one({"hash_identity": hash_identity})


async def insert_candidate(document: dict) -> str:
    result = await _collection().insert_one(document)
    return str(result.inserted_id)


async def update_candidate(candidate_id: str, updates: dict) -> None:
    await _collection().update_one(
        {"_id": candidate_id},
        {"$set": updates},
    )