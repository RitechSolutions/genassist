"""Prompt-caching capability facts"""

from typing import Optional

# Bedrock rejects a cachePoint on a model that doesn't support it, failing every call.
# Support is version-specific: Claude 3 (v1) and the original Claude 3.5 Sonnet release
# never got caching, only 3.5 Sonnet v2 and later did.
# Verified against AWS's supported-models table (docs.aws.amazon.com/bedrock/latest/userguide/prompt-caching.html)
BEDROCK_CACHEABLE_ANTHROPIC_MARKERS = (
    "claude-3-5-sonnet-20241022",  # the v2 release; the 20240620 v1 release is not cache-capable
    "claude-3-5-haiku",
    "claude-3-7-sonnet",
    "claude-opus-4",
    "claude-sonnet-4",
    "claude-haiku-4",
    "claude-opus-5",
    "claude-sonnet-5",
    "claude-fable-5",
)

BEDROCK_CACHEABLE_NOVA_MARKERS = (
    "amazon.nova-micro",
    "amazon.nova-lite",
    "amazon.nova-pro",
    "amazon.nova-premier",
    "amazon.nova-2-lite",
)

CLAUDE_FAMILY = "claude"
NOVA_FAMILY = "nova"

# These cache long prompts server-side with no marker, so a node's caching toggle is
# moot rather than a mistake on them
AUTOMATIC_CACHING_PROVIDERS = frozenset({"openai", "azure_openai", "google_genai", "google_vertexai"})

_RATED_ARN_RESOURCES = ("foundation-model/", "inference-profile/")


def prompt_caching_mode(provider: Optional[str], model_key: Optional[str]) -> str:
    """Caching mode for this provider/model pair: "explicit" (the call is wraped
    with its own cache marker), "automatic" (provider caches server-side, no marker),
    or "none". Exposed so the builder doesn't reimplement this classification"""
    family = (provider or "").strip().lower()
    if family == "anthropic":
        return "explicit"
    if family == "bedrock":
        return "explicit" if bedrock_cache_family(model_key) else "none"
    if family in AUTOMATIC_CACHING_PROVIDERS:
        return "automatic"
    return "none"


def bedrock_cache_family(model_key: Optional[str]) -> Optional[str]:
    """The cache-capable Bedrock family a model id names, or None"""
    name = (model_key or "").lower()
    if name.startswith("arn:") and not name.split(":", 5)[-1].startswith(_RATED_ARN_RESOURCES):
        return None
    if any(marker in name for marker in BEDROCK_CACHEABLE_NOVA_MARKERS):
        return NOVA_FAMILY
    if any(marker in name for marker in BEDROCK_CACHEABLE_ANTHROPIC_MARKERS):
        return CLAUDE_FAMILY
    return None
