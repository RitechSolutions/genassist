from uuid import UUID

from fastapi import APIRouter, Depends

from app.auth.dependencies import auth, permissions
from app.modules.agents.llm.provider import LLMProvider
from app.schemas.llm import LlmProviderCreate, LlmProviderRead, LlmProviderUpdate
from app.services.llm_providers import LlmProviderService


router = APIRouter()

@router.get("/", response_model=list[LlmProviderRead], dependencies=[
    Depends(auth),
    Depends(permissions("read:llm_provider"))
])
async def get_all(service: LlmProviderService = Depends()):
    return await service.get_all()

@router.get("/{llm_provider_id}", response_model=LlmProviderRead, dependencies=[
    Depends(auth),
    Depends(permissions("read:llm_provider"))
])
async def get(llm_provider_id: UUID, service: LlmProviderService = Depends()):
    return await service.get_by_id(llm_provider_id)

@router.post("/", response_model=LlmProviderRead, dependencies=[
    Depends(auth),
    Depends(permissions("create:llm_provider"))
])
async def create(data: LlmProviderCreate, service: LlmProviderService = Depends()):
    res = await service.create(data)
    await LLMProvider.get_instance().reload()
    return res

@router.patch("/{llm_provider_id}", response_model=LlmProviderRead, dependencies=[
    Depends(auth),
    Depends(permissions("update:llm_provider"))
])
async def update(llm_provider_id: UUID, data: LlmProviderUpdate, service: LlmProviderService = Depends()):
    res = await service.update(llm_provider_id, data)
    await LLMProvider.get_instance().reload()
    return res

@router.delete("/{llm_provider_id}", dependencies=[
    Depends(auth),
    Depends(permissions("delete:llm_provider"))
])
async def delete(llm_provider_id: UUID, service: LlmProviderService = Depends()):
    res = await service.delete(llm_provider_id)
    await LLMProvider.get_instance().reload()
    return res

