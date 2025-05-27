from uuid import UUID
from fastapi import APIRouter, Depends, Request
from app.auth.dependencies import auth, permissions

from app.schemas.api_key import ApiKeyRead, ApiKeyReadAfterCreate, ApiKeyCreate, ApiKeyUpdate
from app.schemas.filter import ApiKeysFilter
from app.services.api_keys import ApiKeysService

router = APIRouter()

@router.post("/", response_model=ApiKeyReadAfterCreate, dependencies=[
    Depends(auth),
    Depends(permissions("create:api_key"))
])
async def create(api_key: ApiKeyCreate, service: ApiKeysService = Depends()):
    """
    Create an API key with a given list of 'role_ids'.
    NOTE: The user must actually possess those roles, or creation will fail.
    """
    return await service.create(api_key)

@router.get("/", response_model=list[ApiKeyRead], dependencies=[
    Depends(auth),
    Depends(permissions("read:api_key"))
])
async def get_all(api_keys_filter: ApiKeysFilter = Depends(), service: ApiKeysService = Depends()):
    return await service.get_all(api_keys_filter)

@router.get("/{api_key_id}", response_model=ApiKeyRead, dependencies=[
    Depends(auth),
    Depends(permissions("read:api_key"))
])
async def get(api_key_id: UUID, service: ApiKeysService = Depends()):
    return await service.get(api_key_id)

@router.delete("/{api_key_id}", dependencies=[
    Depends(auth),
    Depends(permissions("delete:api_key"))
])
async def delete(api_key_id: UUID, service: ApiKeysService = Depends()):
    return await service.delete(api_key_id)

@router.patch("/{api_key_id}", response_model=ApiKeyRead, dependencies=[
    Depends(auth),
    Depends(permissions("update:api_key"))
])
async def update(request: Request, api_key_id: UUID, api_key_data: ApiKeyUpdate, service: ApiKeysService =
Depends()):
    return await service.update(api_key_id, api_key_data)
