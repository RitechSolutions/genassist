from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi_injector import Injected

from app.auth.dependencies import auth, permissions
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.permissions.constants import Permissions as P
from app.schemas.llm_cost_rate import LlmCostRateImportResult, LlmCostRateRead
from app.services.llm_cost_rates import LlmCostRateService

router = APIRouter()


@router.get(
    "",
    response_model=list[LlmCostRateRead],
    dependencies=[Depends(auth), Depends(permissions(P.LlmProvider.READ))],
)
async def list_cost_rates(service: LlmCostRateService = Injected(LlmCostRateService)):
    rows = await service.list_active()
    return [
        LlmCostRateRead.model_validate(r, from_attributes=True)
        for r in rows
    ]


@router.post(
    "/import",
    response_model=LlmCostRateImportResult,
    dependencies=[Depends(auth), Depends(permissions(P.LlmProvider.UPDATE))],
)
async def import_cost_rates_csv(
    file: UploadFile = File(...),
    service: LlmCostRateService = Injected(LlmCostRateService),
):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise AppException(error_key=ErrorKey.INVALID_FILE_FORMAT, status_code=400, error_detail="File must be a CSV file")
    raw = await file.read()
    if not raw:
        raise AppException(error_key=ErrorKey.INVALID_FILE_FORMAT, status_code=400, error_detail="Empty file")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as e:
        raise AppException(
            error_key=ErrorKey.INVALID_FILE_FORMAT,
            status_code=400,
            error_detail="File must be UTF-8 encoded"
        ) from e
    return await service.import_csv(text)


@router.delete(
    "/{rate_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(auth), Depends(permissions(P.LlmProvider.UPDATE))],
)
async def delete_cost_rate(
    rate_id: UUID,
    service: LlmCostRateService = Injected(LlmCostRateService),
):
    deleted = await service.delete_by_id(rate_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Cost rate not found")
