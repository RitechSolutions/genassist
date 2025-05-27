from typing import List
from uuid import UUID
from fastapi import Depends

from app.repositories.app_settings import AppSettingsRepository
from app.schemas.app_settings import AppSettingsCreate, AppSettingsUpdate, AppSettingsRead
from app.core.exceptions.exception_classes import AppException
from app.core.exceptions.error_messages import ErrorKey

class AppSettingsService:
    def __init__(self, repo: AppSettingsRepository = Depends()):
        self.repo = repo

    async def get_all(self) -> List[AppSettingsRead]:
        rows = await self.repo.get_all()
        return [AppSettingsRead.model_validate(r, from_attributes=True) for r in rows]

    async def get_by_id(self, id: UUID) -> AppSettingsRead:
        row = await self.repo.get_by_id(id)
        if not row:
            raise AppException(status_code=404, error_key=ErrorKey.APP_SETTINGS_NOT_FOUND)
        return AppSettingsRead.model_validate(row, from_attributes=True)

    async def create(self, dto: AppSettingsCreate) -> AppSettingsRead:
        row = await self.repo.create(dto)
        return AppSettingsRead.model_validate(row, from_attributes=True)

    async def update(self, id: UUID, dto: AppSettingsUpdate) -> AppSettingsRead:
        existing = await self.repo.get_by_id(id)
        if not existing:
            raise AppException(status_code=404, error_key=ErrorKey.APP_SETTINGS_NOT_FOUND)
        updated = await self.repo.update(id, dto)
        return AppSettingsRead.model_validate(updated, from_attributes=True)

    async def delete(self, id: UUID):
        existing = await self.repo.get_by_id(id)
        if not existing:
            raise AppException(status_code=404, error_key=ErrorKey.APP_SETTINGS_NOT_FOUND)
        await self.repo.delete(id)
