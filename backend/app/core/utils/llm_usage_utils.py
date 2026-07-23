"""
Token usage extraction utilities for LLM responses.

Extracts input_tokens, output_tokens, total_tokens from a LangChain AIMessage,
preferring the standardized usage_metadata attribute with a response_metadata
fallback for provider-specific structures (OpenAI, Anthropic, etc.).
"""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def _first_present(data: Dict[str, Any], *keys: str) -> Optional[int]:
    """Return the first numeric value found among ``keys``. Zero is valid.

    Skip non-numbers (``""``, ``[]``, ``None``, etc.) so a bad provider payload
    can't break token math
    """
    for key in keys:
        value = data.get(key)
        if isinstance(value, (int, float)):
            return value
    return None


def extract_usage_from_response_metadata(metadata: Dict[str, Any]) -> Optional[Dict[str, int]]:
    """
    Extract token usage from raw response_metadata dict.

    Handles provider-specific structures:
    - OpenAI: token_usage -> prompt_tokens, completion_tokens
    - Anthropic: usage -> input_tokens, output_tokens
    - Google/Vertex: usage_metadata -> prompt_token_count, candidates_token_count
    - MistralAI/Groq: token_usage with various keys

    Returns:
        Dict with input_tokens, output_tokens, total_tokens, or None if not found.
    """
    if not metadata:
        return None

    input_tokens = None
    output_tokens = None

    # OpenAI: token_usage
    token_usage = metadata.get("token_usage") or metadata.get("usage")
    if token_usage:
        input_tokens = _first_present(token_usage, "prompt_tokens", "input_tokens")
        output_tokens = _first_present(token_usage, "completion_tokens", "output_tokens")

    # Anthropic: usage
    usage = metadata.get("usage")
    if usage:
        if input_tokens is None:
            input_tokens = _first_present(usage, "input_tokens")
        if output_tokens is None:
            output_tokens = _first_present(usage, "output_tokens")

    # Google/Vertex: usage_metadata
    usage_metadata = metadata.get("usage_metadata")
    if usage_metadata:
        if input_tokens is None:
            input_tokens = _first_present(usage_metadata, "prompt_token_count", "input_tokens")
        if output_tokens is None:
            output_tokens = _first_present(usage_metadata, "candidates_token_count", "output_tokens")

    # Try top-level keys
    if input_tokens is None:
        input_tokens = _first_present(metadata, "input_tokens", "prompt_tokens")
    if output_tokens is None:
        output_tokens = _first_present(metadata, "output_tokens", "completion_tokens")

    if input_tokens is None and output_tokens is None:
        return None

    input_tokens = input_tokens if input_tokens is not None else 0
    output_tokens = output_tokens if output_tokens is not None else 0
    total_tokens = input_tokens + output_tokens

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
    }


def extract_usage_from_aimessage(message: Any) -> Optional[Dict[str, int]]:
    """
    Extract token usage from a LangChain AIMessage. Prefer ``usage_metadata`` first.

    Returns:
        Dict with input_tokens, output_tokens, total_tokens, or None if not found.
    """
    if message is None:
        return None

    response_metadata = getattr(message, "response_metadata", None)

    usage = None
    usage_metadata = getattr(message, "usage_metadata", None)
    if isinstance(usage_metadata, dict):
        input_tokens = usage_metadata.get("input_tokens")
        output_tokens = usage_metadata.get("output_tokens")
        if input_tokens is not None or output_tokens is not None:
            input_tokens = input_tokens if input_tokens is not None else 0
            output_tokens = output_tokens if output_tokens is not None else 0
            total_tokens = usage_metadata.get("total_tokens")
            if total_tokens is None:
                total_tokens = input_tokens + output_tokens
            usage = {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens,
            }

    if usage is None and response_metadata:
        usage = extract_usage_from_response_metadata(response_metadata)

    if usage is None:
        return None

    # If this response came from a FallbackChatModel, record which provider actually
    # answered so usage can be attributed correctly (the primary may have failed over).
    if isinstance(response_metadata, dict):
        from app.modules.workflow.llm.fallback_exceptions import FALLBACK_PROVIDER_ID_KEY

        responding_provider_id = response_metadata.get(FALLBACK_PROVIDER_ID_KEY)
        if responding_provider_id:
            usage["provider_id"] = responding_provider_id

    return usage
