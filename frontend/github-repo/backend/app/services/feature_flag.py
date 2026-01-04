from typing import List
from uuid import UUID
from injector import inject

from app.repositories.feature_flag import FeatureFlagRepository
from app.schemas.feature_flag import (
    FeatureFlagCreate,
    FeatureFlagUpdate,
    FeatureFlagRead,
)
from app.core.exceptions.exception_classes import AppException
from app.core.exceptions.error_messages import ErrorKey

@inject
class FeatureFlagService:
    def __init__(self, repo: FeatureFlagRepository):
        self.repo = repo

    async def get_all(self) -> List[FeatureFlagRead]:
        rows = await self.repo.get_all()
        return [
            FeatureFlagRead.model_validate(r, from_attributes=True) for r in rows
        ]

    async def get_by_id(self, id: UUID) -> FeatureFlagRead:
        row = await self.repo.get_by_id(id)
        if not row:
            raise AppException(
                status_code=404, error_key=ErrorKey.FEATURE_FLAG_NOT_FOUND
            )
        return FeatureFlagRead.model_validate(row, from_attributes=True)

    async def create(self, dto: FeatureFlagCreate) -> FeatureFlagRead:
        row = await self.repo.create(dto)
        return FeatureFlagRead.model_validate(row, from_attributes=True)

    async def update(self, id: UUID, dto: FeatureFlagUpdate) -> FeatureFlagRead:
        existing = await self.repo.get_by_id(id)
        if not existing:
            raise AppException(
                status_code=404, error_key=ErrorKey.FEATURE_FLAG_NOT_FOUND
            )
        updated = await self.repo.update(id, dto)
        return FeatureFlagRead.model_validate(updated, from_attributes=True)

    async def delete(self, id: UUID):
        existing = await self.repo.get_by_id(id)
        if not existing:
            raise AppException(
                status_code=404, error_key=ErrorKey.FEATURE_FLAG_NOT_FOUND
            )
        await self.repo.delete(id)
