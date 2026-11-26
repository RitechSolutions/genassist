from uuid import UUID

from injector import inject
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.guardrail_event import GuardrailEventModel
from app.repositories.db_repository import DbRepository


@inject
class GuardrailEventRepository(DbRepository[GuardrailEventModel]):
    def __init__(self, db: AsyncSession):
        super().__init__(GuardrailEventModel, db)

    async def add_many(self, rows: list[GuardrailEventModel]) -> None:
        # A failed insert rolls back alone, so the turn's own writes survive
        async with self.db.begin_nested():
            self.db.add_all(rows)
            await self.db.flush()

    async def list_by_conversation(self, conversation_id: UUID) -> list[GuardrailEventModel]:
        stmt = (
            select(GuardrailEventModel)
            .where(GuardrailEventModel.conversation_id == conversation_id)
            .order_by(GuardrailEventModel.created_at)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
