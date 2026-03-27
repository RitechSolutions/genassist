"""
Token usage extraction utilities for LLM responses.

Extracts input_tokens, output_tokens, total_tokens from LangChain AIMessage
response_metadata, handling provider-specific structures (OpenAI, Anthropic, etc.).
"""

from typing import Any, Dict, Optional

import logging

logger = logging.getLogger(__name__)


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
        input_tokens = token_usage.get("prompt_tokens") or token_usage.get("input_tokens")
        output_tokens = token_usage.get("completion_tokens") or token_usage.get("output_tokens")

    # Anthropic: usage
    if input_tokens is None and "usage" in metadata:
        usage = metadata["usage"]
        input_tokens = usage.get("input_tokens")
        output_tokens = usage.get("output_tokens")

    # Google/Vertex: usage_metadata
    usage_metadata = metadata.get("usage_metadata")
    if usage_metadata and input_tokens is None:
        input_tokens = usage_metadata.get("prompt_token_count") or usage_metadata.get("input_tokens")
        output_tokens = usage_metadata.get("candidates_token_count") or usage_metadata.get(
            "output_tokens"
        )

    # Try top-level keys
    if input_tokens is None:
        input_tokens = metadata.get("input_tokens") or metadata.get("prompt_tokens")
    if output_tokens is None:
        output_tokens = metadata.get("output_tokens") or metadata.get("completion_tokens")

    if input_tokens is None and output_tokens is None:
        return None

    input_tokens = input_tokens or 0
    output_tokens = output_tokens or 0
    total_tokens = input_tokens + output_tokens

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
    }


def extract_usage_from_aimessage(message: Any) -> Optional[Dict[str, int]]:
    """
    Extract token usage from a LangChain AIMessage.

    Args:
        message: AIMessage instance (from llm.ainvoke) with response_metadata

    Returns:
        Dict with input_tokens, output_tokens, total_tokens, or None if not found.
    """
    if message is None:
        return None

    metadata = None
    if hasattr(message, "response_metadata"):
        metadata = getattr(message, "response_metadata", None)
    elif hasattr(message, "usage_metadata"):
        metadata = getattr(message, "usage_metadata", None)
        if metadata and not isinstance(metadata, dict):
            metadata = {"usage_metadata": metadata} if metadata else None

    if not metadata:
        return None

    return extract_usage_from_response_metadata(metadata)
