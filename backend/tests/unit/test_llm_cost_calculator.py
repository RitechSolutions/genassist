"""Unit tests for LLM cost calculator."""



from app.services.llm_cost_calculator import LlmCostCalculator


class TestCalculateCost:
    def setup_method(self):
        self.calculator = LlmCostCalculator()

    def test_openai_gpt4o(self):
        cost = self.calculator.calculate_cost("openai", "gpt-4o", 1000, 500)
        assert cost > 0
        # 1k input * 0.0025/1k + 500 output * 0.01/1k = 0.0025 + 0.005 = 0.0075
        assert abs(cost - 0.0075) < 0.0001

    def test_zero_tokens(self):
        assert self.calculator.calculate_cost("openai", "gpt-4o", 0, 0) == 0.0

    def test_negative_tokens_returns_zero(self):
        assert self.calculator.calculate_cost("openai", "gpt-4o", -1, 0) == 0.0
        assert self.calculator.calculate_cost("openai", "gpt-4o", 0, -5) == 0.0

    def test_unknown_model_uses_default_pricing(self):
        cost = self.calculator.calculate_cost("openai", "unknown-model-xyz", 1000, 1000)
        assert cost > 0
