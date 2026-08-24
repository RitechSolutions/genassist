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
    stable_volatile_parts: Optional[tuple], llm: Any, stable_text: Optional[str] = None
) -> tuple[bool, Optional[str]]:
    """The shared caching gate every node type calls: returns (applied, reason),
    checked in order"""
    if not stable_volatile_parts:
        return False, REASON_VOLATILE_PROMPT

    unsupported = unwrapped_model_reason(llm)
    if unsupported:
        return False, unsupported

    stable = stable_volatile_parts[0] if stable_text is None else stable_text
    if not isinstance(stable, str) or not stable.strip():
        return False, REASON_EMPTY_PROMPT
    return True, None


def _diagnostics_map(state: Any) -> Optional[dict]:
    diagnostics_map = getattr(state, "prompt_caching_diagnostics", None)
    return diagnostics_map if isinstance(diagnostics_map, dict) else None


def record(state: Any, node_id: str, *, applied: bool, reason: Optional[str] = None) -> None:
    """Write the node's decision into the state's diagnostics map. Best effort: a
    diagnostic must never raise into the business path"""
    try:
        diagnostics_map = _diagnostics_map(state)
        if diagnostics_map is None:
            return
        diagnostics_map[node_id] = {
            "requested": True,
            "applied": applied,
            "reason": None if applied else reason,
        }
    except Exception:
        logger.warning("Failed writing the prompt-caching diagnostic for node %s", node_id, exc_info=True)


def record_observed_cache_tokens(state: Any, node_id: str, usage_entries: Any) -> None:
    """Stamp the provider-reported cache activity onto an applied diagnostic, so
    "marker applied" can be told apart from "provider actually cached" (short prompts
    below the provider's minimum are silently processed uncached)"""
    try:
        diagnostics_map = _diagnostics_map(state)
        if diagnostics_map is None:
            return
        entry = diagnostics_map.get(node_id)
        if not isinstance(entry, dict) or not entry.get("applied"):
            return

        from app.core.utils.llm_usage_utils import extract_cache_tokens, extract_usage_from_aimessage

        cache_read = cache_creation = 0
        reported = False
        for usage in usage_entries or []:
            if usage is not None and not isinstance(usage, dict):
                usage = extract_usage_from_aimessage(usage)
            if not isinstance(usage, dict):
                continue
            reported = True
            read, creation = extract_cache_tokens(usage.get("token_details"))
            cache_read += read
            cache_creation += creation
        # A run with no usage at all stays unstamped: absent fields mean "not reported",
        # zeros mean "reported, and nothing was cached"
        if reported:
            entry["cache_read_tokens"] = cache_read
            entry["cache_creation_tokens"] = cache_creation
    except Exception:
        logger.warning("Failed recording observed cache tokens for node %s", node_id, exc_info=True)
