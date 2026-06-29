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


def workflow_has_start_form(nodes, edges) -> bool:
    """True when a Human In The Loop node with "show_on_start" enabled is wired directly
    after the Chat Input (Start) node.

    In that case the chat plugin auto-runs the workflow as the conversation opens (an
    invisible system-trigger message) so the form appears immediately, instead of waiting
    for the visitor's first message.
    """
    if not isinstance(nodes, list) or not isinstance(edges, list):
        return False

    start_node = next(
        (n for n in nodes if isinstance(n, dict) and n.get("type") == "chatInputNode"),
        None,
    )
    if not start_node or not start_node.get("id"):
        return False
    start_id = start_node["id"]

    for edge in edges:
        if not isinstance(edge, dict) or edge.get("source") != start_id:
            continue
        target = next(
            (n for n in nodes if isinstance(n, dict) and n.get("id") == edge.get("target")),
            None,
        )
        if not target or target.get("type") != "humanInTheLoopNode":
            continue
        data = target.get("data") or {}
        form_fields = data.get("form_fields")
        if data.get("show_on_start") is True and isinstance(form_fields, list) and form_fields:
            return True
    return False


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
    trigger_start_form = False
    if agent.workflow:
        # A live-voice agent's workflow contains exactly one voiceAgentNode. Detect
        # it here while the full workflow dict is still loaded (it's overwritten with
        # testInput just below), so callers can enable voice-only mode without a flag.
        # Also capture its configured voice provider so the caller can check whether
        # a usable Gemini key exists (live-voice readiness) without re-loading nodes.
        nodes = agent.workflow.get('nodes') or []
        voice_node = next(
            (n for n in nodes if isinstance(n, dict) and n.get('type') == 'voiceAgentNode'),
            None,
        )
        live_voice_enabled = voice_node is not None
        if voice_node:
            voice_provider_id = (voice_node.get('data') or {}).get('voiceProviderId')

        # Likewise, while the full workflow is loaded, detect a Human In The Loop node
        # wired directly after Start with "show_on_start" on, so the start endpoint can
        # tell the plugin to auto-run the workflow (the nodes/edges are gone after the
        # overwrite below, which replaces agent.workflow with testInput).
        trigger_start_form = workflow_has_start_form(nodes, agent.workflow.get('edges') or [])

        test_input = agent.workflow.get('testInput', None)

        # remove message from testInput with pop()
        if test_input and 'message' in test_input:
            test_input.pop('message')
        agent.workflow = test_input

    request.state.agent = agent
    request.state.agent_live_voice_enabled = live_voice_enabled
    request.state.agent_voice_provider_id = voice_provider_id
    request.state.agent_trigger_start_form = trigger_start_form
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
    
