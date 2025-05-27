from uuid import UUID
from typing import List, Optional
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.session import get_db
from app.db.models.app_settings import AppSettingsModel
from app.schemas.app_settings import AppSettingsCreate, AppSettingsUpdate

class AppSettingsRepository:
    def __init__(self, db: AsyncSession = Depends(get_db)):
        self.db = db

    async def create(self, dto: AppSettingsCreate) -> AppSettingsModel:
        obj = AppSettingsModel(**dto.model_dump())
        self.db.add(obj)
        await self.db.commit()
        await self.db.refresh(obj)
        return obj

    async def get_by_id(self, id: UUID) -> Optional[AppSettingsModel]:
        return await self.db.get(AppSettingsModel, id)

    async def update(self, id: UUID, dto: AppSettingsUpdate) -> Optional[AppSettingsModel]:
        obj = await self.db.get(AppSettingsModel, id)
        if not obj:
            return None
        for field, val in dto.model_dump(exclude_unset=True).items():
            setattr(obj, field, val)
        await self.db.commit()
        await self.db.refresh(obj)
        return obj

    async def delete(self, id: UUID) -> bool:
        obj = await self.db.get(AppSettingsModel, id)
        if not obj:
            return False
        await self.db.delete(obj)
        await self.db.commit()
        return True

    async def get_all(self) -> List[AppSettingsModel]:
        result = await self.db.execute(select(AppSettingsModel))
        return result.scalars().all()
