"""
LLM pricing: database-backed rates (llm_cost_rates) with static fallback (USD per 1K tokens).

DB rows override static defaults for the same provider/model keys.
"""

from typing import Dict

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


def _normalize_model_name(model: str) -> str:
    if not model:
        return ""
    return str(model).lower().strip()


def _merged_provider_pricing(provider_key: str, tenant: str) -> Dict[str, Dict[str, float]]:
    static = dict(STATIC_LLM_PRICING_FALLBACK.get(provider_key, {}))
    db_nested = get_db_pricing_nested(tenant)
    db_prov = db_nested.get(provider_key, {})
    static.update(db_prov)
    return static


def find_pricing(provider: str, model: str) -> Dict[str, float]:
    tenant = get_tenant_context()
    provider_key = (provider or "").lower()
    model_key = _normalize_model_name(model)

    provider_pricing = _merged_provider_pricing(provider_key, tenant)
    if not provider_pricing:
        return DEFAULT_PRICING.copy()

    if model_key and model_key in provider_pricing:
        return provider_pricing[model_key].copy()

    for known_model, pricing in provider_pricing.items():
        if known_model.startswith("_"):
            continue
        if model_key and model_key.startswith(known_model):
            return pricing.copy()

    default_row = provider_pricing.get("_default")
    if default_row:
        return default_row.copy()
    return DEFAULT_PRICING.copy()
