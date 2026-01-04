from injector import inject
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from sqlalchemy.orm import joinedload
from starlette_context import context
from app.db.models.llm import LlmAnalystModel
from app.schemas.llm import LlmAnalystCreate

@inject
class LlmAnalystRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, data: LlmAnalystCreate) -> LlmAnalystModel:
        obj = LlmAnalystModel(**data.model_dump())
        self.db.add(obj)
        await self.db.commit()
        await self.db.refresh(obj)
        return obj


    async def get_by_id(self, llm_analyst_id: UUID):
        query = (
            select(LlmAnalystModel)
            .options(
                    joinedload(LlmAnalystModel.llm_provider)
                    )
            .where(LlmAnalystModel.id == llm_analyst_id)
        )
        result = await self.db.execute(query)
        return result.scalars().first()


    async def update(self, obj: LlmAnalystModel):
        obj.updated_by = context["user_id"]
        self.db.add(obj)
        await self.db.commit()
        await self.db.refresh(obj)
        return obj

    async def delete(self, obj: LlmAnalystModel):
        await self.db.delete(obj)
        await self.db.commit()

    async def get_all(self):
        result = await self.db.execute(
            select(LlmAnalystModel)
            .options(joinedload(LlmAnalystModel.llm_provider))
            .order_by(LlmAnalystModel.created_at.asc())
        )
        return result.scalars().all()
