from typing import Tuple
from uuid import UUID
from injector import inject
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload
from app.db.events.group_scope import GROUP_SCOPE_BYPASS_FLAG, get_group_scope_clause
from app.db.models import AgentModel, OperatorModel
from app.repositories.db_repository import DbRepository
from app.schemas.filter import BaseFilterModel

@inject
class AgentRepository(DbRepository[AgentModel]):

    def __init__(self, db: AsyncSession):
        super().__init__(AgentModel, db)


    async def get_by_id_full(self, agent_id: UUID) -> AgentModel | None:
        """
        Return the Agent row with operator, workflow, and security_settings
        eagerly loaded.
        """
        stmt = select(AgentModel).options(
                joinedload(AgentModel.operator).joinedload(OperatorModel.user),
                selectinload(AgentModel.workflow),  # separate query avoids cartesian product with other joins
                joinedload(AgentModel.security_settings)
            ).where(AgentModel.id == agent_id)
        stmt = stmt.execution_options(**{GROUP_SCOPE_BYPASS_FLAG: True})
        result = await self.db.execute(stmt)
        return result.scalars().first()


    async def get_all_full(self) -> list[AgentModel]:
        """
        Return the Agent row *with* agent_tools and agent_knowledge_bases
        eagerly loaded in a single round‑trip.
        """
        result = await self.db.execute(
            select(AgentModel)
            .options(
                joinedload(AgentModel.operator).joinedload(OperatorModel.user),
                joinedload(AgentModel.workflow),
                joinedload(AgentModel.security_settings)
            )
            .order_by(AgentModel.created_at.asc())
        )
        return result.scalars().all()


    async def get_by_user_id(self,
                             user_id: UUID,
                             with_workflow: bool = False
                             ) -> AgentModel:
        options = [
            joinedload(AgentModel.operator).joinedload(OperatorModel.user),
            joinedload(AgentModel.security_settings),
        ]
        if with_workflow:
            options.append(joinedload(AgentModel.workflow))

        stmt = (
            select(AgentModel)
            .join(OperatorModel)
            .where(OperatorModel.user_id == user_id)
            .options(*options)
        )
        stmt = stmt.execution_options(**{GROUP_SCOPE_BYPASS_FLAG: True})
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def get_list_paginated(
        self, filter_obj: BaseFilterModel, is_system: bool | None = None
    ) -> Tuple[list[AgentModel], int]:
        """
        Return minimal agent data for list view with pagination.
        Only loads columns needed for the list display (no relationships).
        Returns tuple of (agents, total_count).
        """
        group_clause = get_group_scope_clause(AgentModel)

        # Count query - get total without loading data
        count_stmt = select(func.count(AgentModel.id)).where(AgentModel.is_deleted == 0)
        if group_clause is not None:
            count_stmt = count_stmt.where(group_clause)
        if is_system is not None:
            count_stmt = count_stmt.where(AgentModel.is_system == is_system)
        count_result = await self.db.execute(count_stmt)
        total = count_result.scalar() or 0

        # Data query - only select minimal columns needed for list view
        data_stmt = select(
            AgentModel.id,
            AgentModel.name,
            AgentModel.workflow_id,
            AgentModel.possible_queries,
            AgentModel.is_active,
            AgentModel.is_system,
        ).where(AgentModel.is_deleted == 0)
        if group_clause is not None:
            data_stmt = data_stmt.where(group_clause)
        if is_system is not None:
            data_stmt = data_stmt.where(AgentModel.is_system == is_system)

        # System agents first, then apply user-requested sorting
        data_stmt = data_stmt.order_by(AgentModel.is_system.desc())
        data_stmt = self._apply_sorting(data_stmt, filter_obj)

        # Apply pagination using base repository method
        data_stmt = self._apply_pagination(data_stmt, filter_obj)

        result = await self.db.execute(data_stmt)
        rows = result.all()

        return rows, total
