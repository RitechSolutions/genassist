from typing import List

from injector import inject
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models.workflow import WorkflowModel
from app.repositories.db_repository import DbRepository

@inject
class WorkflowRepository(DbRepository[WorkflowModel]):
    def __init__(self, db: AsyncSession):
        super().__init__(WorkflowModel, db)

    async def get_all_minimal(self) -> List[WorkflowModel]:
        stmt = select(
            WorkflowModel.id,
            WorkflowModel.name,
            WorkflowModel.version,
        )
        if hasattr(WorkflowModel, "is_deleted"):
            stmt = stmt.where(WorkflowModel.is_deleted == 0)
        result = await self.db.execute(stmt)
        return result.all()
