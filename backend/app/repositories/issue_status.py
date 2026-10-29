from typing import Optional

from injector import inject
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.issue_status import IssueStatusModel
from app.repositories.db_repository import DbRepository


@inject
class IssueStatusRepository(DbRepository[IssueStatusModel]):
    def __init__(self, db: AsyncSession):
        super().__init__(IssueStatusModel, db)

    async def list_ordered(self) -> list[IssueStatusModel]:
        result = await self.db.execute(
            select(IssueStatusModel).order_by(IssueStatusModel.position, IssueStatusModel.key)
        )
        return list(result.scalars().all())

    async def get_by_key(self, key: str) -> Optional[IssueStatusModel]:
        result = await self.db.execute(select(IssueStatusModel).where(IssueStatusModel.key == key))
        return result.scalars().first()

    async def max_position(self) -> int:
        position = await self.db.scalar(select(func.max(IssueStatusModel.position)))
        return -1 if position is None else position

    async def set_positions(self, keys: list[str]) -> None:
        statuses = {status.key: status for status in await self.list_ordered()}
        for position, key in enumerate(keys):
            statuses[key].position = position
        await self.db.flush()
