from injector import inject
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from uuid import UUID
from app.db.models.llm import LlmProvidersModel
from app.repositories.db_repository import DbRepository

@inject
class LlmProviderRepository(DbRepository[LlmProvidersModel]):
    def __init__(self, db: AsyncSession):
        super().__init__(LlmProvidersModel, db)

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

    async def get_all_minimal(self):
        stmt = select(
            LlmProvidersModel.id,
            LlmProvidersModel.name,
            LlmProvidersModel.llm_model_provider,
            LlmProvidersModel.llm_model,
            LlmProvidersModel.is_active,
        )
        if hasattr(LlmProvidersModel, "is_deleted"):
            stmt = stmt.where(LlmProvidersModel.is_deleted == 0)
        stmt = stmt.order_by(LlmProvidersModel.created_at.asc())
        result = await self.db.execute(stmt)
        return result.all()
