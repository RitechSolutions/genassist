import logging
from uuid import UUID

from injector import inject
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.db.models.llm_cost_rate import LlmCostRateModel
from app.repositories.db_repository import DbRepository

logger = logging.getLogger(__name__)


@inject
class LlmCostRateRepository(DbRepository[LlmCostRateModel]):
    def __init__(self, db: AsyncSession):
        super().__init__(LlmCostRateModel, db)

    async def create(self, obj: LlmCostRateModel) -> LlmCostRateModel:
        # SAVEPOINT so a duplicate only rolls back this insert, not the whole
        # request/task transaction (repos no longer own the commit boundary).
        try:
            async with self.db.begin_nested():
                return await super().create(obj)
        except IntegrityError as e:
            logger.warning("Duplicate active LLM cost rate rejected by the database: %s", e)
            raise AppException(error_key=ErrorKey.LLM_COST_RATE_ALREADY_EXISTS, status_code=409) from e

    async def list_active(self) -> list[LlmCostRateModel]:
        result = await self.db.execute(
            select(LlmCostRateModel)
            .where(LlmCostRateModel.is_deleted == 0)
            .order_by(
                LlmCostRateModel.provider_key, LlmCostRateModel.model_key
            )
        )
        return list(result.scalars().all())

    async def get_active_by_id(self, rate_id: UUID) -> LlmCostRateModel | None:
        result = await self.db.execute(
            select(LlmCostRateModel).where(
                LlmCostRateModel.id == rate_id,
                LlmCostRateModel.is_deleted == 0,
            )
        )
        return result.scalar_one_or_none()

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
        await self.db.flush()
        return True
