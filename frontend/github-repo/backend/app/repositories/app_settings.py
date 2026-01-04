from uuid import UUID
from typing import List, Optional
from injector import inject
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_
from sqlalchemy.exc import IntegrityError
from app.db.models.app_settings import AppSettingsModel
from app.schemas.app_settings import AppSettingsCreate, AppSettingsUpdate


@inject
class AppSettingsRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, dto: AppSettingsCreate) -> AppSettingsModel:
        # Exclude 'id' from model_dump if present, as it should be auto-generated
        # Also exclude any fields that shouldn't be set manually (like timestamps)
        obj = AppSettingsModel(
            name=dto.name,
            type=dto.type,
            values=dto.values,
            description=dto.description,
            is_active=dto.is_active,
        )
        self.db.add(obj)
        await self.db.commit()
        await self.db.refresh(obj)
        return obj

    async def get_by_id(self, id: UUID) -> Optional[AppSettingsModel]:
        return await self.db.get(AppSettingsModel, id)

    async def get_by_type_and_name(
        self, setting_type: str, name: str
    ) -> Optional[AppSettingsModel]:
        """Get app setting by type and name."""
        query = select(AppSettingsModel).where(
            and_(AppSettingsModel.type == setting_type, AppSettingsModel.name == name)
        )
        result = await self.db.execute(query)
        return result.scalars().first()

    async def get_by_type(self, setting_type: str) -> List[AppSettingsModel]:
        """Get all app settings of a given type."""
        query = select(AppSettingsModel).where(AppSettingsModel.type == setting_type)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update(
        self, id: UUID, dto: AppSettingsUpdate
    ) -> Optional[AppSettingsModel]:
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
        result = await self.db.execute(
            select(AppSettingsModel).order_by(AppSettingsModel.created_at.asc())
        )
        return list(result.scalars().all())
