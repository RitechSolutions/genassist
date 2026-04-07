from uuid import UUID

from injector import inject
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.llm_cost_rate import LlmCostRateModel


@inject
class LlmCostRateRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_active(self) -> list[LlmCostRateModel]:
        result = await self.db.execute(
            select(LlmCostRateModel)
            .where(LlmCostRateModel.is_deleted == 0)
            .order_by(
                LlmCostRateModel.provider_key, LlmCostRateModel.model_key
            )
        )
        return list(result.scalars().all())

    async def get_active_by_provider_model(
        self, provider_key: str, model_key: str
    ) -> LlmCostRateModel | None:
        provider_key = (provider_key or "").strip().lower()
        model_key = (model_key or "").strip().lower()
        result = await self.db.execute(
            select(LlmCostRateModel).where(
                func.lower(func.trim(LlmCostRateModel.provider_key)) == provider_key,
                func.lower(func.trim(LlmCostRateModel.model_key)) == model_key,
                LlmCostRateModel.is_deleted == 0,
            )
        )
        return result.scalar_one_or_none()

    async def soft_delete_by_id(self, rate_id: UUID) -> bool:
        result = await self.db.execute(
            select(LlmCostRateModel).where(
                LlmCostRateModel.id == rate_id,
                LlmCostRateModel.is_deleted == 0,
            )
        )
        row = result.scalar_one_or_none()
        if not row:
            return False
        row.is_deleted = 1
        await self.db.commit()
        return True
