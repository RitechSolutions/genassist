from injector import inject
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.llm_usage import CONTROL_SINGLETON_KEY, LlmUsageControlModel
from app.repositories.db_repository import DbRepository


@inject
class LlmUsageControlRepository(DbRepository[LlmUsageControlModel]):
    """Reads and mutates the single LLM-usage control row"""

    def __init__(self, db: AsyncSession):
        super().__init__(LlmUsageControlModel, db)

    async def get_singleton(self) -> LlmUsageControlModel | None:
        """Always read the row as the database has it"""
        result = await self.db.execute(
            select(LlmUsageControlModel)
            .where(LlmUsageControlModel.singleton_key == CONTROL_SINGLETON_KEY)
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def activate_capture(self) -> LlmUsageControlModel | None:
        """One-way activation. COALESCE keeps any existing stamp so the backfill
        boundary is fixed on first activation and never moves on a repeat call."""
        await self.db.execute(
            update(LlmUsageControlModel)
            .where(LlmUsageControlModel.singleton_key == CONTROL_SINGLETON_KEY)
            .values(
                capture_enabled=True,
                capture_started_at=func.coalesce(LlmUsageControlModel.capture_started_at, func.now()),
            )
        )
        await self.db.commit()
        return await self.get_singleton()
