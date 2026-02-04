"""
Dependencies for agent-specific security (CORS and rate limiting)
"""

import logging
from uuid import UUID
from fastapi import Request
from fastapi_injector import Injected

from app.auth.utils import get_current_user_id
from app.services.agent_config import AgentConfigService
from app.services.conversations import ConversationService
from app.core.exceptions.exception_classes import AppException
from app.core.exceptions.error_messages import ErrorKey

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
    conversation_service: ConversationService = Injected(ConversationService),
):
    """
    Dependency to get agent for conversation update endpoint.
    Gets agent from conversation's operator.
    Stores agent in request.state for use in rate limiting and CORS.
    """

    try:
        # check if agent exists set in the state
        state_agent = request.state.agent if hasattr(request.state, "agent") else None
        if state_agent:
            return state_agent

        # get conversation with operator and agent eager-loaded
        conversation = await conversation_service.get_conversation_by_id_with_operator_agent(conversation_id)
        if conversation is None:
            raise AppException(ErrorKey.CONVERSATION_NOT_FOUND, status_code=404)

        operator = conversation.operator
        agent = conversation.operator.agent
        
        # if agent is not set, get it from the operator
        if agent is None:
            agent = await agent_config_service.get_by_operator_id(operator.id)
            if agent is None:
                raise AppException(ErrorKey.AGENT_NOT_FOUND, status_code=404)

        request.state.agent = agent
        return agent
    except AppException:
        raise AppException(ErrorKey.AGENT_NOT_FOUND, status_code=404)
    
