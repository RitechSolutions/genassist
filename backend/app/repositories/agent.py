from typing import Optional
from uuid import UUID

from fastapi import Depends
from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.db.models import AgentKnowledgeBaseModel, AgentModel, AgentToolModel, OperatorModel
from app.db.session import get_db
from app.repositories.db_repository import DbRepository


class AgentRepository(DbRepository[AgentModel]):

    def __init__(self, db: AsyncSession = Depends(get_db)):
        super().__init__(AgentModel, db)


    async def create_with_foreign_keys(
            self,
            agent_model: AgentModel,
            tool_ids: list[UUID],
            kb_ids: list[UUID],
            ) -> AgentModel:
        # we're already inside a tx opened by the service layer.

        self.db.add(agent_model)
        await self.db.flush()  # agent_model.id now available

        if tool_ids:
            self.db.add_all(AgentToolModel(agent_id=agent_model.id, tool_id=t)
                            for t in tool_ids)
        if kb_ids:
            self.db.add_all(AgentKnowledgeBaseModel(
                    agent_id=agent_model.id, knowledge_base_id=kb)
                            for kb in kb_ids)


        await self.db.flush()  # stay in outer tx

        await self.db.refresh(agent_model)
        return agent_model


    async def update_with_foreign_keys(
            self,
            agent: AgentModel,
            tool_ids: Optional[list[UUID]] = None,
            kb_ids: Optional[list[UUID]] = None,
            ) -> AgentModel:
        try:
            # ---------- link‑table replacement ----------
            if tool_ids is not None:
                await self.db.execute(
                        delete(AgentToolModel).where(AgentToolModel.agent_id == agent.id)
                        )
                if tool_ids:  # []  = keep empty
                    self.db.add_all(
                            AgentToolModel(agent_id=agent.id, tool_id=t)
                            for t in tool_ids
                            )

            if kb_ids is not None:
                await self.db.execute(
                        delete(AgentKnowledgeBaseModel).where(
                                AgentKnowledgeBaseModel.agent_id == agent.id
                                )
                        )
                if kb_ids:
                    self.db.add_all(
                            AgentKnowledgeBaseModel(
                                    agent_id=agent.id, knowledge_base_id=kb
                                    )
                            for kb in kb_ids
                            )

            await self.db.flush()
            await self.db.commit()
        except SQLAlchemyError:
            await self.db.rollback()
            raise

        await self.db.refresh(agent)
        return agent


    async def get_by_id_full(self, agent_id: UUID) -> AgentModel | None:
        """
        Return the Agent row *with* agent_tools and agent_knowledge_bases
        eagerly loaded in a single round‑trip.
        """
        result = await self.db.execute(
                select(AgentModel)
                .options(
                        selectinload(AgentModel.agent_tools),
                        selectinload(AgentModel.agent_knowledge_bases),
                        joinedload(AgentModel.llm_provider),
                        joinedload(AgentModel.operator).joinedload(OperatorModel.user)
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
                        selectinload(AgentModel.agent_tools),
                        selectinload(AgentModel.agent_knowledge_bases),
                        joinedload(AgentModel.llm_provider),
                        joinedload(AgentModel.operator).joinedload(OperatorModel.user)
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
