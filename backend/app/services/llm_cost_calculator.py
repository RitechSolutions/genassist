"""
LLM cost calculation service.

Calculates cost in USD from token usage using provider/model pricing.
"""

from app.core.config.llm_pricing import blended_token_cost, inclusive_cache_fallback, resolve_live_pricing


class LlmCostCalculator:
    def calculate_cost(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cache_read_tokens: int = 0,
        cache_creation_tokens: int = 0,
    ) -> float | None:
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
            Cost in USD, or None when an active cache bucket has no resolvable rate
        """
        if input_tokens < 0 or output_tokens < 0:
            return 0.0
        provider_key = (provider or "").strip().lower()
        pricing = resolve_live_pricing(provider, model)
        input_per_1k = pricing.display_rates.get("input_per_1k", 0.001)
        output_per_1k = pricing.display_rates.get("output_per_1k", 0.002)
        read_rate = inclusive_cache_fallback(provider_key, pricing.cache_read_per_1k, input_per_1k)
        creation_rate = inclusive_cache_fallback(provider_key, pricing.cache_creation_per_1k, input_per_1k)

        cost = blended_token_cost(
            provider_key,
            input_tokens,
            output_tokens,
            cache_read_tokens,
            cache_creation_tokens,
            input_per_1k,
            output_per_1k,
            read_rate,
            creation_rate,
            1000.0,
        )
        return None if cost is None else round(cost, 6)
