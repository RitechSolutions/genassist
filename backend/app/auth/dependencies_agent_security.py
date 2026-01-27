"""
Dependencies for agent-specific security (CORS and rate limiting)
"""

import logging
from uuid import UUID
from fastapi import Depends, Request
from fastapi_injector import Injected

from app.auth.utils import get_current_user_id
from app.services.agent_config import AgentConfigService
from app.services.conversations import ConversationService

logger = logging.getLogger(__name__)


async def get_agent_for_start(
    request: Request,
    agent_config_service: AgentConfigService = Injected(AgentConfigService),
):
    """
    Dependency to get agent for conversation start endpoint.
    Stores agent in request.state for use in rate limiting and CORS.
    """
    userid = get_current_user_id()
    agent = await agent_config_service.get_by_user_id(userid)
    request.state.agent = agent
    return agent


async def get_agent_for_update(
    request: Request,
    conversation_id: UUID,
    agent_config_service: AgentConfigService = Injected(AgentConfigService),
    # conversation_service: ConversationService = Injected(ConversationService),
):
    """
    Dependency to get agent for conversation update endpoint.
    Gets agent from conversation's operator.
    Stores agent in request.state for use in rate limiting and CORS.
    """
    # Get conversation with operator and agent eager-loaded (avoids async lazy-load)
    # conversation = await conversation_service.get_conversation_by_id_with_operator_agent(
    #     conversation_id, raise_not_found=False
    # )

    # if conversation and conversation.operator and conversation.operator.agent:
    #     agent = conversation.operator.agent
    # else:
    #     # Fallback: get agent from user_id (for new conversations)
    #     userid = get_current_user_id()
    #     agent = await agent_config_service.get_by_user_id(userid)

    userid = get_current_user_id()
    agent = await agent_config_service.get_by_user_id(userid)
    request.state.agent = agent
    return agent
