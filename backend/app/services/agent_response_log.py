from typing import Any, Dict
from uuid import UUID

from injector import inject

from app.repositories.agent_response_log import AgentResponseLogRepository


@inject
class AgentResponseLogService:
    """
    Service layer for agent response logging.
    """

    def __init__(self, repo: AgentResponseLogRepository):
        self.repo = repo

    async def log_response_for_message(
        self,
        conversation_id: UUID,
        transcript_message_id: UUID,
        agent_response: Dict[str, Any],
    ):
        """
        Persist the raw agent response for later debugging.
        """
        return await self.repo.log_response(
            conversation_id=conversation_id,
            transcript_message_id=transcript_message_id,
            raw_response=agent_response,
        )

    async def get_log_for_message(
        self,
        transcript_message_id: UUID,
    ):
        """
        Get the stored agent response log for a given transcript message id.
        """
        return await self.repo.get_by_transcript_message_id(transcript_message_id)

