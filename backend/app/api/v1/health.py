"""Health and readiness endpoints."""

import asyncio

import structlog
from fastapi import APIRouter

from app.config import settings
from app.infrastructure.persistence.database import engine

logger = structlog.get_logger()
router = APIRouter(tags=["health"])

HEALTH_CHECK_TIMEOUT = 3.0  # seconds


async def _check_database() -> str:
    """Check database connectivity with timeout."""
    try:
        async with asyncio.timeout(HEALTH_CHECK_TIMEOUT):
            async with engine.connect() as conn:
                await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        return "healthy"
    except Exception as exc:
        # Don't escalate — /health is polled frequently and an unhealthy DB
        # already shows up in the response. Info-level lets ops dashboards
        # surface the cause without flooding warn channels.
        await logger.ainfo(
            "health_check_db_unreachable",
            error=type(exc).__name__,
        )
        return "unreachable"


async def _check_redis() -> str:
    """Check Redis connectivity with timeout."""
    try:
        import redis.asyncio as aioredis

        async with asyncio.timeout(HEALTH_CHECK_TIMEOUT):
            client = aioredis.from_url(settings.REDIS_URL)
            await client.ping()
            await client.aclose()
        return "healthy"
    except Exception as exc:
        await logger.ainfo(
            "health_check_redis_unreachable",
            error=type(exc).__name__,
        )
        return "unreachable"


@router.get("/health")
async def health_check():
    db_status = await _check_database()
    redis_status = await _check_redis()

    all_healthy = db_status == "healthy" and redis_status == "healthy"
    any_up = db_status == "healthy" or redis_status == "healthy"

    if all_healthy:
        status = "healthy"
    elif any_up:
        status = "degraded"
    else:
        status = "unhealthy"

    response = {
        "status": status,
        "services": {
            "database": db_status,
            "redis": redis_status,
        },
    }

    if status == "unhealthy":
        from fastapi.responses import JSONResponse
        return JSONResponse(content=response, status_code=503)

    return response


@router.get("/ready")
async def readiness_check():
    db_status = await _check_database()
    if db_status != "healthy":
        from fastapi.responses import JSONResponse
        return JSONResponse(
            content={"ready": False, "reason": "database not reachable"},
            status_code=503,
        )
    return {"ready": True}
