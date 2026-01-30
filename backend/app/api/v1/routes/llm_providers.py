from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi_injector import Injected
from app.core.permissions.constants import Permissions as P
from app.auth.dependencies import auth, permissions
from app.modules.workflow.llm.provider import LLMProvider
from app.schemas.llm import LlmProviderCreate, LlmProviderRead, LlmProviderUpdate
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
    llm_provider: LLMProvider = Injected(LLMProvider),
):
    res = await service.create(data)
    await llm_provider.reload()
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
    llm_provider: LLMProvider = Injected(LLMProvider),
):
    res = await service.update(llm_provider_id, data)
    await llm_provider.reload()
    return res


@router.delete(
    "/{llm_provider_id}",
    dependencies=[Depends(auth), Depends(permissions(P.LlmProvider.DELETE))],
)
async def delete(
    llm_provider_id: UUID,
    service: LlmProviderService = Injected(LlmProviderService),
    llm_provider: LLMProvider = Injected(LLMProvider),
):
    res = await service.delete(llm_provider_id)
    await llm_provider.reload()
    return res
