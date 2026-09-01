"""
LLM pricing: database-backed rates (llm_cost_rates) with static fallback (USD per 1K tokens).

DB rows override static defaults for the same provider/model keys.
"""

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, Optional, TypeVar

from app.core.config.llm_prompt_cache_capabilities import bedrock_cache_family
from app.core.tenant_scope import get_tenant_context
from app.services.llm_pricing_cache import get_db_pricing_nested

_BEDROCK_REGION_PREFIX = re.compile(r"^(?:us|eu|apac|us-gov)\.")
_Rate = TypeVar("_Rate", Decimal, float)

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
        "eu.amazon.nova-2-lite-v1:0": {"input_per_1k": 0.0001, "output_per_1k": 0.0004},
        "ca.amazon.nova-2-lite-v1:0": {"input_per_1k": 0.0001, "output_per_1k": 0.0004},
        "us.amazon.nova-2-lite-v1:0": {"input_per_1k": 0.0001, "output_per_1k": 0.0004},
        "apac.amazon.nova-2-lite-v1:0": {"input_per_1k": 0.0001, "output_per_1k": 0.0004},
        "us.amazon.nova-2-pro-v1:0": {"input_per_1k": 0.0002, "output_per_1k": 0.0008},
        "eu.amazon.nova-2-pro-v1:0": {"input_per_1k": 0.0002, "output_per_1k": 0.0008},
        "apac.amazon.nova-2-pro-v1:0": {"input_per_1k": 0.0002, "output_per_1k": 0.0008},
        "us.amazon.nova-2-flash-v1:0": {"input_per_1k": 0.0004, "output_per_1k": 0.0016},
        "eu.amazon.nova-2-flash-v1:0": {"input_per_1k": 0.0004, "output_per_1k": 0.0016},
        "apac.amazon.nova-2-flash-v1:0": {"input_per_1k": 0.0004, "output_per_1k": 0.0016},
    },
}

DEFAULT_PRICING = {"input_per_1k": 0.001, "output_per_1k": 0.002}
CACHE_EXCLUSIVE_PROVIDERS = frozenset({"bedrock"})
# Cache ratios off the input rate, shared by Anthropic and the cache-capable Bedrock families
CACHE_READ_MULTIPLIER = Decimal("0.1")
CACHE_WRITE_5M_MULTIPLIER = Decimal("1.25")

CACHE_READ_KEY = "cache_read_per_1k"
CACHE_CREATION_KEY = "cache_creation_per_1k"


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


@dataclass(frozen=True)
class LivePricing:
    """Resolves rates and cache buckets using the ledger's ladder. Returns None
    if no rate exists."""

    display_rates: Dict[str, float]
    cache_read_per_1k: Optional[float] = None
    cache_creation_per_1k: Optional[float] = None


@dataclass(frozen=True)
class _LayerMatch:
    status: PricingStatus
    matched_key: str
    rates: tuple[Decimal, Decimal]
    row: Mapping[str, Any]
    is_exact: bool


def _normalize_model_name(model: str) -> str:
    if not model:
        return ""
    return str(model).lower().strip()


def cache_rate_or_input(rate: Optional[_Rate], input_per_1k: _Rate) -> _Rate:
    """An unresolved cache bucket bills at the input rate"""
    return input_per_1k if rate is None else rate


def inclusive_cache_fallback(provider_key: str, rate: Optional[_Rate], input_per_1k: _Rate) -> Optional[_Rate]:
    if rate is None and provider_key in CACHE_EXCLUSIVE_PROVIDERS:
        return None
    return cache_rate_or_input(rate, input_per_1k)


def canonical_prompt_tokens(
    provider_key: str, input_tokens: int, cache_read_tokens: int, cache_creation_tokens: int
) -> int:
    """Prompt tokens sent, normalized across providers"""
    prompt = max(int(input_tokens), 0)
    if provider_key in CACHE_EXCLUSIVE_PROVIDERS:
        prompt += max(int(cache_read_tokens), 0) + max(int(cache_creation_tokens), 0)
    return prompt


def blended_token_cost(
    provider_key: str,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int,
    cache_creation_tokens: int,
    input_per_1k: _Rate,
    output_per_1k: _Rate,
    cache_read_per_1k: Optional[_Rate],
    cache_creation_per_1k: Optional[_Rate],
    thousand: _Rate,
) -> Optional[_Rate]:
    """The blended cost, or None when an active cache bucket has no resolved rate"""
    cache_read = max(int(cache_read_tokens), 0)
    cache_creation = max(int(cache_creation_tokens), 0)
    if not cache_read and not cache_creation:
        return (int(input_tokens) / thousand) * input_per_1k + (int(output_tokens) / thousand) * output_per_1k

    if (cache_read and cache_read_per_1k is None) or (cache_creation and cache_creation_per_1k is None):
        return None

    if provider_key in CACHE_EXCLUSIVE_PROVIDERS:
        uncached = max(int(input_tokens), 0)
    else:
        uncached = max(int(input_tokens) - cache_read - cache_creation, 0)

    cost = (uncached / thousand) * input_per_1k + (int(output_tokens) / thousand) * output_per_1k
    if cache_read:
        cost += (cache_read / thousand) * cache_read_per_1k
    if cache_creation:
        cost += (cache_creation / thousand) * cache_creation_per_1k
    return cost


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


def _matchers_for(provider_key: str, status: PricingStatus) -> list[Callable[[str, Mapping[str, Any]], Optional[str]]]:
    """Matchers within one layer. Bedrock retries per-tenant; rates are
    region-specific."""
    matchers = [_exact_or_longest_prefix]
    if provider_key == "bedrock" and status is PricingStatus.CONFIGURED:
        matchers.append(_match_bedrock_region_agnostic)
    return matchers


def _pricing_layers(
    provider_key: str, configured: Optional[Mapping[str, Mapping[str, Any]]]
) -> tuple[Mapping[str, Any], Mapping[str, Any], tuple[tuple[Mapping[str, Any], PricingStatus], ...]]:
    configured_table = (configured or {}).get(provider_key) or {}
    bundled_table = STATIC_LLM_PRICING_FALLBACK.get(provider_key, {})
    layers = ((configured_table, PricingStatus.CONFIGURED), (bundled_table, PricingStatus.FALLBACK))
    return configured_table, bundled_table, layers


def _collect_layer_matches(
    provider_key: str,
    model_key: str,
    layers: tuple[tuple[Mapping[str, Any], PricingStatus], ...],
) -> list[_LayerMatch]:
    matches: list[_LayerMatch] = []
    for table, status in layers:
        for matcher in _matchers_for(provider_key, status):
            matched_key = matcher(model_key, table)
            if matched_key is None:
                continue
            row = table[matched_key]
            rates = _rate_pair(row)
            if rates is not None:
                matches.append(_LayerMatch(status, matched_key, rates, row, matched_key == model_key))
                break
    return matches


def _default_row_match(table: Mapping[str, Any], status: PricingStatus) -> Optional[_LayerMatch]:
    row = table.get("_default")
    rates = _rate_pair(row)
    if rates is None:
        return None
    return _LayerMatch(status, "_default", rates, row, False)


def _select_base_rates(matches: list[_LayerMatch]) -> Optional[_LayerMatch]:
    return matches[0] if matches else None


def _bundled_match(matches: list[_LayerMatch]) -> Optional[_LayerMatch]:
    return next((match for match in matches if match.status is PricingStatus.FALLBACK), None)


def _row_cache_rate(match: Optional[_LayerMatch], key: str) -> Optional[Decimal]:
    if match is None:
        return None
    if match.status is PricingStatus.FALLBACK and not match.is_exact:
        return None
    return _cache_rate(match.row, key)


def _family_cache_rate(
    provider_key: str, model_key: str, input_per_1k: Decimal, multiplier: Decimal
) -> Optional[Decimal]:
    if provider_key == "anthropic":
        return input_per_1k * multiplier
    if provider_key == "bedrock" and bedrock_cache_family(model_key):
        return input_per_1k * multiplier
    return None


def _resolve_cache_bucket_rates(
    provider_key: str,
    model_key: str,
    selected: _LayerMatch,
    bundled: Optional[_LayerMatch],
) -> tuple[Optional[Decimal], Optional[Decimal]]:
    """Read and write resolve separately: base rates row → bundled row → family default."""
    resolved: list[Optional[Decimal]] = []
    for key, multiplier in (
        (CACHE_READ_KEY, CACHE_READ_MULTIPLIER),
        (CACHE_CREATION_KEY, CACHE_WRITE_5M_MULTIPLIER),
    ):
        rate = _row_cache_rate(selected, key)
        if rate is None and bundled is not selected:
            rate = _row_cache_rate(bundled, key)
        if rate is None:
            rate = _family_cache_rate(provider_key, model_key, selected.rates[0], multiplier)
        resolved.append(rate)
    return resolved[0], resolved[1]


def resolve_pricing(
    provider: str,
    model: str,
    configured: Optional[Mapping[str, Mapping[str, Any]]] = None,
) -> PricingResolution:
    """Resolve one call's rate for the ledger and report where it came from"""
    provider_key = (provider or "").strip().lower()
    model_key = _normalize_model_name(model)

    configured_table, _, layers = _pricing_layers(provider_key, configured)

    matches = _collect_layer_matches(provider_key, model_key, layers)
    selected = _select_base_rates(matches) or _default_row_match(configured_table, PricingStatus.CONFIGURED)
    if selected is None:
        return PricingResolution(PricingStatus.UNPRICED, None, None, None)

    cache_read, cache_creation = _resolve_cache_bucket_rates(provider_key, model_key, selected, _bundled_match(matches))
    return PricingResolution(
        selected.status,
        selected.rates[0],
        selected.rates[1],
        selected.matched_key,
        cache_read_per_1k=cache_read,
        cache_creation_per_1k=cache_creation,
    )


def _float_rates(rates: tuple[Decimal, Decimal], row: Mapping[str, Any]) -> Dict[str, float]:
    """Display-shaped rates. Cache keys appear only when the matched row carries them"""
    pricing = {"input_per_1k": float(rates[0]), "output_per_1k": float(rates[1])}
    for key in (CACHE_READ_KEY, CACHE_CREATION_KEY):
        rate = _cache_rate(row, key)
        if rate is not None:
            pricing[key] = float(rate)
    return pricing


def resolve_live_pricing(provider: str, model: str) -> LivePricing:
    tenant = get_tenant_context()
    provider_key = (provider or "").strip().lower()
    model_key = _normalize_model_name(model)

    _, _, layers = _pricing_layers(provider_key, get_db_pricing_nested(tenant))

    matches = _collect_layer_matches(provider_key, model_key, layers)
    selected = _select_base_rates(matches)
    if selected is None:
        for table, status in layers:
            selected = _default_row_match(table, status)
            if selected is not None:
                break
    if selected is None:
        default_input = Decimal(str(DEFAULT_PRICING["input_per_1k"]))
        cache_read = _family_cache_rate(provider_key, model_key, default_input, CACHE_READ_MULTIPLIER)
        cache_creation = _family_cache_rate(provider_key, model_key, default_input, CACHE_WRITE_5M_MULTIPLIER)
        return LivePricing(
            DEFAULT_PRICING.copy(),
            None if cache_read is None else float(cache_read),
            None if cache_creation is None else float(cache_creation),
        )

    cache_read, cache_creation = _resolve_cache_bucket_rates(provider_key, model_key, selected, _bundled_match(matches))
    return LivePricing(
        _float_rates(selected.rates, selected.row),
        None if cache_read is None else float(cache_read),
        None if cache_creation is None else float(cache_creation),
    )
