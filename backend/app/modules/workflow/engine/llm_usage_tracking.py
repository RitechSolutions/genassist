"""
LLM usage tracking utilities for workflow nodes.

Provides a helper to merge llm_usage from agent/node results into workflow state.
A decorator approach was evaluated: wrapping process() to auto-merge llm_usage
would require provider/model resolution inside the decorator. The explicit
merge in each node is clearer and keeps provider resolution at the call site.

Metering is best-effort: nothing here may raise into a node's business path.
"""

import logging
from typing import Any, Dict, Optional

from app.core.utils.llm_usage_utils import extract_usage_from_aimessage, usage_or_placeholder
from app.services.llm_providers import LlmProviderService

logger = logging.getLogger(__name__)


# One provider id resolved to (provider, model)
ProviderAttribution = tuple[str, str]


async def resolve_provider_model(
    provider_id: Any,
    cache: Optional[Dict[str, ProviderAttribution]] = None,
) -> ProviderAttribution:
    """Resolve provider/model names for pricing, memoized per id when ``cache`` is given"""
    key = str(provider_id) if provider_id else ""
    if cache is not None and key in cache:
        return cache[key]

    resolved = ("", "")
    if key:
        try:
            from app.dependencies.injector import injector

            info = await injector.get(LlmProviderService).get_by_id(provider_id)
            resolved = ((info.llm_model_provider or "").lower(), info.llm_model or "")
        except Exception:
            logger.warning("Could not resolve LLM provider %s for usage attribution", key, exc_info=True)

    if cache is not None:
        cache[key] = resolved
    return resolved


async def merge_llm_usage_from_result(
    state,
    result: Dict[str, Any],
    node_id: str,
    provider_id: str,
    prompt_caching_enabled: bool = False,
) -> None:
    """
    Merge llm_usage from agent result into workflow state.

    Call this after agent.invoke() when the result may contain llm_usage.
    Resolves provider/model from provider_id and adds each usage entry to state.

    Args:
        state: WorkflowState instance (from self.get_state())
        result: Agent result dict that may contain "llm_usage" list
        node_id: Node ID for tracking
        provider_id: LLM provider ID to resolve provider/model names
        prompt_caching_enabled: Whether the node asked for prompt caching on this call
    """
    try:
        llm_usage_list = result.get("llm_usage", []) if isinstance(result, dict) else []
        if not llm_usage_list:
            return

        resolved: Dict[str, ProviderAttribution] = {}

        for u in llm_usage_list:
            if not isinstance(u, dict):
                continue
            pid = u.get("provider_id") or provider_id
            provider, model = await resolve_provider_model(pid, resolved)
            state.add_llm_usage(
                input_tokens=u.get("input_tokens", 0),
                output_tokens=u.get("output_tokens", 0),
                total_tokens=u.get("total_tokens"),
                provider=provider,
                model=model,
                node_id=node_id,
                purpose=u.get("purpose"),
                token_details=u.get("token_details"),
                llm_provider_id=pid,
                prompt_caching_enabled=prompt_caching_enabled,
            )
    except Exception:
        logger.warning("Failed merging LLM usage for node %s", node_id, exc_info=True)


async def record_node_llm_usage(
    state,
    response: Any,
    node_id: str,
    provider_id: str,
    purpose: Optional[str] = None,
    prompt_caching_enabled: bool = False,
) -> None:
    """Record token usage from one LangChain message onto ``state``"""
    if response is None:
        return

    try:
        usage = extract_usage_from_aimessage(response)
    except Exception:
        logger.warning("Failed extracting LLM usage for node %s", node_id, exc_info=True)
        usage = None

    entry = usage_or_placeholder(usage)
    entry["purpose"] = purpose
    await merge_llm_usage_from_result(state, {"llm_usage": [entry]}, node_id, provider_id, prompt_caching_enabled)


async def record_compaction_usage(
    state,
    summary: Any,
    node_id: str,
    provider_id: str,
) -> None:
    """Record the compaction call, then drop the raw message before the summary is stored"""
    response = summary.pop("_llm_response", None) if isinstance(summary, dict) else None
    await record_node_llm_usage(state, response, node_id, provider_id, "compaction")
