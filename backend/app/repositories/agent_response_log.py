from typing import Any, Dict, List
from uuid import UUID
import json

from injector import inject
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models.agent_response_log import AgentResponseLogModel
from app.schemas.filter import AgentResponseLogFilter


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

    async def get_by_filter(
        self,
        agent_response_log_filter: AgentResponseLogFilter,
    ) -> List[AgentResponseLogModel]:
        """
        Fetch log entries matching the given filter.
        conversation_id is applied at the DB level; node_type is applied
        in Python by inspecting raw_response.row_agent_response.state.nodeExecutionStatus[*].type.
        """
        stmt = select(AgentResponseLogModel).where(
            AgentResponseLogModel.conversation_id == agent_response_log_filter.conversation_id
        )
        result = await self.db.execute(stmt)
        rows = result.scalars().all()

        if agent_response_log_filter.node_type is None:
            return list(rows)

        matched = []
        for row in rows:
            try:
                payload = json.loads(row.raw_response)
                node_statuses = payload.get("row_agent_response", {}).get("state", {}).get("nodeExecutionStatus", [])
                if isinstance(node_statuses, dict):
                    node_statuses = node_statuses.values()
                if any(n.get("type") == agent_response_log_filter.node_type for n in node_statuses):
                    matched.append(row)
            except (json.JSONDecodeError, AttributeError):
                continue

        return matched
