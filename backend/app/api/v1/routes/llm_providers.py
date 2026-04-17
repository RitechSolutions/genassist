from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi_injector import Injected

from app.auth.dependencies import auth, permissions
from app.cache.redis_cache import invalidate_llm_provider_cache
from app.core.permissions.constants import Permissions as P
from app.modules.workflow.llm.provider import LLMProvider
from app.schemas.llm import LlmProviderBase, LlmProviderCreate, LlmProviderMinimal, LlmProviderRead, LlmProviderUpdate
from app.services.llm_providers import LlmProviderService

router = APIRouter()


@router.get(
    "",
    response_model=list[LlmProviderRead],
    dependencies=[Depends(auth), Depends(permissions(P.LlmProvider.READ))],
)
async def get_all(service: LlmProviderService = Injected(LlmProviderService)):
    return await service.get_all()


@router.get(
    "/minimal",
    response_model=list[LlmProviderMinimal],
    dependencies=[Depends(auth), Depends(permissions(P.LlmProvider.READ))],
)
async def get_all_minimal(service: LlmProviderService = Injected(LlmProviderService)):
    """
    Get a lightweight list of all LLM providers (no connection_data or connection_status).
    """
    return await service.get_all_minimal()


@router.get(
    "/form_schemas",
    dependencies=[
        Depends(auth),
    ],
)
async def get_form_schemas(llm_provider: LLMProvider = Injected(LLMProvider)):
    return await llm_provider.get_configuration_definitions()


@router.get(
    "/{llm_provider_id}",
    response_model=LlmProviderRead,
    dependencies=[Depends(auth), Depends(permissions(P.LlmProvider.READ))],
)
async def get(
    llm_provider_id: UUID, service: LlmProviderService = Injected(LlmProviderService)
):
    return await service.get_by_id(llm_provider_id)


@router.post(
    "",
    response_model=LlmProviderRead,
    dependencies=[Depends(auth), Depends(permissions(P.LlmProvider.CREATE))],
)
async def create(
    data: LlmProviderCreate,
    service: LlmProviderService = Injected(LlmProviderService),
):
    res = await service.create(data)
    await invalidate_llm_provider_cache(provider_id=None)
    return res


@router.patch(
    "/{llm_provider_id}",
    response_model=LlmProviderRead,
    dependencies=[Depends(auth), Depends(permissions(P.LlmProvider.UPDATE))],
)
async def update(
    llm_provider_id: UUID,
    data: LlmProviderUpdate,
    service: LlmProviderService = Injected(LlmProviderService),
):
    res = await service.update(llm_provider_id, data)
    await invalidate_llm_provider_cache(provider_id=llm_provider_id)
    return res


@router.delete(
    "/{llm_provider_id}",
    dependencies=[Depends(auth), Depends(permissions(P.LlmProvider.DELETE))],
)
async def delete(
    llm_provider_id: UUID,
    service: LlmProviderService = Injected(LlmProviderService),
):
    res = await service.delete(llm_provider_id)
    await invalidate_llm_provider_cache(provider_id=llm_provider_id)
    return res


@router.post("/test-connection", dependencies=[Depends(auth)])
async def test_connection(
    llm_provider: LlmProviderBase,
    provider_id: Optional[UUID] = None,
    service: LlmProviderService = Injected(LlmProviderService),
):
    return await service.test_connection(
        llm_provider.llm_model_provider, llm_provider.connection_data, provider_id
    )
