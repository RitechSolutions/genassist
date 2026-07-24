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
        result = await self.db.execute(
            select(LlmUsageControlModel).where(LlmUsageControlModel.singleton_key == CONTROL_SINGLETON_KEY)
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

    async def start_shadow(self) -> LlmUsageControlModel | None:
        await self.db.execute(
            update(LlmUsageControlModel)
            .where(LlmUsageControlModel.singleton_key == CONTROL_SINGLETON_KEY)
            .values(shadow_started_at=func.now())
        )
        await self.db.commit()
        return await self.get_singleton()

    async def mark_shadow_passed(self) -> LlmUsageControlModel | None:
        """Stamp the pass once. Guarded so a later run can't move an existing stamp"""
        await self.db.execute(
            update(LlmUsageControlModel)
            .where(
                LlmUsageControlModel.singleton_key == CONTROL_SINGLETON_KEY,
                LlmUsageControlModel.shadow_passed_at.is_(None),
            )
            .values(shadow_passed_at=func.now())
        )
        await self.db.commit()
        return await self.get_singleton()

    async def set_cutover(self, enabled: bool) -> LlmUsageControlModel | None:
        await self.db.execute(
            update(LlmUsageControlModel)
            .where(LlmUsageControlModel.singleton_key == CONTROL_SINGLETON_KEY)
            .values(ledger_cutover_enabled=enabled)
        )
        await self.db.commit()
        return await self.get_singleton()
