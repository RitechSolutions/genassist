from typing import List
from uuid import UUID

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
            WorkflowModel.agent_id,
        )
        if hasattr(WorkflowModel, "is_deleted"):
            stmt = stmt.where(WorkflowModel.is_deleted == 0)
        result = await self.db.execute(stmt)
        return result.all()

    async def get_minimal_by_ids(self, ids: List[UUID]) -> List:
        if not ids:
            return []
        stmt = select(
            WorkflowModel.id,
            WorkflowModel.name,
            WorkflowModel.version,
            WorkflowModel.agent_id,
        ).where(WorkflowModel.id.in_(ids))
        if hasattr(WorkflowModel, "is_deleted"):
            stmt = stmt.where(WorkflowModel.is_deleted == 0)
        result = await self.db.execute(stmt)
        return result.all()

    async def get_summaries_by_agent(self, agent_id: UUID) -> List:
        stmt = (
            select(
                WorkflowModel.id,
                WorkflowModel.name,
                WorkflowModel.description,
                WorkflowModel.version,
                WorkflowModel.agent_id,
                WorkflowModel.created_at,
                WorkflowModel.updated_at,
                WorkflowModel.created_by,
                WorkflowModel.updated_by,
            )
            .where(WorkflowModel.agent_id == agent_id)
            .order_by(WorkflowModel.created_at.desc())
        )
        if hasattr(WorkflowModel, "is_deleted"):
            stmt = stmt.where(WorkflowModel.is_deleted == 0)
        result = await self.db.execute(stmt)
        return result.all()
