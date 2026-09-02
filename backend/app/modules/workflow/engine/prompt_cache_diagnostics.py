"""Per-node prompt-caching diagnostics: what a node asked for, and what it actually got"""

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

REASON_UNSUPPORTED_MODE = "unsupported_mode"
REASON_VOLATILE_PROMPT = "volatile_prompt"
REASON_MIXED_FALLBACK_CHAIN = "mixed_fallback_chain"
REASON_UNSUPPORTED_CACHE_MARKERS = "unsupported_cache_markers"
REASON_EMPTY_PROMPT = "empty_prompt"


def unwrapped_model_reason(llm: Any) -> Optional[str]:
    """Why this model cannot cache: a chain only partly wrappable, or a provider/model that
    does not accept explicit cache markers. None when the model can cache after all"""
    from app.modules.workflow.llm.fallback_chat_model import FallbackChatModel
    from app.modules.workflow.llm.prompt_caching_chat_model import model_has_prompt_caching

    if model_has_prompt_caching(llm):
        return None
    if isinstance(llm, FallbackChatModel) and any(model_has_prompt_caching(child) for child in llm.models or []):
        return REASON_MIXED_FALLBACK_CHAIN
    return REASON_UNSUPPORTED_CACHE_MARKERS


def cache_split_decision(
    stable_volatile_parts: Optional[tuple], llm: Any, *, stable_never_blank: bool = False
) -> tuple[bool, Optional[str]]:
    """The shared caching gate every node type calls: returns (applied, reason),checked in order"""
    if not stable_volatile_parts:
        return False, REASON_VOLATILE_PROMPT

    unsupported = unwrapped_model_reason(llm)
    if unsupported:
        return False, unsupported

    if stable_never_blank:
        return True, None
    stable = stable_volatile_parts[0]
    if not isinstance(stable, str) or not stable.strip():
        return False, REASON_EMPTY_PROMPT
    return True, None


def _diagnostics_map(state: Any) -> Optional[dict]:
    diagnostics_map = getattr(state, "prompt_caching_diagnostics", None)
    return diagnostics_map if isinstance(diagnostics_map, dict) else None


def record(state: Any, node_id: str, *, applied: bool, reason: Optional[str] = None) -> None:
    """Write the node's decision into the state's diagnostics map. Best effort: a
    diagnostic must never raise into the business path.

    ``applied`` means a cache marker was serialized into the provider request.

    A delegation loop re-records the same node once per turn, so the entry covers
    the whole node execution: one applied turn marks the node applied"""
    try:
        if not applied and reason:
            logger.debug("Prompt caching withheld for node %s: %s", node_id, reason)
        diagnostics_map = _diagnostics_map(state)
        if diagnostics_map is None:
            return
        entry = {"requested": True, "applied": applied}
        previous = diagnostics_map.get(node_id)
        if isinstance(previous, dict) and previous.get("applied"):
            entry["applied"] = True
        diagnostics_map[node_id] = entry
    except Exception:
        logger.warning("Failed writing the prompt-caching diagnostic for node %s", node_id, exc_info=True)


def with_observed_cache_tokens(diagnostics_map: dict, llm_usage: Any) -> dict:

    from app.core.utils.llm_usage_utils import extract_cache_tokens, is_usage_metadata_missing

    serialized: dict = {}
    for node_id, entry in diagnostics_map.items():
        if not isinstance(entry, dict) or not entry.get("applied"):
            serialized[node_id] = entry
            continue
        cache_read = cache_creation = 0
        reported = False
        for usage in llm_usage or []:
            if not isinstance(usage, dict) or usage.get("node_id") != node_id:
                continue
            if not usage.get("prompt_caching_enabled") or is_usage_metadata_missing(usage.get("token_details")):
                continue
            reported = True
            read, creation = extract_cache_tokens(usage.get("token_details"))
            cache_read += read
            cache_creation += creation
        if reported:
            entry = {**entry, "cache_read_tokens": cache_read, "cache_creation_tokens": cache_creation}
        serialized[node_id] = entry
    return serialized
