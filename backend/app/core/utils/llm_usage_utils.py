"""
Token usage extraction utilities for LLM responses.

Extracts input_tokens, output_tokens, total_tokens from a LangChain AIMessage,
preferring the standardized usage_metadata attribute with a response_metadata
fallback for provider-specific structures (OpenAI, Anthropic, etc.).
"""

import logging
import math
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Marks a call the provider reported no usage for. Pricing must leave it unpriced
USAGE_METADATA_MISSING = "usage_metadata_missing"


def _coerce_count(value: Any) -> Optional[int]:
    """Return ``value`` as a token count, or None when it isn't one"""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return max(int(value), 0)


def _first_present(data: Any, *keys: str) -> Optional[int]:
    """Return the first usable count found among ``keys``. Zero is valid"""
    if not isinstance(data, dict):
        return None
    for key in keys:
        count = _coerce_count(data.get(key))
        if count is not None:
            return count
    return None


def extract_cache_tokens(token_details: Any) -> tuple[int, int]:
    """Cache read and cache creation counts from a stored ``token_details``

    Returns:
        ``(cache_read, cache_creation)``
    """
    if not isinstance(token_details, dict):
        return 0, 0
    details = token_details.get("input_token_details")
    if not isinstance(details, dict) or not details:
        details = token_details
    return _coerce_count(details.get("cache_read")) or 0, _coerce_count(details.get("cache_creation")) or 0


def _provider_total(metadata: Dict[str, Any]) -> Optional[int]:
    """Provider-reported total"""
    for source in (
        metadata.get("token_usage"),
        metadata.get("usage"),
        metadata.get("usage_metadata"),
        metadata,
    ):
        total = _first_present(source, "total_tokens", "total_token_count")
        if total is not None:
            return total
    return None


def _standard_token_details(usage_metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Keep LangChain's standardized breakdowns (cache reads, reasoning tokens).

    They are not priced today but are preserved on the event for later refinement
    """
    details: Dict[str, Any] = {}
    for key in ("input_token_details", "output_token_details"):
        value = usage_metadata.get(key)
        if isinstance(value, dict) and value:
            details[key] = value
    return details


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

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": max(_provider_total(metadata) or 0, input_tokens + output_tokens),
    }


def extract_usage_from_aimessage(message: Any) -> Optional[Dict[str, Any]]:
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
        input_tokens = _first_present(usage_metadata, "input_tokens")
        output_tokens = _first_present(usage_metadata, "output_tokens")
        if input_tokens is not None or output_tokens is not None:
            input_tokens = input_tokens if input_tokens is not None else 0
            output_tokens = output_tokens if output_tokens is not None else 0
            provider_total = _first_present(usage_metadata, "total_tokens") or 0
            usage = {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": max(provider_total, input_tokens + output_tokens),
            }
            details = _standard_token_details(usage_metadata)
            if details:
                usage["token_details"] = details

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


def usage_or_placeholder(usage: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Every observed invocation counts as a call"""
    if usage:
        return dict(usage)
    return {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "token_details": {USAGE_METADATA_MISSING: True},
    }


def is_usage_metadata_missing(token_details: Any) -> bool:
    return isinstance(token_details, dict) and bool(token_details.get(USAGE_METADATA_MISSING))
