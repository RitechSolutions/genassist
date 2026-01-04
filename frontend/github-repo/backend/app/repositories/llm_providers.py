from injector import inject
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from uuid import UUID
from app.db.models.llm import LlmProvidersModel

@inject
class LlmProviderRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, data):
        obj = LlmProvidersModel(**data.model_dump())
        self.db.add(obj)
        await self.db.commit()
        await self.db.refresh(obj)
        return obj

    async def get_by_id(self, llm_provider_id: UUID):
        return await self.db.get(LlmProvidersModel, llm_provider_id)

    async def update(self, obj: LlmProvidersModel):
        self.db.add(obj)
        await self.db.commit()
        await self.db.refresh(obj)
        return obj

    async def delete(self, obj: LlmProvidersModel):
        await self.db.delete(obj)
        await self.db.commit()

    async def get_all(self):
        result = await self.db.execute(
            select(LlmProvidersModel)
            .order_by(LlmProvidersModel.created_at.asc())
        )
        return result.scalars().all()
