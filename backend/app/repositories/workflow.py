from typing import List
from uuid import UUID

from injector import inject
from sqlalchemy import and_, case, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.events.group_scope import GROUP_SCOPE_BYPASS_FLAG, get_group_scope_clause
from app.db.models.agent import AgentModel
from app.db.models.workflow import WorkflowModel
from app.repositories.db_repository import DbRepository

@inject
class WorkflowRepository(DbRepository[WorkflowModel]):
    def __init__(self, db: AsyncSession):
        super().__init__(WorkflowModel, db)

    @staticmethod
    def _visible_agent():
        """An agent the caller may see: live, and inside their groups."""
        clause = AgentModel.is_deleted == 0
        scope_clause = get_group_scope_clause(AgentModel)
        return clause if scope_clause is None else and_(clause, scope_clause)

    def _minimal_select(self):
        """Minimal workflow columns, the active-version flag, and the owning
        agent's identity.

        The automatic agent scope filter is bypassed so the active-version
        pointer reads the same for every caller; scoping is applied explicitly
        instead. The agent's name is a scoped column, so it is nulled for agents
        outside the caller's groups on every path.
        """
        is_active_version = case(
            (AgentModel.workflow_id == WorkflowModel.id, True), else_=False
        ).label("is_active_version")
        agent_name = case((self._visible_agent(), AgentModel.name), else_=None).label(
            "agent_name"
        )
        stmt = select(
            WorkflowModel.id,
            WorkflowModel.name,
            WorkflowModel.version,
            WorkflowModel.agent_id,
            is_active_version,
            agent_name,
        ).outerjoin(AgentModel, AgentModel.id == WorkflowModel.agent_id)
        if hasattr(WorkflowModel, "is_deleted"):
            stmt = stmt.where(WorkflowModel.is_deleted == 0)
        return stmt.execution_options(**{GROUP_SCOPE_BYPASS_FLAG: True})

    async def get_all_minimal(self) -> List[WorkflowModel]:
        """Every workflow. Internal callers rely on seeing them all, e.g. to find
        a workflow's sibling versions; user-facing lists use the visible variant."""
        result = await self.db.execute(self._minimal_select())
        return result.all()

    async def get_visible_minimal(self) -> List[WorkflowModel]:
        """Workflows whose agent the caller can see, as Agent Studio lists them.

        A workflow with no live agent of its own — a row created without one, or
        a leftover from a deleted agent — is not listed, since there is no agent
        to see it under.
        """
        stmt = self._minimal_select().where(self._visible_agent())
        result = await self.db.execute(stmt)
        return result.all()

    async def get_minimal_by_ids(self, ids: List[UUID]) -> List:
        """Point lookup by id — not scoped, so a stored reference still resolves
        to a name (e.g. labelling an existing run)."""
        if not ids:
            return []
        stmt = self._minimal_select().where(WorkflowModel.id.in_(ids))
        result = await self.db.execute(stmt)
        return result.all()

    async def soft_delete_by_agent(self, agent_id: UUID, commit: bool = True) -> None:
        """Retire every version of an agent's workflow.

        Each version is a separate row, so deleting the agent leaves them all
        behind. Skip the commit to batch this with the agent's own delete.
        """
        await self.db.execute(
            update(WorkflowModel)
            .where(WorkflowModel.agent_id == agent_id)
            .values(is_deleted=1)
            .execution_options(synchronize_session="fetch")
        )
        if commit:
            await self.db.flush()

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
