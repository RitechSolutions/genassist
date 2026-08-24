"""Shared agent invocation path"""

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

from langchain_core.messages import SystemMessage

from app.modules.workflow.agents.react_agent import ReActAgent
from app.modules.workflow.agents.react_agent_lc import ReActAgentLC
from app.modules.workflow.agents.simple_tool_agent import SimpleToolAgent
from app.modules.workflow.agents.tool_agent import ToolAgent
from app.modules.workflow.llm.prompt_caching_chat_model import (
    build_cacheable_system_message,
    model_has_prompt_caching,
)
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
) -> Union[str, SystemMessage]:
    """A cacheable prefix plus its volatile tail, or the full string when ineligible"""
    if not stable_volatile_parts or not model_has_prompt_caching(llm_model):
        return system_prompt

    stable, volatile = stable_volatile_parts
    if not stable.strip():
        return system_prompt

    return build_cacheable_system_message(stable, volatile)


def _split_failure_reason(stable_volatile_parts: Optional[tuple[str, str]], llm_model: Any) -> Optional[str]:
    """Best-effort explanation for a withheld split, in the same order the split code gates.
    None when no predicate explains it, so a future gate degrades to a plain not-applied"""
    from app.modules.workflow.engine import prompt_cache_diagnostics as diagnostics

    if not stable_volatile_parts:
        return diagnostics.REASON_VOLATILE_PROMPT

    unsupported = diagnostics.unwrapped_model_reason(llm_model)
    if unsupported:
        return unsupported

    stable, _ = stable_volatile_parts
    if not stable.strip():
        return diagnostics.REASON_EMPTY_PROMPT
    return None


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
    prompt_caching_enabled: bool = False,
) -> AgentRunResult:
    """Pick the LLM if needed, create the agent for ``agent_type``, run it once,
    add its token usage to ``state``, and return a normalized result"""
    if llm_model is None:
        from app.dependencies.injector import injector

        llm_provider = injector.get(LLMProvider)
        llm_model = await llm_provider.get_model_for_node(provider_id, fallback_chain_id, prompt_caching_enabled)
        logger.info("Agent type selected: %s, LLM model: %s", agent_type, llm_model)

    # `applied` always reads back the branch's own split outcome, so the diagnostic can
    # never claim caching that did not happen.
    applied = False
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
        react_prompt = _react_system_prompt(system_prompt, stable_volatile_parts, llm_model)
        agent = ReActAgentLC(
            llm_model=llm_model,
            system_prompt=react_prompt,
            tools=tools,
            max_iterations=max_iterations,
        )
        applied = isinstance(react_prompt, SystemMessage)
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
        )
        # The agent's own stored decision, so a change to its split rule carries over here.
        applied = bool(agent._cache_split)

    if prompt_caching_enabled:
        from app.modules.workflow.engine import prompt_cache_diagnostics as diagnostics

        if applied:
            reason = None
        elif mode_never_splits:
            reason = diagnostics.REASON_UNSUPPORTED_MODE
        else:
            reason = _split_failure_reason(stable_volatile_parts, llm_model)
        diagnostics.record(state, node_id, applied=applied, reason=reason)

    result = await agent.invoke(user_prompt, chat_history=chat_history or [])
    logger.debug("Agent result: %s", result)

    from app.modules.workflow.engine.llm_usage_tracking import merge_llm_usage_from_result

    await merge_llm_usage_from_result(state, result, node_id, provider_id, prompt_caching_enabled)

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
