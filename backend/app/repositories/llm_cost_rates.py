from injector import inject
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.llm_cost_rate import LlmCostRateModel


@inject
class LlmCostRateRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_active(self) -> list[LlmCostRateModel]:
        result = await self.db.execute(
            select(LlmCostRateModel).order_by(
                LlmCostRateModel.provider_key, LlmCostRateModel.model_key
            )
        )
        return list(result.scalars().all())

    async def get_active_by_provider_model(
        self, provider_key: str, model_key: str
    ) -> LlmCostRateModel | None:
        result = await self.db.execute(
            select(LlmCostRateModel).where(
                LlmCostRateModel.provider_key == provider_key,
                LlmCostRateModel.model_key == model_key,
            )
        )
        return result.scalar_one_or_none()
