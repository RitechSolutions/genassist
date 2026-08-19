"""
LLM pricing: database-backed rates (llm_cost_rates) with static fallback (USD per 1K tokens).

DB rows override static defaults for the same provider/model keys.
"""

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, Optional

from app.core.tenant_scope import get_tenant_context
from app.services.llm_pricing_cache import get_db_pricing_nested

_BEDROCK_REGION_PREFIX = re.compile(r"^(?:us|eu|apac|us-gov)\.")

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
CACHE_EXCLUSIVE_PROVIDERS = frozenset({"bedrock"})
# Applied to the input rate when a tenant has configured no explicit cache rates
ANTHROPIC_CACHE_READ_MULTIPLIER = Decimal("0.1")
ANTHROPIC_CACHE_WRITE_MULTIPLIER = Decimal("1.25")


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
    cache_read_per_1k: Optional[Decimal] = None
    cache_creation_per_1k: Optional[Decimal] = None


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
    """Response-cost/display helper: float rates, DEFAULT_PRICING when unknown"""
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


def _rate_pair(row: Any) -> Optional[tuple[Decimal, Decimal]]:
    """Coerce one rate row to Decimals, or None when it can't be priced honestly"""
    if not isinstance(row, Mapping):
        return None
    try:
        rates = (Decimal(str(row["input_per_1k"])), Decimal(str(row["output_per_1k"])))
    except (KeyError, TypeError, ArithmeticError, ValueError):
        return None
    if any(r.is_nan() or r.is_infinite() or r < 0 for r in rates):
        return None
    return rates


def _cache_rate(row: Any, key: str) -> Optional[Decimal]:
    """Coerce one optional cache rate to Decimal, or None if missing or invalid"""
    if not isinstance(row, Mapping):
        return None
    value = row.get(key)
    if value is None:
        return None
    try:
        rate = Decimal(str(value))
    except (TypeError, ArithmeticError, ValueError):
        return None
    if rate.is_nan() or rate.is_infinite() or rate < 0:
        return None
    return rate


def _exact_or_longest_prefix(model_key: str, table: Mapping[str, Any]) -> Optional[str]:
    if not model_key:
        return None
    if model_key in table and not model_key.startswith("_"):
        return model_key
    prefixes = [key for key in table if not key.startswith("_") and model_key.startswith(key)]
    return max(prefixes, key=len) if prefixes else None


def _match_bedrock_region_agnostic(model_key: str, table: Mapping[str, Any]) -> Optional[str]:
    """Match a region-prefixed Bedrock model against region-stripped rate keys"""
    base = _BEDROCK_REGION_PREFIX.sub("", model_key)
    if not base:
        return None
    # Sorted so two region variants of one model always resolve the same way
    candidates = [(_BEDROCK_REGION_PREFIX.sub("", key), key) for key in sorted(table) if not key.startswith("_")]
    exact = [key for stripped, key in candidates if stripped == base]
    if exact:
        return exact[0]
    prefixed = [(stripped, key) for stripped, key in candidates if stripped and base.startswith(stripped)]
    if prefixed:
        return max(prefixed, key=lambda pair: len(pair[0]))[1]
    return None


def _matchers_for(provider_key: str) -> list[Callable[[str, Mapping[str, Any]], Optional[str]]]:
    """Matchers to try within one layer. Bedrock adds a region-agnostic retry"""
    if provider_key == "bedrock":
        return [_exact_or_longest_prefix, _match_bedrock_region_agnostic]
    return [_exact_or_longest_prefix]


def _match_layers(
    provider_key: str,
    model_key: str,
    layers: tuple[tuple[Mapping[str, Any], PricingStatus], ...],
) -> Optional[tuple[PricingStatus, str, tuple[Decimal, Decimal], Mapping[str, Any]]]:
    """Search the tenant-configured table first, then the bundled fallback"""
    matchers = _matchers_for(provider_key)
    for table, status in layers:
        for matcher in matchers:
            matched_key = matcher(model_key, table)
            if matched_key is None:
                continue
            row = table[matched_key]
            rates = _rate_pair(row)
            if rates is not None:
                return status, matched_key, rates, row
    return None


def resolve_pricing(
    provider: str,
    model: str,
    configured: Optional[Mapping[str, Mapping[str, Any]]] = None,
) -> PricingResolution:
    """Resolve one call's rate for the ledger and report where it came from"""
    provider_key = (provider or "").strip().lower()
    model_key = _normalize_model_name(model)

    configured_table = (configured or {}).get(provider_key) or {}
    bundled_table = STATIC_LLM_PRICING_FALLBACK.get(provider_key, {})
    layers = ((configured_table, PricingStatus.CONFIGURED), (bundled_table, PricingStatus.FALLBACK))

    match = _match_layers(provider_key, model_key, layers)
    if match is not None:
        status, matched_key, rates, row = match
        return PricingResolution(
            status,
            rates[0],
            rates[1],
            matched_key,
            cache_read_per_1k=_cache_rate(row, "cache_read_per_1k"),
            cache_creation_per_1k=_cache_rate(row, "cache_creation_per_1k"),
        )

    default_row = configured_table.get("_default")
    default_rates = _rate_pair(default_row)
    if default_rates is not None:
        return PricingResolution(
            PricingStatus.CONFIGURED,
            default_rates[0],
            default_rates[1],
            "_default",
            cache_read_per_1k=_cache_rate(default_row, "cache_read_per_1k"),
            cache_creation_per_1k=_cache_rate(default_row, "cache_creation_per_1k"),
        )

    return PricingResolution(PricingStatus.UNPRICED, None, None, None)
