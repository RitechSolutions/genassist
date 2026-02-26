from typing import Any, Dict
from uuid import UUID
import json

from injector import inject
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models.agent_response_log import AgentResponseLogModel


@inject
class AgentResponseLogRepository:
    """
    Repository for persisting and querying agent response logs.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def log_response(
        self,
        conversation_id: UUID,
        transcript_message_id: UUID,
        raw_response: Dict[str, Any],
    ) -> AgentResponseLogModel:
        """
        Create a log entry for a given transcript message with the full agent response.
        """
        entry = AgentResponseLogModel(
            conversation_id=conversation_id,
            transcript_message_id=transcript_message_id,
            raw_response=json.dumps(raw_response),
        )
        self.db.add(entry)
        await self.db.commit()
        await self.db.refresh(entry)
        return entry

    async def get_by_transcript_message_id(
        self,
        transcript_message_id: UUID,
    ) -> AgentResponseLogModel | None:
        """
        Fetch a log entry by the transcript (message) id.
        """
        stmt = select(AgentResponseLogModel).where(
            AgentResponseLogModel.transcript_message_id == transcript_message_id
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()
