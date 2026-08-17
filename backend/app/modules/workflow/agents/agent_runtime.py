"""Shared agent invocation path"""

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

from langchain_core.messages import SystemMessage

from app.modules.workflow.agents.react_agent import ReActAgent
from app.modules.workflow.agents.react_agent_lc import ReActAgentLC
from app.modules.workflow.agents.simple_tool_agent import SimpleToolAgent
from app.modules.workflow.agents.tool_agent import ToolAgent
from app.modules.workflow.llm.prompt_caching_chat_model import model_has_prompt_caching
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


def _split_system_prompt(
    system_prompt: str, volatile_system_suffix: Optional[str], llm_model: Any
) -> Union[str, SystemMessage]:
    """Split the prompt into a cacheable prefix plus its volatile tail, or leave it as a string"""
    if not volatile_system_suffix or not model_has_prompt_caching(llm_model):
        return system_prompt
    if not system_prompt.endswith(volatile_system_suffix):
        return system_prompt

    base = system_prompt[: -len(volatile_system_suffix)]
    if not base.strip():
        return system_prompt

    return SystemMessage(
        content=[
            {"type": "text", "text": base},
            {"type": "text", "text": volatile_system_suffix},
        ]
    )


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
    volatile_system_suffix: Optional[str] = None,
) -> AgentRunResult:
    """Pick the LLM if needed, create the agent for ``agent_type``, run it once,
    add its token usage to ``state``, and return a normalized result"""
    if llm_model is None:
        from app.dependencies.injector import injector

        llm_provider = injector.get(LLMProvider)
        llm_model = await llm_provider.get_model_for_node(provider_id, fallback_chain_id)
        logger.info("Agent type selected: %s, LLM model: %s", agent_type, llm_model)

    if agent_type == "ReActAgent":
        agent = ReActAgent(
            llm_model=llm_model,
            system_prompt=system_prompt,
            tools=tools,
            max_iterations=max_iterations,
        )
    elif agent_type == "ReActAgentLC":
        agent = ReActAgentLC(
            llm_model=llm_model,
            system_prompt=_split_system_prompt(system_prompt, volatile_system_suffix, llm_model),
            tools=tools,
            max_iterations=max_iterations,
        )
    elif agent_type == "SimpleToolExecutor":
        agent = SimpleToolAgent(
            llm_model=llm_model,
            system_prompt=system_prompt,
            tools=tools,
        )
    else:
        agent = ToolAgent(
            llm_model=llm_model,
            system_prompt=system_prompt,
            tools=tools,
            max_iterations=max_iterations,
            volatile_system_suffix=volatile_system_suffix,
        )

    result = await agent.invoke(user_prompt, chat_history=chat_history or [])
    logger.debug("Agent result: %s", result)

    from app.modules.workflow.engine.llm_usage_tracking import merge_llm_usage_from_result

    await merge_llm_usage_from_result(state, result, node_id, provider_id)

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
