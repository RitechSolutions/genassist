"""Per-node prompt-caching diagnostics: what a node asked for, and what it actually got"""

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

DIAGNOSTIC_KEY = "prompt_caching"

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


def record(state: Any, node_id: str, *, applied: bool, reason: Optional[str] = None) -> None:
    """Annotate the node's own execution entry. Best effort: a diagnostic must never raise
    into the business path"""
    try:
        annotate = getattr(state, "annotate_node_execution", None)
        if annotate is None:
            return
        annotate(
            node_id,
            DIAGNOSTIC_KEY,
            {"requested": True, "applied": applied, "reason": None if applied else reason},
        )
    except Exception:
        logger.warning("Failed writing the prompt-caching diagnostic for node %s", node_id, exc_info=True)
