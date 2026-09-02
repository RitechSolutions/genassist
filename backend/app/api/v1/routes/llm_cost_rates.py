from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from fastapi_injector import Injected

from app.auth.dependencies import auth, permissions
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.permissions.constants import Permissions as P
from app.core.utils.cache_headers import no_store_headers
from app.schemas.llm_cost_rate import (
    LlmCostRateCreate,
    LlmCostRateImportResult,
    LlmCostRateRead,
    LlmCostRateUpdate,
)
from app.services.llm_cost_rates import (
    MAX_IMPORT_BYTES,
    LlmCostRateService,
    import_exceeds_byte_cap,
)

router = APIRouter()


@router.get(
    "",
    response_model=list[LlmCostRateRead],
    dependencies=[Depends(auth), Depends(permissions(P.LlmProvider.READ))],
)
async def list_cost_rates(service: LlmCostRateService = Injected(LlmCostRateService)):
    rows = await service.list_active()
    # Defensive: older rows might have NULL updated_at; avoid breaking response validation.
    for r in rows:
        if getattr(r, "updated_at", None) is None:
            r.updated_at = getattr(r, "created_at", None)
    return [
        LlmCostRateRead.model_validate(r, from_attributes=True)
        for r in rows
    ]


@router.post(
    "",
    response_model=LlmCostRateRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(auth), Depends(permissions(P.LlmProvider.UPDATE))],
)
async def create_cost_rate(
    body: LlmCostRateCreate,
    service: LlmCostRateService = Injected(LlmCostRateService),
):
    return await service.create_rate(body)


@router.put(
    "/{rate_id}",
    response_model=LlmCostRateRead,
    dependencies=[Depends(auth), Depends(permissions(P.LlmProvider.UPDATE))],
)
async def update_cost_rate(
    rate_id: UUID,
    body: LlmCostRateUpdate,
    service: LlmCostRateService = Injected(LlmCostRateService),
):
    updated = await service.update_rate(rate_id, body)
    if not updated:
        raise HTTPException(status_code=404, detail="Cost rate not found")
    return updated


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
    raw = await file.read(MAX_IMPORT_BYTES + 1)
    if not raw:
        raise AppException(error_key=ErrorKey.INVALID_FILE_FORMAT, status_code=400, error_detail="Empty file")
    if import_exceeds_byte_cap(raw):
        raise AppException(
            error_key=ErrorKey.INVALID_FILE_FORMAT,
            status_code=400,
            error_detail=f"File must be {MAX_IMPORT_BYTES // (1024 * 1024)} MB or smaller",
        )
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as e:
        raise AppException(
            error_key=ErrorKey.INVALID_FILE_FORMAT,
            status_code=400,
            error_detail="File must be UTF-8 encoded"
        ) from e
    return await service.import_csv(text)


@router.get(
    "/export",
    dependencies=[Depends(auth), Depends(permissions(P.LlmProvider.READ))],
)
async def export_cost_rates_csv(
    include_cache_rates: bool = Query(
        False, description="Add the cache rate columns. Off keeps the 4-column layout older tools expect."
    ),
    service: LlmCostRateService = Injected(LlmCostRateService),
):
    csv_text = await service.export_csv(include_cache_rates)
    return StreamingResponse(
        iter([csv_text]),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="llm-cost-rates.csv"',
            **no_store_headers(),
        },
    )


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
