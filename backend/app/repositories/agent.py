from typing import Tuple
from uuid import UUID
from injector import inject
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from app.db.models import AgentModel, OperatorModel
from app.repositories.db_repository import DbRepository
from app.schemas.filter import BaseFilterModel

@inject
class AgentRepository(DbRepository[AgentModel]):

    def __init__(self, db: AsyncSession):
        super().__init__(AgentModel, db)


    async def get_by_id_full(self, agent_id: UUID) -> AgentModel | None:
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
            .where(AgentModel.id == agent_id)
        )
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
                             ) -> AgentModel:
        stmt = (
            select(AgentModel)
            .join(OperatorModel)
            .where(OperatorModel.user_id == user_id)
            .options(
                joinedload(AgentModel.operator).joinedload(OperatorModel.user),
                joinedload(AgentModel.security_settings),
            )
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def get_list_paginated(
        self, filter_obj: BaseFilterModel
    ) -> Tuple[list[AgentModel], int]:
        """
        Return minimal agent data for list view with pagination.
        Only loads columns needed for the list display (no relationships).
        Returns tuple of (agents, total_count).
        """
        # Count query - get total without loading data
        count_stmt = select(func.count(AgentModel.id)).where(
            AgentModel.is_deleted == 0
        )
        count_result = await self.db.execute(count_stmt)
        total = count_result.scalar() or 0

        # Data query - only select minimal columns needed for list view
        data_stmt = select(
            AgentModel.id,
            AgentModel.name,
            AgentModel.workflow_id,
            AgentModel.possible_queries,
            AgentModel.is_active,
        ).where(AgentModel.is_deleted == 0)

        # Apply sorting using base repository method
        data_stmt = self._apply_sorting(data_stmt, filter_obj)

        # Apply pagination using base repository method
        data_stmt = self._apply_pagination(data_stmt, filter_obj)

        result = await self.db.execute(data_stmt)
        rows = result.all()

        return rows, total
