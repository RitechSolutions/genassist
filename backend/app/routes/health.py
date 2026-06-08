from __future__ import annotations

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.dependencies.injector import injector

router = APIRouter()


@router.get("/health")
async def health():
    return {"service": "backend", "status": "ok"}


@router.get("/ready")
async def ready():
    """
    Readiness probe.

    Backend service's `/ready` endpoint, but validates backend-critical
    dependencies (Redis) instead of WS connection stats.
    """
    try:
        from app.dependencies.dependency_injection import RedisBinary, RedisString

        redis_string = injector.get(RedisString)
        redis_binary = injector.get(RedisBinary)

        await redis_string.ping()
        await redis_binary.ping()

        return {"service": "backend", "status": "ready"}
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"service": "backend", "status": "not_ready", "error": str(e)},
        )

