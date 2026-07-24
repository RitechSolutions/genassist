from fastapi import APIRouter, Depends
from fastapi_injector import Injected

from app.auth.dependencies import auth, permissions
from app.core.permissions.constants import Permissions as P
from app.schemas.llm_usage_control import LlmUsageControlRead, LlmUsageCutoverRequest
from app.services.llm_usage_control import LlmUsageControlService

router = APIRouter()


@router.get(
    "/control",
    response_model=LlmUsageControlRead,
    dependencies=[Depends(auth), Depends(permissions(P.Dashboard.READ))],
    summary="Get LLM usage capture / shadow / cutover state",
)
async def get_control(
    service: LlmUsageControlService = Injected(LlmUsageControlService),
) -> LlmUsageControlRead:
    return await service.get_control()


@router.post(
    "/capture",
    response_model=LlmUsageControlRead,
    dependencies=[Depends(auth), Depends(permissions(P.AppSettings.WRITE))],
    summary="Activate LLM usage capture",
)
async def activate_capture(
    service: LlmUsageControlService = Injected(LlmUsageControlService),
) -> LlmUsageControlRead:
    """Enable usage capture and mark the backfill start time. No request body"""
    return await service.activate_capture()


@router.post(
    "/shadow/start",
    response_model=LlmUsageControlRead,
    dependencies=[Depends(auth), Depends(permissions(P.AppSettings.WRITE))],
    summary="Start shadow reconciliation",
)
async def start_shadow(
    service: LlmUsageControlService = Injected(LlmUsageControlService),
) -> LlmUsageControlRead:
    return await service.start_shadow()


@router.post(
    "/cutover",
    response_model=LlmUsageControlRead,
    dependencies=[Depends(auth), Depends(permissions(P.AppSettings.WRITE))],
    summary="Flip the dashboard cost source to the ledger (reversible)",
)
async def set_cutover(
    body: LlmUsageCutoverRequest,
    service: LlmUsageControlService = Injected(LlmUsageControlService),
) -> LlmUsageControlRead:
    return await service.set_cutover(body.enabled)
