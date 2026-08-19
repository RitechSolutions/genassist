"""
LLM cost calculation service.

Calculates cost in USD from token usage using provider/model pricing.
"""

from app.core.config.llm_pricing import (
    ANTHROPIC_CACHE_READ_MULTIPLIER,
    ANTHROPIC_CACHE_WRITE_MULTIPLIER,
    CACHE_EXCLUSIVE_PROVIDERS,
    default_cache_rate,
    find_pricing,
)

_CACHE_READ_MULTIPLIER = float(ANTHROPIC_CACHE_READ_MULTIPLIER)
_CACHE_WRITE_MULTIPLIER = float(ANTHROPIC_CACHE_WRITE_MULTIPLIER)


class LlmCostCalculator:
    def calculate_cost(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cache_read_tokens: int = 0,
        cache_creation_tokens: int = 0,
    ) -> float:
        """
        Calculate cost in USD for given token usage.

        Args:
            provider: LLM provider name (e.g. openai, anthropic, google_genai)
            model: Model name (e.g. gpt-4o, claude-3-sonnet)
            input_tokens: Number of input/prompt tokens
            output_tokens: Number of output/completion tokens
            cache_read_tokens: Prompt tokens served from the provider's cache
            cache_creation_tokens: Prompt tokens written to the provider's cache

        Returns:
            Cost in USD
        """
        if input_tokens < 0 or output_tokens < 0:
            return 0.0
        pricing = find_pricing(provider, model)
        input_per_1k = pricing.get("input_per_1k", 0.001)
        output_per_1k = pricing.get("output_per_1k", 0.002)
        cache_read = max(int(cache_read_tokens), 0)
        cache_creation = max(int(cache_creation_tokens), 0)
        if not cache_read and not cache_creation:
            return round((input_tokens / 1000.0) * input_per_1k + (output_tokens / 1000.0) * output_per_1k, 6)

        provider_key = (provider or "").strip().lower()
        read_rate = pricing.get("cache_read_per_1k")
        if read_rate is None:
            read_rate = default_cache_rate(provider_key, input_per_1k, _CACHE_READ_MULTIPLIER)
        creation_rate = pricing.get("cache_creation_per_1k")
        if creation_rate is None:
            creation_rate = default_cache_rate(provider_key, input_per_1k, _CACHE_WRITE_MULTIPLIER)

        if provider_key in CACHE_EXCLUSIVE_PROVIDERS:
            uncached = input_tokens
        else:
            uncached = max(input_tokens - cache_read - cache_creation, 0)

        return round(
            (uncached / 1000.0) * input_per_1k
            + (output_tokens / 1000.0) * output_per_1k
            + (cache_read / 1000.0) * read_rate
            + (cache_creation / 1000.0) * creation_rate,
            6,
        )
