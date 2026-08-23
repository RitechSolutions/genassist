"""Prompt-caching capability facts and the platform-level effective-state policy"""

from typing import Any, Dict, Optional

# Bedrock rejects a cachePoint on a model that doesn't support it, failing every call.
# Nova support is family-wide; Claude support is version-specific, Claude 3 (v1) and the
# original Claude 3.5 Sonnet release never got caching, only 3.5 Sonnet v2 and later did.
# Verified against AWS's supported-models table (docs.aws.amazon.com/bedrock/latest/userguide/prompt-caching.html).
BEDROCK_CACHEABLE_ANTHROPIC_MARKERS = (
    "claude-3-5-sonnet-20241022",  # the v2 release; the 20240620 v1 release is not cache-capable
    "claude-3-5-haiku",
    "claude-3-7-sonnet",
    "claude-opus-4",
    "claude-sonnet-4",
    "claude-haiku-4",
)

CLAUDE_FAMILY = "claude"
NOVA_FAMILY = "nova"


def bedrock_cache_family(model_key: Optional[str]) -> Optional[str]:
    """The cache-capable Bedrock family a model id names, or None"""
    name = (model_key or "").lower()
    if NOVA_FAMILY in name:
        return NOVA_FAMILY
    if any(marker in name for marker in BEDROCK_CACHEABLE_ANTHROPIC_MARKERS):
        return CLAUDE_FAMILY
    return None


def prompt_caching_effective(connection_data: Optional[Dict[str, Any]]) -> bool:
    """True only if the platform flag and the provider opt-in are both on.
    The stored opt-in is never rewritten"""
    from app.core.config.settings import settings

    if not settings.PROMPT_CACHING_FEATURE_ENABLED:
        return False
    return (connection_data or {}).get("prompt_caching_enabled") is True
