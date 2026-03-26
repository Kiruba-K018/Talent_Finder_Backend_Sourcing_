from fastapi import APIRouter

from src.data.clients.mongo_client import get_mongo_client
from src.data.clients.postgres_client import get_engine
from src.schema.sourcing_schema import HealthCheckResponse, HealthReadinessResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthCheckResponse)
async def health_check() -> HealthCheckResponse:
    """Check service health status.

    Returns basic service liveness status without dependency checks.

    Returns:
        HealthCheckResponse: Service status (ok).
    """
    return HealthCheckResponse(status="ok", service="talent_finder_backend_sourcing")


@router.get("/health/ready", response_model=HealthReadinessResponse)
async def readiness() -> HealthReadinessResponse:
    """Check service readiness with dependency status.

    Performs health checks on MongoDB and PostgreSQL connections to verify service readiness.
    Returns degraded status if any dependency is unavailable.

    Returns:
        HealthReadinessResponse: Status (ok/degraded) with per-dependency checks.
    """
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
    return HealthReadinessResponse(status=status, checks=checks)
