from uuid import UUID
from fastapi import APIRouter, Depends, Request
from fastapi_injector import Injected

from app.auth.dependencies import auth, permissions
from app.core.permissions.constants import Permissions as P
from app.schemas.api_key import ApiKeyRead, ApiKeyCreate, ApiKeyRotate, ApiKeyUpdate
from app.schemas.filter import ApiKeysFilter
from app.services.api_keys import ApiKeysService

router = APIRouter()

@router.post("", response_model=ApiKeyRead, dependencies=[
    Depends(auth),
    Depends(permissions(P.ApiKey.CREATE))
])
async def create(api_key: ApiKeyCreate, service: ApiKeysService = Injected(ApiKeysService)):
    """
    Create an API key with a given list of 'role_ids'.
    NOTE: The user must actually possess those roles, or creation will fail.
    """
    return await service.create(api_key)

@router.get("", response_model=list[ApiKeyRead], dependencies=[
    Depends(auth),
    Depends(permissions(P.ApiKey.READ))
])
async def get_all(api_keys_filter: ApiKeysFilter = Depends(), service: ApiKeysService = Injected(ApiKeysService)):
    return await service.get_all(api_keys_filter)

@router.get("/{api_key_id}", response_model=ApiKeyRead, dependencies=[
    Depends(auth),
    Depends(permissions(P.ApiKey.READ))
])
async def get(api_key_id: UUID, service: ApiKeysService = Injected(ApiKeysService)):
    return await service.get(api_key_id)

@router.delete("/{api_key_id}", dependencies=[
    Depends(auth),
    Depends(permissions(P.ApiKey.DELETE))
])
async def delete(api_key_id: UUID, service: ApiKeysService = Injected(ApiKeysService)):
     await service.delete(api_key_id)
     return {"message": f"API key with id: {api_key_id} deleted successfully"}

@router.patch("/{api_key_id}", response_model=ApiKeyRead, dependencies=[
    Depends(auth),
    Depends(permissions(P.ApiKey.UPDATE))
])
async def update(request: Request, api_key_id: UUID, api_key_data: ApiKeyUpdate, service: ApiKeysService =
                Injected(ApiKeysService)):
    return await service.update(api_key_id, api_key_data)


@router.post(
    "/{api_key_id}/rotate",
    response_model=ApiKeyRead,
    dependencies=[
        Depends(auth),
        Depends(permissions(P.ApiKey.UPDATE)),
    ],
)
async def rotate_api_key(
    api_key_id: UUID,
    body: ApiKeyRotate,
    service: ApiKeysService = Injected(ApiKeysService),
):
    """
    Issue a new secret for this API key. The previous secret can remain valid for a bounded
    overlap window to support agent and integration cutovers.
    """
    return await service.rotate(api_key_id, body)
