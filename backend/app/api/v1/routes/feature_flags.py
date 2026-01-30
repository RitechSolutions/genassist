from fastapi import APIRouter, Depends, status
from typing import List
from uuid import UUID

from fastapi_injector import Injected

from app.schemas.feature_flag import (
    FeatureFlagCreate,
    FeatureFlagUpdate,
    FeatureFlagRead,
)
from app.services.feature_flag import FeatureFlagService
from app.auth.dependencies import auth, permissions
from app.core.permissions.constants import Permissions as P

router = APIRouter()

@router.get(
    "", response_model=List[FeatureFlagRead],
    dependencies=[Depends(auth), Depends(permissions(P.FeatureFlag.READ))]
)
async def list_feature_flags(svc: FeatureFlagService = Injected(FeatureFlagService)):
    return await svc.get_all()

@router.get(
    "/{flag_id}", response_model=FeatureFlagRead,
    dependencies=[Depends(auth), Depends(permissions(P.FeatureFlag.READ))]
)
async def get_feature_flag(flag_id: UUID, svc: FeatureFlagService = Injected(FeatureFlagService)):
    return await svc.get_by_id(flag_id)

@router.post(
    "", response_model=FeatureFlagRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(auth), Depends(permissions(P.FeatureFlag.CREATE))]
)
async def create_feature_flag(
    dto: FeatureFlagCreate, svc: FeatureFlagService = Injected(FeatureFlagService)
):
    return await svc.create(dto)

@router.patch(
    "/{flag_id}", response_model=FeatureFlagRead,
    response_model_exclude_none=True,
    dependencies=[Depends(auth), Depends(permissions(P.FeatureFlag.UPDATE))]
)
async def update_feature_flag(
    flag_id: UUID, dto: FeatureFlagUpdate, svc: FeatureFlagService = Injected(FeatureFlagService)
):
    return await svc.update(flag_id, dto)

@router.delete(
    "/{flag_id}", status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(auth), Depends(permissions(P.FeatureFlag.DELETE))]
)
async def delete_feature_flag(flag_id: UUID, svc: FeatureFlagService = Injected(FeatureFlagService)):
    await svc.delete(flag_id)
