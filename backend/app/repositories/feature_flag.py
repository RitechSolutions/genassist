from uuid import UUID
from typing import List, Optional
from injector import inject
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.db.models.feature_flag import FeatureFlagModel
from app.schemas.feature_flag import FeatureFlagCreate, FeatureFlagUpdate

@inject
class FeatureFlagRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, dto: FeatureFlagCreate) -> FeatureFlagModel:
        obj = FeatureFlagModel(**dto.model_dump())
        self.db.add(obj)
        await self.db.commit()
        await self.db.refresh(obj)
        return obj

    async def get_by_id(self, id: UUID) -> Optional[FeatureFlagModel]:
        return await self.db.get(FeatureFlagModel, id)

    async def get_all(self) -> List[FeatureFlagModel]:
        result = await self.db.execute(select(FeatureFlagModel))
        return result.scalars().all()

    async def update(
        self, id: UUID, dto: FeatureFlagUpdate
    ) -> Optional[FeatureFlagModel]:
        obj = await self.db.get(FeatureFlagModel, id)
        if not obj:
            return None
        for field, val in dto.model_dump(exclude_unset=True).items():
            setattr(obj, field, val)
        await self.db.commit()
        await self.db.refresh(obj)
        return obj

    async def delete(self, id: UUID) -> bool:
        obj = await self.db.get(FeatureFlagModel, id)
        if not obj:
            return False
        await self.db.delete(obj)
        await self.db.commit()
        return True
