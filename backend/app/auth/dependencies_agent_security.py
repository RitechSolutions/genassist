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
    agent = await agent_config_service.get_by_user_id(userid, with_workflow=True)

    test_input = None
    live_voice_enabled = False
    voice_provider_id = None
    workflow_nodes: list = []
    if agent.workflow:
        # A live-voice agent's workflow contains exactly one voiceAgentNode. Detect
        # it here while the full workflow dict is still loaded (it's overwritten with
        # testInput just below), so callers can enable voice-only mode without a flag.
        # Also capture its configured voice provider so the caller can check whether
        # a usable Gemini key exists (live-voice readiness) without re-loading nodes.
        nodes = agent.workflow.get('nodes') or []
        # Keep the node graph for callers; agent.workflow is replaced with testInput below.
        workflow_nodes = nodes
        voice_node = next(
            (n for n in nodes if isinstance(n, dict) and n.get('type') == 'voiceAgentNode'),
            None,
        )
        live_voice_enabled = voice_node is not None
        if voice_node:
            voice_provider_id = (voice_node.get('data') or {}).get('voiceProviderId')

        test_input = agent.workflow.get('testInput', None)

        # remove message from testInput with pop()
        if test_input and 'message' in test_input:
            test_input.pop('message')
        agent.workflow = test_input

    request.state.agent = agent
    request.state.agent_workflow_nodes = workflow_nodes
    request.state.agent_live_voice_enabled = live_voice_enabled
    request.state.agent_voice_provider_id = voice_provider_id
    # Agent-level toggle: greet the visitor (and trigger a HITL form wired right after
    # Chat Input) as the conversation opens. Plain scalar column, unaffected by the
    # workflow→testInput swap above.
    request.state.agent_trigger_start_form = bool(getattr(agent, "greet_on_start", False))
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
    
