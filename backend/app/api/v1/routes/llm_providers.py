<<<<<<< HEAD
from fastapi import APIRouter, Depends
from uuid import UUID

from app.dependencies.services import get_llm_provider_service
from app.schemas.llm import LlmProviderRead, LlmProviderCreate, LlmProviderUpdate
from app.auth.dependencies import auth, permissions
from app.services.llm_providers import LlmProviderService

=======
from uuid import UUID

from fastapi import APIRouter, Depends

from app.auth.dependencies import auth, permissions
from app.modules.agents.llm.provider import LLMProvider
from app.schemas.llm import LlmProviderCreate, LlmProviderRead, LlmProviderUpdate
from app.services.llm_providers import LlmProviderService


>>>>>>> development
router = APIRouter()

@router.get("/", response_model=list[LlmProviderRead], dependencies=[
    Depends(auth),
    Depends(permissions("read:llm_provider"))
])
<<<<<<< HEAD
async def get_all(service: LlmProviderService = Depends(get_llm_provider_service)):
=======
async def get_all(service: LlmProviderService = Depends()):
>>>>>>> development
    return await service.get_all()

@router.get("/{llm_provider_id}", response_model=LlmProviderRead, dependencies=[
    Depends(auth),
    Depends(permissions("read:llm_provider"))
])
<<<<<<< HEAD
async def get(llm_provider_id: UUID, service: LlmProviderService = Depends(get_llm_provider_service)):
=======
async def get(llm_provider_id: UUID, service: LlmProviderService = Depends()):
>>>>>>> development
    return await service.get_by_id(llm_provider_id)

@router.post("/", response_model=LlmProviderRead, dependencies=[
    Depends(auth),
    Depends(permissions("create:llm_provider"))
])
<<<<<<< HEAD
async def create(data: LlmProviderCreate, service: LlmProviderService = Depends(get_llm_provider_service)):
    return await service.create(data)
=======
async def create(data: LlmProviderCreate, service: LlmProviderService = Depends()):
    res = await service.create(data)
    await LLMProvider.get_instance().reload()
    return res
>>>>>>> development

@router.patch("/{llm_provider_id}", response_model=LlmProviderRead, dependencies=[
    Depends(auth),
    Depends(permissions("update:llm_provider"))
])
<<<<<<< HEAD
async def update(llm_provider_id: UUID, data: LlmProviderUpdate, service: LlmProviderService = Depends(get_llm_provider_service)):
    return await service.update(llm_provider_id, data)
=======
async def update(llm_provider_id: UUID, data: LlmProviderUpdate, service: LlmProviderService = Depends()):
    res = await service.update(llm_provider_id, data)
    await LLMProvider.get_instance().reload()
    return res
>>>>>>> development

@router.delete("/{llm_provider_id}", dependencies=[
    Depends(auth),
    Depends(permissions("delete:llm_provider"))
])
<<<<<<< HEAD
async def delete(llm_provider_id: UUID, service: LlmProviderService = Depends(get_llm_provider_service)):
    return await service.delete(llm_provider_id)
=======
async def delete(llm_provider_id: UUID, service: LlmProviderService = Depends()):
    res = await service.delete(llm_provider_id)
    await LLMProvider.get_instance().reload()
    return res

>>>>>>> development
