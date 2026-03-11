from typing import Any, Dict, List, Optional
from uuid import UUID

from injector import inject

from app.repositories.agent_response_log import AgentResponseLogRepository
from app.schemas.filter import AgentResponseLogFilter
from app.schemas.dynamic_form_schemas.nodes import NODE_TYPE_LABELS


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

    async def get_logs_by_filter(
        self,
        agent_response_log_filter: AgentResponseLogFilter,
    ) -> List:
        """
        Get agent response logs matching the given filter.
        """
        return await self.repo.get_by_filter(agent_response_log_filter)

    async def build_enrichment_context(
        self,
        conversation_id: Optional[UUID],
        enrichment_keys: List[str],
    ) -> str:
        """
        Build a context string from enabled enrichment keys for prompt injection.
        Each enabled key is resolved by querying the agent response logs for the
        relevant node type and appending a human-readable fact line.
        """
        if not conversation_id or not enrichment_keys:
            return ""

        lines = []

        if "zendesk_ticket_created" in enrichment_keys:
            logs = await self.get_logs_by_filter(
                AgentResponseLogFilter(
                    conversation_id=conversation_id,
                    node_type="zendeskTicketNode",
                )
            )
            lines.append(f"- Zendesk ticket created: {'Yes' if logs else 'No'}")

        if "knowledge_base_used" in enrichment_keys:
            logs = await self.get_logs_by_filter(
                AgentResponseLogFilter(
                    conversation_id=conversation_id,
                    node_type="knowledgeBaseNode",
                )
            )
            lines.append(f"- Knowledge base queried: {'Yes' if logs else 'No'}")

        for key in enrichment_keys:
            if key.startswith("node:"):
                node_type = key[5:]
                label = NODE_TYPE_LABELS.get(node_type, node_type)
                logs = await self.get_logs_by_filter(
                    AgentResponseLogFilter(
                        conversation_id=conversation_id,
                        node_type=node_type,
                    )
                )
                lines.append(f"- {label} node used: {'Yes' if logs else 'No'}")

        return "\n".join(lines)

