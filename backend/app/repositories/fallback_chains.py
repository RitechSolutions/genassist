from uuid import UUID

from injector import inject
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.models.fallback_chain import FallbackChainModel


@inject
class FallbackChainRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, data):
        obj = FallbackChainModel(**data)
        self.db.add(obj)
        await self.db.commit()
        await self.db.refresh(obj)
        return obj

    async def get_by_id(self, chain_id: UUID):
        return await self.db.get(FallbackChainModel, chain_id)

    async def update(self, obj: FallbackChainModel):
        self.db.add(obj)
        await self.db.commit()
        await self.db.refresh(obj)
        return obj

    async def delete(self, obj: FallbackChainModel):
        await self.db.delete(obj)
        await self.db.commit()

    async def get_all(self):
        result = await self.db.execute(
            select(FallbackChainModel)
            .where(FallbackChainModel.is_deleted == 0)
            .order_by(FallbackChainModel.created_at.asc())
        )
        return result.scalars().all()

    async def get_all_minimal(self):
        stmt = (
            select(
                FallbackChainModel.id,
                FallbackChainModel.name,
                FallbackChainModel.is_active,
            )
            .where(FallbackChainModel.is_deleted == 0)
            .order_by(FallbackChainModel.created_at.asc())
        )
        result = await self.db.execute(stmt)
        return result.all()
