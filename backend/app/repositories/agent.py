from typing import Optional
from uuid import UUID

from fastapi import Depends
from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.db.models import AgentModel, OperatorModel
from app.db.session import get_db
from app.repositories.db_repository import DbRepository


class AgentRepository(DbRepository[AgentModel]):

    def __init__(self, db: AsyncSession = Depends(get_db)):
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
                        joinedload(AgentModel.workflow)
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
                        joinedload(AgentModel.workflow)
                        )
                )
        return result.scalars().all()


    async def get_by_user_id(self,
                             user_id: UUID,
                             ) -> AgentModel:
        stmt = (
            select(AgentModel)
            .join(OperatorModel)
            .where(OperatorModel.user_id == user_id)
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()
