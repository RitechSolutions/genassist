"""
LLM cost calculation service.

Calculates cost in USD from token usage using provider/model pricing.
"""

from app.core.config.llm_pricing import find_pricing


class LlmCostCalculator:
    def calculate_cost(self, provider: str, model: str, input_tokens: int, output_tokens: int) -> float:
        """
        Calculate cost in USD for given token usage.

        Args:
            provider: LLM provider name (e.g. openai, anthropic, google_genai)
            model: Model name (e.g. gpt-4o, claude-3-sonnet)
            input_tokens: Number of input/prompt tokens
            output_tokens: Number of output/completion tokens

        Returns:
            Cost in USD
        """
        if input_tokens < 0 or output_tokens < 0:
            return 0.0
        pricing = find_pricing(provider, model)
        input_per_1k = pricing.get("input_per_1k", 0.001)
        output_per_1k = pricing.get("output_per_1k", 0.002)
        return round((input_tokens / 1000.0) * input_per_1k + (output_tokens / 1000.0) * output_per_1k, 6)
