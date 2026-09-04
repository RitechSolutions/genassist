from injector import inject
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from sqlalchemy.orm import joinedload
from starlette_context import context
from app.db.models.llm import LlmAnalystModel
from app.repositories.db_repository import DbRepository
from app.schemas.llm import LlmAnalystCreate

@inject
class LlmAnalystRepository(DbRepository[LlmAnalystModel]):
    def __init__(self, db: AsyncSession):
        super().__init__(LlmAnalystModel, db)

    async def create(self, data: LlmAnalystCreate) -> LlmAnalystModel:
        obj = LlmAnalystModel(**data.model_dump())
        self.db.add(obj)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj


    async def get_by_id(self, llm_analyst_id: UUID, include_inactive: bool = False):
        query = (
            select(LlmAnalystModel)
            .options(
                    joinedload(LlmAnalystModel.llm_provider)
                    )
            .where(LlmAnalystModel.id == llm_analyst_id)
        )
        if not include_inactive:
            query = query.where(LlmAnalystModel.is_active == 1)
        result = await self.db.execute(query)
        return result.scalars().first()


    async def update(self, obj: LlmAnalystModel):
        obj.updated_by = context["user_id"]
        self.db.add(obj)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj

    async def get_all(self):
        result = await self.db.execute(
            select(LlmAnalystModel)
            .options(joinedload(LlmAnalystModel.llm_provider))
            .order_by(LlmAnalystModel.created_at.asc())
        )
        return result.scalars().all()
