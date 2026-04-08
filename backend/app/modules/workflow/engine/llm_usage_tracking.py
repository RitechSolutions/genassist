"""
LLM usage tracking utilities for workflow nodes.

Provides a helper to merge llm_usage from agent/node results into workflow state.
A decorator approach was evaluated: wrapping process() to auto-merge llm_usage
would require provider/model resolution inside the decorator. The explicit
merge in each node is clearer and keeps provider resolution at the call site.
"""

from typing import Any, Dict

from app.services.llm_providers import LlmProviderService


async def merge_llm_usage_from_result(
    state,
    result: Dict[str, Any],
    node_id: str,
    provider_id: str,
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
    """
    llm_usage_list = result.get("llm_usage", []) if isinstance(result, dict) else []
    if not llm_usage_list:
        return

    from app.dependencies.injector import injector

    llm_service = injector.get(LlmProviderService)
    provider_info = await llm_service.get_by_id(provider_id)
    provider = (provider_info.llm_model_provider or "").lower()
    model = provider_info.llm_model or ""

    for u in llm_usage_list:
        state.add_llm_usage(
            input_tokens=u.get("input_tokens", 0),
            output_tokens=u.get("output_tokens", 0),
            provider=provider,
            model=model,
            node_id=node_id,
        )
