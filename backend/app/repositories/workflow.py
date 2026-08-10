from typing import List
from uuid import UUID

from injector import inject
from sqlalchemy import case, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.events.group_scope import GROUP_SCOPE_BYPASS_FLAG
from app.db.models.agent import AgentModel
from app.db.models.workflow import WorkflowModel
from app.repositories.db_repository import DbRepository

@inject
class WorkflowRepository(DbRepository[WorkflowModel]):
    def __init__(self, db: AsyncSession):
        super().__init__(WorkflowModel, db)

    def _minimal_select(self):
        """Minimal workflow columns plus whether this row is its agent's live
        version — the one the builder marks Active.

        Agents are group-scoped but workflows are not, so the scope filter is
        bypassed for the join; otherwise the same version would look active to
        some callers and not to others. Only the pointer is read.
        """
        is_active_version = case(
            (AgentModel.workflow_id == WorkflowModel.id, True), else_=False
        ).label("is_active_version")
        stmt = select(
            WorkflowModel.id,
            WorkflowModel.name,
            WorkflowModel.version,
            WorkflowModel.agent_id,
            is_active_version,
        ).outerjoin(AgentModel, AgentModel.id == WorkflowModel.agent_id)
        if hasattr(WorkflowModel, "is_deleted"):
            stmt = stmt.where(WorkflowModel.is_deleted == 0)
        return stmt.execution_options(**{GROUP_SCOPE_BYPASS_FLAG: True})

    async def get_all_minimal(self) -> List[WorkflowModel]:
        result = await self.db.execute(self._minimal_select())
        return result.all()

    async def get_minimal_by_ids(self, ids: List[UUID]) -> List:
        if not ids:
            return []
        stmt = self._minimal_select().where(WorkflowModel.id.in_(ids))
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
