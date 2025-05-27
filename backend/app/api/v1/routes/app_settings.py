from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from uuid import UUID

from app.schemas.app_settings import (
    AppSettingsCreate, AppSettingsUpdate, AppSettingsRead
)
from app.services.app_settings import AppSettingsService
from app.auth.dependencies import auth, permissions

router = APIRouter()

@router.get("/", response_model=List[AppSettingsRead],
            dependencies=[Depends(auth), Depends(permissions("read:app-settings"))])
async def list_settings(svc: AppSettingsService = Depends()):
    return await svc.get_all()

@router.get("/{setting_id}", response_model=AppSettingsRead,
            dependencies=[Depends(auth), Depends(permissions("read:app-settings"))])
async def get_setting(setting_id: UUID, svc: AppSettingsService = Depends()):
    return await svc.get_by_id(setting_id)

@router.post("/", response_model=AppSettingsRead, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(auth), Depends(permissions("create:app-settings"))])
async def create_setting(dto: AppSettingsCreate, svc: AppSettingsService = Depends()):
    return await svc.create(dto)

@router.patch(
    "/{setting_id}",
    response_model=AppSettingsRead,
    response_model_exclude_none=True,
    dependencies=[Depends(auth), Depends(permissions("update:app-settings"))]
)
async def update_setting(setting_id: UUID, dto: AppSettingsUpdate, svc: AppSettingsService = Depends()):
    return await svc.update(setting_id, dto)


@router.delete("/{setting_id}", status_code=status.HTTP_204_NO_CONTENT,
               dependencies=[Depends(auth), Depends(permissions("delete:app-settings"))])
async def delete_setting(setting_id: UUID, svc: AppSettingsService = Depends()):
    await svc.delete(setting_id)
