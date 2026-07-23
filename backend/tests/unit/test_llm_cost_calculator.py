"""Unit tests for LLM cost calculator and pricing resolution"""

from decimal import Decimal

import pytest

import app.core.config.llm_pricing as llm_pricing
from app.core.config.llm_pricing import (
    DEFAULT_PRICING,
    PricingStatus,
    find_pricing,
    find_pricing_with_status,
)
from app.services.llm_cost_calculator import LlmCostCalculator


@pytest.fixture
def no_db_rates(monkeypatch):
    monkeypatch.setattr(llm_pricing, "get_db_pricing_nested", lambda tenant: {})


class TestCalculateCost:
    @pytest.fixture(autouse=True)
    def _no_db_rates(self, no_db_rates):
        pass

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

    def test_bedrock_nova_lite(self):
        cost = self.calculator.calculate_cost("bedrock", "us.amazon.nova-2-lite-v1:0", 1000, 1000)
        assert abs(cost - 0.0005) < 0.0001

    def test_longest_prefix_model_variant(self):
        cost = self.calculator.calculate_cost("openai", "gpt-4o-mini-2024-07-18", 1000, 1000)
        assert abs(cost - 0.00075) < 1e-9


class TestFindPricingWithStatus:
    @pytest.fixture(autouse=True)
    def _no_db_rates(self, no_db_rates):
        pass

    def test_exact_match_from_static_table_is_fallback(self):
        res = find_pricing_with_status("openai", "gpt-4o")
        assert res.status is PricingStatus.FALLBACK
        assert res.input_per_1k == Decimal("0.0025")
        assert res.output_per_1k == Decimal("0.01")
        assert res.matched_model_key == "gpt-4o"

    def test_longest_prefix_wins(self):
        res = find_pricing_with_status("openai", "gpt-4o-mini-2024-07-18")
        assert res.matched_model_key == "gpt-4o-mini"
        assert res.input_per_1k == Decimal("0.00015")

    def test_rates_are_decimal_from_str(self):
        res = find_pricing_with_status("anthropic", "claude-3-5-haiku")
        assert isinstance(res.input_per_1k, Decimal)
        assert res.input_per_1k == Decimal("0.0008")
        assert res.output_per_1k == Decimal("0.004")

    def test_unknown_model_without_default_is_unpriced(self):
        res = find_pricing_with_status("openai", "unknown-model-xyz")
        assert res.status is PricingStatus.UNPRICED
        assert res.input_per_1k is None
        assert res.output_per_1k is None
        assert res.matched_model_key is None

    def test_unknown_provider_is_unpriced(self):
        res = find_pricing_with_status("no-such-provider", "gpt-4o")
        assert res.status is PricingStatus.UNPRICED

    def test_provider_default_row_matches_as_fallback(self):
        res = find_pricing_with_status("openrouter", "some/new-model")
        assert res.status is PricingStatus.FALLBACK
        assert res.matched_model_key == "_default"
        assert res.input_per_1k == Decimal("0.001")

    def test_model_name_is_normalized(self):
        res = find_pricing_with_status("openai", "  GPT-4o  ")
        assert res.matched_model_key == "gpt-4o"

    def test_db_rate_reports_configured_and_overrides_static(self, monkeypatch):
        monkeypatch.setattr(
            llm_pricing,
            "get_db_pricing_nested",
            lambda tenant: {"openai": {"gpt-4o": {"input_per_1k": 0.005, "output_per_1k": 0.02}}},
        )
        res = find_pricing_with_status("openai", "gpt-4o")
        assert res.status is PricingStatus.CONFIGURED
        assert res.input_per_1k == Decimal("0.005")
        assert res.output_per_1k == Decimal("0.02")

    def test_db_longer_prefix_beats_static_prefix(self, monkeypatch):
        monkeypatch.setattr(
            llm_pricing,
            "get_db_pricing_nested",
            lambda tenant: {"openai": {"gpt-4o-mini-2024": {"input_per_1k": 0.0002, "output_per_1k": 0.0008}}},
        )
        res = find_pricing_with_status("openai", "gpt-4o-mini-2024-07-18")
        assert res.status is PricingStatus.CONFIGURED
        assert res.matched_model_key == "gpt-4o-mini-2024"


class TestFindPricingLegacyContract:
    @pytest.fixture(autouse=True)
    def _no_db_rates(self, no_db_rates):
        pass

    def test_returns_floats_for_known_model(self):
        pricing = find_pricing("openai", "gpt-4o")
        assert pricing == {"input_per_1k": 0.0025, "output_per_1k": 0.01}
        assert isinstance(pricing["input_per_1k"], float)

    def test_unmatched_returns_default_pricing_copy(self):
        pricing = find_pricing("openai", "unknown-model-xyz")
        assert pricing == DEFAULT_PRICING
        assert pricing is not DEFAULT_PRICING

    def test_longest_prefix_applies_to_legacy_path(self):
        assert find_pricing("openai", "gpt-4o-mini-2024-07-18")["input_per_1k"] == 0.00015
