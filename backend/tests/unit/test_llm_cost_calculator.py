"""Unit tests for LLM cost calculator."""

import pytest

from app.services.llm_cost_calculator import calculate_cost


class TestCalculateCost:
    def test_openai_gpt4o(self):
        cost = calculate_cost("openai", "gpt-4o", 1000, 500)
        assert cost > 0
        # 1k input * 0.0025/1k + 500 output * 0.01/1k = 0.0025 + 0.005 = 0.0075
        assert abs(cost - 0.0075) < 0.0001

    def test_zero_tokens(self):
        assert calculate_cost("openai", "gpt-4o", 0, 0) == 0.0

    def test_negative_tokens_returns_zero(self):
        assert calculate_cost("openai", "gpt-4o", -1, 0) == 0.0
        assert calculate_cost("openai", "gpt-4o", 0, -5) == 0.0

    def test_unknown_model_uses_default_pricing(self):
        cost = calculate_cost("openai", "unknown-model-xyz", 1000, 1000)
        assert cost > 0
