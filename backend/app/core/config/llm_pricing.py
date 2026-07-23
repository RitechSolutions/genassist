"""
LLM pricing: database-backed rates (llm_cost_rates) with static fallback (USD per 1K tokens).

DB rows override static defaults for the same provider/model keys.
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Dict, Optional

from app.core.tenant_scope import get_tenant_context
from app.services.llm_pricing_cache import get_db_pricing_nested

# Static fallback when DB is empty or missing a row (also used before first migration).
STATIC_LLM_PRICING_FALLBACK: Dict[str, Dict[str, Dict[str, float]]] = {
    "openai": {
        "gpt-4o": {"input_per_1k": 0.0025, "output_per_1k": 0.01},
        "gpt-4o-mini": {"input_per_1k": 0.00015, "output_per_1k": 0.0006},
        "gpt-4-turbo": {"input_per_1k": 0.01, "output_per_1k": 0.03},
        "gpt-4": {"input_per_1k": 0.03, "output_per_1k": 0.06},
        "gpt-3.5-turbo": {"input_per_1k": 0.0005, "output_per_1k": 0.0015},
        "gpt-3.5-turbo-16k": {"input_per_1k": 0.003, "output_per_1k": 0.004},
        "o1": {"input_per_1k": 0.015, "output_per_1k": 0.06},
        "o1-mini": {"input_per_1k": 0.003, "output_per_1k": 0.012},
    },
    "anthropic": {
        "claude-3-5-sonnet": {"input_per_1k": 0.003, "output_per_1k": 0.015},
        "claude-3-5-haiku": {"input_per_1k": 0.0008, "output_per_1k": 0.004},
        "claude-3-sonnet": {"input_per_1k": 0.003, "output_per_1k": 0.015},
        "claude-3-opus": {"input_per_1k": 0.015, "output_per_1k": 0.075},
        "claude-3-haiku": {"input_per_1k": 0.00025, "output_per_1k": 0.00125},
    },
    "google_genai": {
        "gemini-1.5-pro": {"input_per_1k": 0.00125, "output_per_1k": 0.005},
        "gemini-1.5-flash": {"input_per_1k": 0.000075, "output_per_1k": 0.0003},
        "gemini-1.0-pro": {"input_per_1k": 0.0005, "output_per_1k": 0.0015},
    },
    "openrouter": {
        "_default": {"input_per_1k": 0.001, "output_per_1k": 0.002},
    },
    "vllm": {
        "_default": {"input_per_1k": 0.0, "output_per_1k": 0.0},
    },
    "ollama": {
        "_default": {"input_per_1k": 0.0, "output_per_1k": 0.0},
    },
    "bedrock": {
        "us.amazon.nova-2-lite-v1:0": {"input_per_1k": 0.0001, "output_per_1k": 0.0004},
        "us.amazon.nova-2-pro-v1:0": {"input_per_1k": 0.0002, "output_per_1k": 0.0008},
        "us.amazon.nova-2-flash-v1:0": {"input_per_1k": 0.0004, "output_per_1k": 0.0016},
    },
}

DEFAULT_PRICING = {"input_per_1k": 0.001, "output_per_1k": 0.002}


class PricingStatus(str, Enum):

    CONFIGURED = "configured"  # tenant-managed llm_cost_rates row
    FALLBACK = "fallback"  # bundled static rate table
    UNPRICED = "unpriced"  # no matching rate; cost must stay NULL
    LEGACY_ESTIMATE = "legacy_estimate"  # old cost copied during backfill; not calculated at runtime



@dataclass(frozen=True)
class PricingResolution:
    status: PricingStatus
    input_per_1k: Optional[Decimal]
    output_per_1k: Optional[Decimal]
    matched_model_key: Optional[str]


def _normalize_model_name(model: str) -> str:
    if not model:
        return ""
    return str(model).lower().strip()


def find_pricing_with_status(provider: str, model: str) -> PricingResolution:
    """Resolve a rate and report where it came from"""
    tenant = get_tenant_context()
    provider_key = (provider or "").lower()
    model_key = _normalize_model_name(model)

    db_provider_pricing = get_db_pricing_nested(tenant).get(provider_key, {})
    provider_pricing = dict(STATIC_LLM_PRICING_FALLBACK.get(provider_key, {}))
    provider_pricing.update(db_provider_pricing)

    matched_key = None
    if model_key and model_key in provider_pricing:
        matched_key = model_key
    else:
        prefix_matches = [
            known
            for known in provider_pricing
            if not known.startswith("_") and model_key and model_key.startswith(known)
        ]
        if prefix_matches:
            matched_key = max(prefix_matches, key=len)
        elif "_default" in provider_pricing:
            matched_key = "_default"

    if matched_key is None:
        return PricingResolution(PricingStatus.UNPRICED, None, None, None)

    rate = provider_pricing[matched_key]
    return PricingResolution(
        status=PricingStatus.CONFIGURED if matched_key in db_provider_pricing else PricingStatus.FALLBACK,
        input_per_1k=Decimal(str(rate["input_per_1k"])),
        output_per_1k=Decimal(str(rate["output_per_1k"])),
        matched_model_key=matched_key,
    )


def find_pricing(provider: str, model: str) -> Dict[str, float]:
    """Older helper for UI display: always returns float rates, or DEFAULT_PRICING if unknown"""
    resolution = find_pricing_with_status(provider, model)
    if resolution.status is PricingStatus.UNPRICED:
        return DEFAULT_PRICING.copy()
    return {
        "input_per_1k": float(resolution.input_per_1k),
        "output_per_1k": float(resolution.output_per_1k),
    }
