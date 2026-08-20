from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi_injector import Injected

from app.auth.dependencies import auth, permissions
from app.core.permissions.constants import Permissions as P
from app.schemas.llm_model_catalog import (
    LlmModelCatalogCreate,
    LlmModelCatalogProvider,
    LlmModelCatalogRead,
    LlmModelCatalogUpdate,
)
from app.services.llm_model_catalog import LlmModelCatalogService

router = APIRouter()


@router.get(
    "",
    response_model=list[LlmModelCatalogRead],
    dependencies=[Depends(auth), Depends(permissions(P.LlmProvider.READ))],
)
async def list_models(
    service: LlmModelCatalogService = Injected(LlmModelCatalogService),
):
    return await service.list_entries()


@router.get(
    "/providers",
    response_model=list[LlmModelCatalogProvider],
    dependencies=[Depends(auth), Depends(permissions(P.LlmProvider.READ))],
)
async def list_providers(
    service: LlmModelCatalogService = Injected(LlmModelCatalogService),
):
    """Provider types that can be extended, with the models already built in."""
    return service.list_providers()


@router.post(
    "",
    response_model=LlmModelCatalogRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(auth), Depends(permissions(P.LlmProvider.UPDATE))],
)
async def create_model(
    body: LlmModelCatalogCreate,
    service: LlmModelCatalogService = Injected(LlmModelCatalogService),
):
    return await service.create_entry(body)


@router.put(
    "/{entry_id}",
    response_model=LlmModelCatalogRead,
    dependencies=[Depends(auth), Depends(permissions(P.LlmProvider.UPDATE))],
)
async def update_model(
    entry_id: UUID,
    body: LlmModelCatalogUpdate,
    service: LlmModelCatalogService = Injected(LlmModelCatalogService),
):
    updated = await service.update_entry(entry_id, body)
    if not updated:
        raise HTTPException(status_code=404, detail="Model not found")
    return updated


@router.delete(
    "/{entry_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(auth), Depends(permissions(P.LlmProvider.DELETE))],
)
async def delete_model(
    entry_id: UUID,
    service: LlmModelCatalogService = Injected(LlmModelCatalogService),
):
    if not await service.delete_entry(entry_id):
        raise HTTPException(status_code=404, detail="Model not found")
