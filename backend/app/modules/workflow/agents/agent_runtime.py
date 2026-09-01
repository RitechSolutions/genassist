"""Shared agent invocation path"""

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

from langchain_core.messages import SystemMessage

from app.modules.workflow.agents.react_agent import ReActAgent
from app.modules.workflow.agents.react_agent_lc import ReActAgentLC
from app.modules.workflow.agents.simple_tool_agent import SimpleToolAgent
from app.modules.workflow.agents.tool_agent import ToolAgent
from app.modules.workflow.llm.prompt_caching_chat_model import build_cacheable_system_message
from app.modules.workflow.llm.provider import LLMProvider

if TYPE_CHECKING:
    from app.modules.workflow.engine.workflow_state import WorkflowState

logger = logging.getLogger(__name__)


@dataclass
class AgentRunResult:
    """Normalized outcome of one agent invocation"""

    response: Any
    steps: List[Any]
    tools_used: List[Any]
    status: Optional[str]
    error: Optional[str]
    raw: Dict[str, Any]
    llm_model: Any


def _react_system_prompt(
    system_prompt: str, stable_volatile_parts: Optional[tuple[str, str]], llm_model: Any
) -> tuple[Union[str, SystemMessage], tuple[bool, Optional[str]]]:
    """A cacheable prefix plus its volatile tail, or the full string when ineligible,
    together with the (applied, reason) decision that produced it"""
    from app.modules.workflow.engine import prompt_cache_diagnostics as diagnostics

    applied, reason = diagnostics.cache_split_decision(stable_volatile_parts, llm_model)
    if not applied:
        return system_prompt, (False, reason)

    stable, volatile = stable_volatile_parts
    return build_cacheable_system_message(stable, volatile), (True, None)


async def run_agent_once(
    *,
    state: "WorkflowState",
    node_id: str,
    provider_id: Optional[str],
    fallback_chain_id: Optional[str],
    agent_type: str,
    system_prompt: str,
    user_prompt: str,
    tools: List[Any],
    max_iterations: int,
    chat_history: Optional[List[Any]] = None,
    llm_model: Any = None,
    stable_volatile_parts: Optional[tuple[str, str]] = None,
    stable_tool_names: Optional[frozenset[str]] = None,
    prompt_caching_enabled: bool = False,
) -> AgentRunResult:
    """Pick the LLM if needed, create the agent for ``agent_type``, run it once,
    add its token usage to ``state``, and return a normalized result"""
    if llm_model is None:
        from app.dependencies.injector import injector

        llm_provider = injector.get(LLMProvider)
        llm_model = await llm_provider.get_model_for_node(provider_id, fallback_chain_id, prompt_caching_enabled)
        logger.info("Agent type selected: %s, LLM model: %s", agent_type, llm_model)

    # The decision always reads back the branch's own split outcome, so the diagnostic
    # can never claim caching that did not happen.
    decision: tuple[bool, Optional[str]] = (False, None)
    mode_never_splits = False

    if agent_type == "ReActAgent":
        agent = ReActAgent(
            llm_model=llm_model,
            system_prompt=system_prompt,
            tools=tools,
            max_iterations=max_iterations,
        )
        mode_never_splits = True
    elif agent_type == "ReActAgentLC":
        react_prompt, decision = _react_system_prompt(system_prompt, stable_volatile_parts, llm_model)
        agent = ReActAgentLC(
            llm_model=llm_model,
            system_prompt=react_prompt,
            tools=tools,
            max_iterations=max_iterations,
        )
    elif agent_type == "SimpleToolExecutor":
        agent = SimpleToolAgent(
            llm_model=llm_model,
            system_prompt=system_prompt,
            tools=tools,
        )
        mode_never_splits = True
    else:
        agent = ToolAgent(
            llm_model=llm_model,
            system_prompt=system_prompt,
            tools=tools,
            max_iterations=max_iterations,
            stable_volatile_parts=stable_volatile_parts,
            stable_tool_names=stable_tool_names,
        )
        # The agent's own stored decision, so a change to its split rule carries over here.
        decision = agent.cache_split_decision

    applied, split_reason = decision
    # A withheld verdict is config-truth and lands before the call; "applied" waits
    # until the invocation returns, so a failed run leaves no misleading marker
    if prompt_caching_enabled and not applied:
        from app.modules.workflow.engine import prompt_cache_diagnostics as diagnostics

        reason = diagnostics.REASON_UNSUPPORTED_MODE if mode_never_splits else split_reason
        diagnostics.record(state, node_id, applied=False, reason=reason)

    result = await agent.invoke(user_prompt, chat_history=chat_history or [])
    logger.debug("Agent result: %s", result)

    from app.modules.workflow.engine.llm_usage_tracking import merge_llm_usage_from_result

    await merge_llm_usage_from_result(state, result, node_id, provider_id, prompt_caching_enabled)

    if prompt_caching_enabled and applied and not (result.get("status") == "error" and not result.get("llm_usage")):
        from app.modules.workflow.engine import prompt_cache_diagnostics as diagnostics

        diagnostics.record(state, node_id, applied=True)

    steps_key = "reasoning_steps" if agent_type in ["ReActAgent", "ReActAgentLC"] else "steps"

    return AgentRunResult(
        response=result.get("response"),
        steps=result.get(steps_key, []),
        tools_used=result.get("tools_used", []),
        status=result.get("status"),
        error=result.get("error"),
        raw=result,
        llm_model=llm_model,
    )
