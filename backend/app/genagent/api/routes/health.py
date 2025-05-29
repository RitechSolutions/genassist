from fastapi import APIRouter, Depends
from app.genagent.core.config import get_settings

router = APIRouter(prefix="/health")

@router.get("/", summary="Health check")
async def health_check():
    """Return health status of the API."""
    return {"status": "healthy"}

@router.get("/info", summary="Application info")
async def info(settings=Depends(get_settings)):
    """Return application information."""
    return {
        "app_name": settings.app_name,
        "environment": settings.environment,
        "version": settings.version
    } 