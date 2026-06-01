"""Resolve agent ID lists for analytics filters (single agent, group, or all)."""

from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.events.group_scope import GROUP_SCOPE_BYPASS_FLAG
from app.db.models.agent import AgentModel
from app.db.models.operator import OperatorModel
from app.db.models.user import UserModel
from app.db.models.workflow import WorkflowModel


def _users_in_group_subquery(group_id: UUID):
    return select(UserModel.id).where(
        UserModel.group_id == group_id,
        UserModel.is_deleted == 0,
    )


def _agents_for_group_clause(group_id: UUID):
    """Agents belonging to a group via operator user, creator, or workflow owner."""
    users_in_group = _users_in_group_subquery(group_id)
    return or_(
        AgentModel.created_by.in_(users_in_group),
        OperatorModel.user_id.in_(users_in_group),
        WorkflowModel.user_id.in_(users_in_group),
    )


async def get_agent_ids_for_group(db: AsyncSession, group_id: UUID) -> list[UUID]:
    stmt = (
        select(AgentModel.id)
        .outerjoin(OperatorModel, AgentModel.operator_id == OperatorModel.id)
        .outerjoin(WorkflowModel, AgentModel.workflow_id == WorkflowModel.id)
        .where(
            AgentModel.is_deleted == 0,
            _agents_for_group_clause(group_id),
        )
        .distinct()
    )
    stmt = stmt.execution_options(**{GROUP_SCOPE_BYPASS_FLAG: True})
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def resolve_scoped_agent_ids(
    db: AsyncSession,
    agent_id: UUID | None = None,
    group_id: UUID | None = None,
) -> list[UUID] | None:
    """
    None — no explicit agent restriction (all agents in scope).
    [] — empty scope (no matching agents).
    [...] — restrict queries to these agent IDs.
    """
    if agent_id is not None:
        if group_id is not None:
            group_agent_ids = await get_agent_ids_for_group(db, group_id)
            return [agent_id] if agent_id in group_agent_ids else []
        return [agent_id]
    if group_id is not None:
        return await get_agent_ids_for_group(db, group_id)
    return None


async def get_agents_for_group(db: AsyncSession, group_id: UUID) -> list[dict]:
    """Id/name pairs for agents in a group (analytics agent dropdown)."""
    stmt = (
        select(AgentModel.id, AgentModel.name)
        .outerjoin(OperatorModel, AgentModel.operator_id == OperatorModel.id)
        .outerjoin(WorkflowModel, AgentModel.workflow_id == WorkflowModel.id)
        .where(
            AgentModel.is_deleted == 0,
            _agents_for_group_clause(group_id),
        )
        .distinct()
        .order_by(AgentModel.name)
    )
    stmt = stmt.execution_options(**{GROUP_SCOPE_BYPASS_FLAG: True})
    result = await db.execute(stmt)
    return [{"id": row.id, "name": row.name} for row in result.all()]
