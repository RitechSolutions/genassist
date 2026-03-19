"""
LLM pricing configuration per provider and model (USD per 1K tokens).

Prices are approximate and should be updated periodically.
Reference: https://openai.com/api/pricing/
"""

from typing import Dict, Any

# Pricing: {provider: {model: {input_per_1k, output_per_1k}}}
LLM_PRICING: Dict[str, Dict[str, Dict[str, float]]] = {
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
        # OpenRouter uses various models; default to generic
        "_default": {"input_per_1k": 0.001, "output_per_1k": 0.002},
    },
    "vllm": {
        "_default": {"input_per_1k": 0.0, "output_per_1k": 0.0},
    },
    "ollama": {
        "_default": {"input_per_1k": 0.0, "output_per_1k": 0.0},
    },
}

# Fallback when provider/model not in table
DEFAULT_PRICING = {"input_per_1k": 0.001, "output_per_1k": 0.002}


def _normalize_model_name(model: str) -> str:
    """Normalize model name for lookup (lowercase, strip)."""
    if not model:
        return ""
    return str(model).lower().strip()


def find_pricing(provider: str, model: str) -> Dict[str, float]:
    """Find pricing for provider/model, with fallbacks."""
    provider_key = (provider or "").lower()
    model_key = _normalize_model_name(model)

    provider_pricing = LLM_PRICING.get(provider_key, {})
    if not provider_pricing:
        return DEFAULT_PRICING.copy()

    # Exact model match
    if model_key and model_key in provider_pricing:
        return provider_pricing[model_key].copy()

    # Partial match (e.g. gpt-4o-2024-05-13 -> gpt-4o)
    for known_model, pricing in provider_pricing.items():
        if known_model.startswith("_"):
            continue
        if model_key and model_key.startswith(known_model):
            return pricing.copy()

    # Provider default
    return provider_pricing.get("_default", DEFAULT_PRICING).copy()
