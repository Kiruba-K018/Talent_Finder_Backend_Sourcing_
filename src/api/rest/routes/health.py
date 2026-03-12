from fastapi import APIRouter
from src.data.clients.mongo_client import get_mongo_client
from src.data.clients.postgres_client import get_engine

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    return {"status": "ok", "service": "talent_finder_backend_sourcing"}


@router.get("/health/ready")
async def readiness():
    checks = {}
    try:
        client = get_mongo_client()
        await client.admin.command("ping")
        checks["mongo"] = "ok"
    except Exception as e:
        checks["mongo"] = str(e)

    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception as e:
        checks["postgres"] = str(e)

    status = "ok" if all(v == "ok" for v in checks.values()) else "degraded"
    return {"status": status, "checks": checks}