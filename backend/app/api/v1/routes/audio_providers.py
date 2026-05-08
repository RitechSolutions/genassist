from typing import Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi_injector import Injected

from app.auth.dependencies import auth, permissions
from app.cache.redis_cache import invalidate_audio_provider_cache
from app.core.permissions.constants import Permissions as P
from app.schemas.audio_provider import (
    AudioProviderBase,
    AudioProviderCreate,
    AudioProviderMinimal,
    AudioProviderRead,
    AudioProviderUpdate,
)
from app.services.audio_providers import AudioProviderService

router = APIRouter()


@router.get(
    "",
    response_model=list[AudioProviderRead],
    dependencies=[Depends(auth), Depends(permissions(P.LlmProvider.READ))],
)
async def get_all(service: AudioProviderService = Injected(AudioProviderService)):
    return await service.get_all()


@router.get(
    "/minimal",
    response_model=list[AudioProviderMinimal],
    dependencies=[Depends(auth), Depends(permissions(P.LlmProvider.READ))],
)
async def get_all_minimal(service: AudioProviderService = Injected(AudioProviderService)):
    return await service.get_all_minimal()


@router.get(
    "/by-capability/{capability}",
    response_model=list[AudioProviderRead],
    dependencies=[Depends(auth), Depends(permissions(P.LlmProvider.READ))],
)
async def get_by_capability(capability: Literal["tts", "stt", "both"], service: AudioProviderService = Injected(AudioProviderService)):
    return await service.get_all_by_capability(capability)


@router.get(
    "/form-schemas",
    dependencies=[Depends(auth)],
)
async def get_form_schemas():
    from app.modules.workflow.audio.provider import get_all_form_schemas
    return get_all_form_schemas()


@router.get(
    "/node-schemas",
    dependencies=[Depends(auth)],
)
async def get_node_schemas():
    from app.modules.workflow.audio.provider import get_all_node_schemas
    return get_all_node_schemas()


@router.get(
    "/{provider_id}",
    response_model=AudioProviderRead,
    dependencies=[Depends(auth), Depends(permissions(P.LlmProvider.READ))],
)
async def get_by_id(provider_id: UUID, service: AudioProviderService = Injected(AudioProviderService)):
    return await service.get_by_id(provider_id)


@router.post(
    "",
    response_model=AudioProviderRead,
    status_code=201,
    dependencies=[Depends(auth), Depends(permissions(P.LlmProvider.CREATE))],
)
async def create(data: AudioProviderCreate, service: AudioProviderService = Injected(AudioProviderService)):
    obj = await service.create(data)
    await invalidate_audio_provider_cache()
    return AudioProviderRead.model_validate(obj)


@router.patch(
    "/{provider_id}",
    response_model=AudioProviderRead,
    dependencies=[Depends(auth), Depends(permissions(P.LlmProvider.UPDATE))],
)
async def update(provider_id: UUID, data: AudioProviderUpdate, service: AudioProviderService = Injected(AudioProviderService)):
    obj = await service.update(provider_id, data)
    await invalidate_audio_provider_cache(provider_id=provider_id)
    return AudioProviderRead.model_validate(obj)


@router.delete(
    "/{provider_id}",
    dependencies=[Depends(auth), Depends(permissions(P.LlmProvider.DELETE))],
)
async def delete(provider_id: UUID, service: AudioProviderService = Injected(AudioProviderService)):
    res = await service.delete(provider_id)
    await invalidate_audio_provider_cache(provider_id=provider_id)
    return res


@router.post("/test-connection", dependencies=[Depends(auth)])
async def test_connection(
    data: AudioProviderBase,
    provider_id: Optional[UUID] = None,
    service: AudioProviderService = Injected(AudioProviderService),
):
    return await service.test_connection(data.provider_type, data.capability, data.connection_data, provider_id)
