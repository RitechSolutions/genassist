"""Unit tests for LLM cost calculator and pricing resolution"""

from decimal import Decimal
from pathlib import Path

import pytest

import app.core.config.llm_pricing as llm_pricing
from app.core.config.llm_pricing import (
    DEFAULT_PRICING,
    PricingStatus,
    find_pricing,
    resolve_pricing,
)
from app.services.llm_cost_calculator import LlmCostCalculator
from app.services.llm_usage_recorder import _resolve_cost


@pytest.fixture
def no_db_rates(monkeypatch):
    monkeypatch.setattr(llm_pricing, "get_db_pricing_nested", lambda tenant: {})

MIRRORED_BEDROCK_RATES = {
    "bedrock": {
        "us.amazon.nova-2-lite-v1:0": {
            "input_per_1k": "0.0001",
            "output_per_1k": "0.0004",
            "cache_read_per_1k": "0.0001",
            "cache_creation_per_1k": "0.0001",
        }
    }
}


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

    def test_bedrock_has_no_bundled_rate_so_the_ledger_refuses_and_the_display_defaults(self):
        assert resolve_pricing("bedrock", "us.amazon.nova-2-lite-v1:0", {}).status is PricingStatus.UNPRICED
        cost = self.calculator.calculate_cost("bedrock", "us.amazon.nova-2-lite-v1:0", 1000, 1000)
        assert cost == round(DEFAULT_PRICING["input_per_1k"] + DEFAULT_PRICING["output_per_1k"], 6)


class TestCalculateCostWithCacheTokens:
    @pytest.fixture(autouse=True)
    def _no_db_rates(self, no_db_rates):
        pass

    def setup_method(self):
        self.calculator = LlmCostCalculator()

    def test_zero_cache_counts_keep_the_legacy_result(self):
        legacy = self.calculator.calculate_cost("openai", "gpt-4o", 1000, 500)
        assert self.calculator.calculate_cost("openai", "gpt-4o", 1000, 500, 0, 0) == legacy

    def test_anthropic_reads_price_at_a_tenth_of_input(self):
        # 400 uncached + 600 read: 0.4*0.003 + 0.6*0.003*0.1 + 0.1*0.015
        cost = self.calculator.calculate_cost("anthropic", "claude-3-5-sonnet", 1000, 100, 600, 0)
        assert cost == round(0.0012 + 0.00018 + 0.0015, 6)

    def test_anthropic_writes_price_at_the_premium(self):
        cost = self.calculator.calculate_cost("anthropic", "claude-3-5-sonnet", 1000, 0, 0, 200)
        assert cost == round(0.8 * 0.003 + 0.2 * 0.003 * 1.25, 6)

    def test_bedrock_buckets_are_additive_to_raw_input(self, monkeypatch):
        monkeypatch.setattr(llm_pricing, "get_db_pricing_nested", lambda tenant: MIRRORED_BEDROCK_RATES)
        cost = self.calculator.calculate_cost("bedrock", "us.amazon.nova-2-lite-v1:0", 7, 20, 3697, 0)
        assert cost == round((7 / 1000) * 0.0001 + (20 / 1000) * 0.0004 + (3697 / 1000) * 0.0001, 6)

    def test_bedrock_without_a_resolved_cache_rate_keeps_the_legacy_display_estimate(self, bundled_bedrock_row):
        cost = self.calculator.calculate_cost("bedrock", "us.amazon.nova-2-lite-v1:0", 7, 20, 3697, 0)
        assert cost == round((7 / 1000) * 0.001 + (20 / 1000) * 0.002 + (3697 / 1000) * 0.001, 6)

    def test_configured_cache_rates_win_over_the_provider_default(self, monkeypatch):
        monkeypatch.setattr(
            llm_pricing,
            "get_db_pricing_nested",
            lambda tenant: {
                "bedrock": {
                    "us.amazon.nova-2-lite-v1:0": {
                        "input_per_1k": 0.0001,
                        "output_per_1k": 0.0004,
                        "cache_read_per_1k": 0.000025,
                        "cache_creation_per_1k": 0.0,
                    }
                }
            },
        )
        cost = self.calculator.calculate_cost("bedrock", "us.amazon.nova-2-lite-v1:0", 0, 0, 4000, 1000)
        assert cost == round(4 * 0.000025, 6)

    def test_unknown_model_prices_cache_buckets_at_the_fabricated_default(self):
        cost = self.calculator.calculate_cost("openai", "unknown-model-xyz", 0, 0, 1000, 0)
        assert cost == round(DEFAULT_PRICING["input_per_1k"], 6)

    def test_negative_cache_counts_are_clamped(self):
        legacy = self.calculator.calculate_cost("openai", "gpt-4o", 1000, 500)
        assert self.calculator.calculate_cost("openai", "gpt-4o", 1000, 500, -5, -9) == legacy

    def test_buckets_larger_than_input_never_price_negative_uncached(self):
        cost = self.calculator.calculate_cost("anthropic", "claude-3-5-sonnet", 100, 0, 600, 0)
        assert cost == round(0.6 * 0.003 * 0.1, 6)


class TestResolvePricingBundledLayer:
    def test_exact_match_from_bundled_table_is_fallback(self):
        res = resolve_pricing("openai", "gpt-4o", {})
        assert res.status is PricingStatus.FALLBACK
        assert res.input_per_1k == Decimal("0.0025")
        assert res.output_per_1k == Decimal("0.01")
        assert res.matched_model_key == "gpt-4o"

    def test_longest_prefix_wins(self):
        res = resolve_pricing("openai", "gpt-4o-mini-2024-07-18", {})
        assert res.matched_model_key == "gpt-4o-mini"
        assert res.input_per_1k == Decimal("0.00015")

    def test_rates_are_decimal_from_str(self):
        res = resolve_pricing("anthropic", "claude-3-5-haiku", {})
        assert isinstance(res.input_per_1k, Decimal)
        assert res.input_per_1k == Decimal("0.0008")
        assert res.output_per_1k == Decimal("0.004")

    def test_tiny_bundled_rate_keeps_full_precision(self):
        res = resolve_pricing("google_genai", "gemini-1.5-flash", {})
        assert res.input_per_1k == Decimal("0.000075")

    def test_unknown_model_without_default_is_unpriced(self):
        res = resolve_pricing("openai", "unknown-model-xyz", {})
        assert res.status is PricingStatus.UNPRICED
        assert res.input_per_1k is None
        assert res.output_per_1k is None
        assert res.matched_model_key is None

    def test_unknown_provider_is_unpriced(self):
        assert resolve_pricing("no-such-provider", "gpt-4o", {}).status is PricingStatus.UNPRICED

    def test_empty_model_is_unpriced(self):
        assert resolve_pricing("openai", "", {}).status is PricingStatus.UNPRICED

    def test_bundled_default_row_is_never_used(self):
        for provider in ("openrouter", "vllm", "ollama"):
            res = resolve_pricing(provider, "some/new-model", {})
            assert res.status is PricingStatus.UNPRICED, provider
            assert res.matched_model_key is None

    def test_provider_and_model_are_normalized(self):
        res = resolve_pricing("  OpenAI  ", "  GPT-4o  ", {})
        assert res.matched_model_key == "gpt-4o"
        assert res.status is PricingStatus.FALLBACK

    def test_missing_configured_map_defaults_to_bundled(self):
        assert resolve_pricing("openai", "gpt-4o").status is PricingStatus.FALLBACK


class TestResolvePricingConfiguredLayer:
    def test_configured_exact_overrides_bundled(self):
        configured = {"openai": {"gpt-4o": {"input_per_1k": "0.005", "output_per_1k": "0.02"}}}
        res = resolve_pricing("openai", "gpt-4o", configured)
        assert res.status is PricingStatus.CONFIGURED
        assert res.input_per_1k == Decimal("0.005")
        assert res.output_per_1k == Decimal("0.02")

    def test_configured_prefix_beats_bundled_exact(self):
        configured = {"openai": {"gpt-4o": {"input_per_1k": "0.009", "output_per_1k": "0.02"}}}
        res = resolve_pricing("openai", "gpt-4o-mini", configured)
        assert res.status is PricingStatus.CONFIGURED
        assert res.matched_model_key == "gpt-4o"

    def test_configured_longest_prefix_wins(self):
        configured = {"openai": {"gpt-4o-mini-2024": {"input_per_1k": "0.0002", "output_per_1k": "0.0008"}}}
        res = resolve_pricing("openai", "gpt-4o-mini-2024-07-18", configured)
        assert res.status is PricingStatus.CONFIGURED
        assert res.matched_model_key == "gpt-4o-mini-2024"

    def test_tenant_default_applies_only_after_specific_layers(self):
        configured = {
            "openai": {
                "gpt-4o": {"input_per_1k": "0.005", "output_per_1k": "0.02"},
                "_default": {"input_per_1k": "0.5", "output_per_1k": "0.9"},
            }
        }
        assert resolve_pricing("openai", "gpt-4o", configured).matched_model_key == "gpt-4o"
        assert resolve_pricing("openai", "gpt-4-turbo", configured).matched_model_key == "gpt-4-turbo"

        fallthrough = resolve_pricing("openai", "brand-new-model", configured)
        assert fallthrough.status is PricingStatus.CONFIGURED
        assert fallthrough.matched_model_key == "_default"
        assert fallthrough.input_per_1k == Decimal("0.5")

    def test_configured_decimal_rates_keep_precision(self):
        configured = {"openai": {"gpt-4o": {"input_per_1k": Decimal("0.0000001"), "output_per_1k": Decimal("0")}}}
        res = resolve_pricing("openai", "gpt-4o", configured)
        assert res.input_per_1k == Decimal("0.0000001")
        assert res.output_per_1k == Decimal("0")

    def test_zero_configured_rate_is_priced_not_unpriced(self):
        configured = {"openai": {"gpt-4o": {"input_per_1k": "0", "output_per_1k": "0"}}}
        res = resolve_pricing("openai", "gpt-4o", configured)
        assert res.status is PricingStatus.CONFIGURED
        assert res.input_per_1k == Decimal("0")

    @pytest.mark.parametrize("bad", ["abc", "-1", "NaN", "Infinity", None])
    def test_unusable_configured_row_falls_through_to_bundled(self, bad):
        configured = {"openai": {"gpt-4o": {"input_per_1k": bad, "output_per_1k": "1"}}}
        res = resolve_pricing("openai", "gpt-4o", configured)
        assert res.status is PricingStatus.FALLBACK
        assert res.input_per_1k == Decimal("0.0025")

    def test_rate_edit_is_picked_up_by_the_next_call_without_invalidation(self):
        before = {"openai": {"gpt-4o": {"input_per_1k": "0.005", "output_per_1k": "0.02"}}}
        after = {"openai": {"gpt-4o": {"input_per_1k": "0.011", "output_per_1k": "0.04"}}}
        assert resolve_pricing("openai", "gpt-4o", before).input_per_1k == Decimal("0.005")
        assert resolve_pricing("openai", "gpt-4o", after).input_per_1k == Decimal("0.011")


class TestResolvePricingBedrockRegions:
    @pytest.mark.parametrize(
        "model",
        [
            "eu.amazon.nova-2-lite-v1:0",
            "apac.amazon.nova-2-lite-v1:0",
            "amazon.nova-2-lite-v1:0",
        ],
    )
    def test_another_geography_never_inherits_a_bundled_us_rate(self, bundled_bedrock_row, model):
        assert resolve_pricing("bedrock", model, {}).status is PricingStatus.UNPRICED

    @pytest.mark.parametrize(
        "model",
        ["us.amazon.nova-2-lite-v1:0", "eu.amazon.nova-2-lite-v1:0", "amazon.nova-2-lite-v1:0"],
    )
    def test_no_bedrock_identifier_prices_from_the_shipped_table(self, model):
        assert resolve_pricing("bedrock", model, {}).status is PricingStatus.UNPRICED

    def test_bedrock_unknown_model_still_unpriced(self):
        assert resolve_pricing("bedrock", "eu.amazon.titan-text-v1", {}).status is PricingStatus.UNPRICED

    def test_configured_region_less_key_beats_bundled_exact_hit(self, bundled_bedrock_row):
        configured = {"bedrock": {"amazon.nova-2-lite-v1:0": {"input_per_1k": "0.009", "output_per_1k": "0.02"}}}
        res = resolve_pricing("bedrock", "us.amazon.nova-2-lite-v1:0", configured)
        assert res.status is PricingStatus.CONFIGURED
        assert res.matched_model_key == "amazon.nova-2-lite-v1:0"
        assert res.input_per_1k == Decimal("0.009")

    def test_bundled_exact_hit_still_beats_a_configured_default(self, bundled_bedrock_row):
        configured = {"bedrock": {"_default": {"input_per_1k": "9", "output_per_1k": "9"}}}
        res = resolve_pricing("bedrock", "us.amazon.nova-2-lite-v1:0", configured)
        assert res.status is PricingStatus.FALLBACK
        assert res.input_per_1k == Decimal("0.001")

    def test_bedrock_region_retry_prefers_configured_over_bundled(self, bundled_bedrock_row):
        configured = {"bedrock": {"us.amazon.nova-2-lite-v1:0": {"input_per_1k": "0.009", "output_per_1k": "0.02"}}}
        res = resolve_pricing("bedrock", "eu.amazon.nova-2-lite-v1:0", configured)
        assert res.status is PricingStatus.CONFIGURED
        assert res.input_per_1k == Decimal("0.009")

    def test_a_tenant_default_answers_a_geography_the_bundled_table_cannot(self):
        configured = {"bedrock": {"_default": {"input_per_1k": "0.5", "output_per_1k": "0.9"}}}
        res = resolve_pricing("bedrock", "eu.amazon.nova-2-lite-v1:0", configured)
        assert res.status is PricingStatus.CONFIGURED
        assert res.matched_model_key == "_default"

    def test_region_prefix_matching_is_deterministic(self):
        configured = {
            "bedrock": {
                "us.amazon.nova-2-lite-v1:0": {"input_per_1k": "0.001", "output_per_1k": "0.002"},
                "eu.amazon.nova-2-lite-v1:0": {"input_per_1k": "0.003", "output_per_1k": "0.004"},
            }
        }
        matches = {resolve_pricing("bedrock", "apac.amazon.nova-2-lite-v1:0", configured).matched_model_key}
        for _ in range(20):
            matches.add(resolve_pricing("bedrock", "apac.amazon.nova-2-lite-v1:0", configured).matched_model_key)
        assert len(matches) == 1


class TestResolvePricingCacheRates:
    def test_configured_cache_rates_are_carried(self):
        configured = {
            "openai": {
                "gpt-4o": {
                    "input_per_1k": "0.005",
                    "output_per_1k": "0.02",
                    "cache_read_per_1k": "0.0005",
                    "cache_creation_per_1k": "0.00625",
                }
            }
        }
        res = resolve_pricing("openai", "gpt-4o", configured)
        assert res.cache_read_per_1k == Decimal("0.0005")
        assert res.cache_creation_per_1k == Decimal("0.00625")

    def test_absent_cache_rates_resolve_to_none(self):
        res = resolve_pricing("openai", "gpt-4o", {})
        assert res.cache_read_per_1k is None
        assert res.cache_creation_per_1k is None

    def test_explicit_zero_stays_distinct_from_absent(self):
        configured = {
            "bedrock": {
                "us.amazon.nova-2-lite-v1:0": {
                    "input_per_1k": "0.0001",
                    "output_per_1k": "0.0004",
                    "cache_read_per_1k": "0.000025",
                    "cache_creation_per_1k": "0",
                }
            }
        }
        res = resolve_pricing("bedrock", "us.amazon.nova-2-lite-v1:0", configured)
        assert res.cache_creation_per_1k == Decimal("0")
        assert res.cache_creation_per_1k is not None

    @pytest.mark.parametrize("bad", ["abc", "-1", "NaN", "Infinity", None, [], True])
    def test_unusable_cache_rate_becomes_none_without_touching_base_rates(self, bad):
        configured = {
            "openai": {"gpt-4o": {"input_per_1k": "0.005", "output_per_1k": "0.02", "cache_read_per_1k": bad}}
        }
        res = resolve_pricing("openai", "gpt-4o", configured)
        assert res.cache_read_per_1k is None
        assert res.status is PricingStatus.CONFIGURED
        assert res.input_per_1k == Decimal("0.005")

    def test_cache_rates_are_carried_from_a_tenant_default_row(self):
        configured = {
            "openai": {"_default": {"input_per_1k": "0.5", "output_per_1k": "0.9", "cache_read_per_1k": "0.05"}}
        }
        res = resolve_pricing("openai", "brand-new-model", configured)
        assert res.matched_model_key == "_default"
        assert res.cache_read_per_1k == Decimal("0.05")
        assert res.cache_creation_per_1k is None

    def test_unpriced_carries_no_cache_rates(self):
        res = resolve_pricing("openai", "totally-unknown-model", {})
        assert res.cache_read_per_1k is None
        assert res.cache_creation_per_1k is None


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

    def test_bundled_default_row_still_applies_on_the_legacy_path(self):
        assert find_pricing("openrouter", "some/new-model") == {"input_per_1k": 0.001, "output_per_1k": 0.002}

    def test_longest_prefix_wins_like_the_ledger(self):
        assert find_pricing("openai", "gpt-4o-mini-2024-07-18")["input_per_1k"] == 0.00015

    def test_bedrock_region_prefixed_model_matches_a_region_less_rate(self, monkeypatch):
        monkeypatch.setattr(
            llm_pricing,
            "get_db_pricing_nested",
            lambda tenant: {"bedrock": {"amazon.nova-2-lite-v1:0": {"input_per_1k": 0.009, "output_per_1k": 0.02}}},
        )
        assert find_pricing("bedrock", "us.amazon.nova-2-lite-v1:0")["input_per_1k"] == 0.009

    def test_configured_prefix_beats_a_bundled_exact_hit(self, monkeypatch):
        monkeypatch.setattr(
            llm_pricing,
            "get_db_pricing_nested",
            lambda tenant: {"openai": {"gpt-4": {"input_per_1k": 0.111, "output_per_1k": 0.222}}},
        )
        assert find_pricing("openai", "gpt-4o")["input_per_1k"] == 0.111

    def test_unusable_configured_row_falls_through_to_bundled(self, monkeypatch):
        monkeypatch.setattr(
            llm_pricing,
            "get_db_pricing_nested",
            lambda tenant: {"openai": {"gpt-4o": {"input_per_1k": "abc", "output_per_1k": "0.02"}}},
        )
        assert find_pricing("openai", "gpt-4o") == {"input_per_1k": 0.0025, "output_per_1k": 0.01}

    def test_configured_cache_rates_reach_the_display_path(self, monkeypatch):
        monkeypatch.setattr(
            llm_pricing,
            "get_db_pricing_nested",
            lambda tenant: {
                "openai": {"gpt-4o": {"input_per_1k": 0.005, "output_per_1k": 0.02, "cache_read_per_1k": 0.0005}}
            },
        )
        pricing = find_pricing("openai", "gpt-4o")
        assert pricing["cache_read_per_1k"] == 0.0005
        assert "cache_creation_per_1k" not in pricing

    def test_provider_whitespace_is_normalized(self):
        assert find_pricing(" OpenAI ", "gpt-4o")["input_per_1k"] == 0.0025


class TestDefaultRowPrecedenceMatchesTheLedger:
    @pytest.fixture(autouse=True)
    def _no_db_rates(self, no_db_rates):
        pass

    def test_ledger_bundled_exact_hit_beats_a_configured_default(self):
        configured = {"openai": {"_default": {"input_per_1k": "9", "output_per_1k": "9"}}}
        res = resolve_pricing("openai", "gpt-4o", configured)
        assert res.status is PricingStatus.FALLBACK
        assert res.input_per_1k == Decimal("0.0025")

    def test_display_bundled_exact_hit_beats_a_configured_default(self, monkeypatch):
        monkeypatch.setattr(
            llm_pricing,
            "get_db_pricing_nested",
            lambda tenant: {"openai": {"_default": {"input_per_1k": 9.0, "output_per_1k": 9.0}}},
        )
        assert find_pricing("openai", "gpt-4o")["input_per_1k"] == 0.0025

    def test_display_configured_default_wins_only_on_a_total_miss(self, monkeypatch):
        monkeypatch.setattr(
            llm_pricing,
            "get_db_pricing_nested",
            lambda tenant: {"openrouter": {"_default": {"input_per_1k": 0.5, "output_per_1k": 0.9}}},
        )
        assert find_pricing("openrouter", "some/new-model")["input_per_1k"] == 0.5

    def test_db_rate_overrides_static(self, monkeypatch):
        monkeypatch.setattr(
            llm_pricing,
            "get_db_pricing_nested",
            lambda tenant: {"openai": {"gpt-4o": {"input_per_1k": 0.005, "output_per_1k": 0.02}}},
        )
        assert find_pricing("openai", "gpt-4o")["input_per_1k"] == 0.005

_BUNDLED_WITH_CACHE = {
    "us.amazon.nova-2-lite-v1:0": {
        "input_per_1k": 0.001,
        "output_per_1k": 0.002,
        "cache_read_per_1k": 0.0004,
        "cache_creation_per_1k": 0.0,
    }
}


@pytest.fixture
def bundled_bedrock_row(monkeypatch):
    monkeypatch.setitem(
        llm_pricing.STATIC_LLM_PRICING_FALLBACK,
        "bedrock",
        {"us.amazon.nova-2-lite-v1:0": {"input_per_1k": 0.001, "output_per_1k": 0.002}},
    )


@pytest.fixture
def bundled_cache_rates(monkeypatch):
    monkeypatch.setitem(llm_pricing.STATIC_LLM_PRICING_FALLBACK, "bedrock", _BUNDLED_WITH_CACHE)


class TestBundledCacheRateProvenance:
    def test_no_bedrock_rate_is_bundled_at_all(self):
        assert llm_pricing.STATIC_LLM_PRICING_FALLBACK["bedrock"] == {}

    def test_an_exact_bundled_match_supplies_both_buckets(self, bundled_cache_rates):
        res = resolve_pricing("bedrock", "us.amazon.nova-2-lite-v1:0", {})
        assert res.cache_read_per_1k == Decimal("0.0004")
        assert res.cache_creation_per_1k == Decimal("0")

    @pytest.mark.parametrize(
        "model",
        ["eu.amazon.nova-2-lite-v1:0", "apac.amazon.nova-2-lite-v1:0", "amazon.nova-2-lite-v1:0"],
    )
    def test_a_bundled_row_prices_nothing_outside_its_own_geography(self, bundled_cache_rates, model):
        res = resolve_pricing("bedrock", model, {})
        assert res.status is PricingStatus.UNPRICED
        assert (res.cache_read_per_1k, res.cache_creation_per_1k) == (None, None)

    @pytest.mark.parametrize(
        ("provider", "model", "expected_base"),
        [
            ("bedrock", "us.amazon.nova-2-lite-v1:0-future", Decimal("0.001")),
            ("openai", "gpt-4o-mini-2024-07-18", Decimal("0.00015")),
        ],
    )
    def test_a_longest_prefix_match_takes_the_base_rate_but_not_the_cache_rates(
        self, bundled_cache_rates, monkeypatch, provider, model, expected_base
    ):
        monkeypatch.setitem(
            llm_pricing.STATIC_LLM_PRICING_FALLBACK["openai"],
            "gpt-4o-mini",
            {"input_per_1k": 0.00015, "output_per_1k": 0.0006, "cache_read_per_1k": 0.001},
        )
        res = resolve_pricing(provider, model, {})
        assert res.input_per_1k == expected_base, "version suffixes still price off the base model"
        assert res.cache_read_per_1k is None

    def test_a_configured_region_less_rate_is_always_allowed(self, bundled_cache_rates):
        configured = {
            "bedrock": {
                "amazon.nova-2-lite-v1:0": {
                    "input_per_1k": "0.001",
                    "output_per_1k": "0.002",
                    "cache_read_per_1k": "0.00009",
                }
            }
        }
        res = resolve_pricing("bedrock", "eu.amazon.nova-2-lite-v1:0", configured)
        assert res.cache_read_per_1k == Decimal("0.00009")


class TestCacheRateLadder:
    def test_configured_beats_bundled_beats_family(self, bundled_cache_rates):
        configured = {
            "bedrock": {
                "us.amazon.nova-2-lite-v1:0": {
                    "input_per_1k": "0.001",
                    "output_per_1k": "0.002",
                    "cache_read_per_1k": "0.00001",
                }
            }
        }
        res = resolve_pricing("bedrock", "us.amazon.nova-2-lite-v1:0", configured)
        assert res.cache_read_per_1k == Decimal("0.00001"), "the tenant's own rate wins"
        assert res.cache_creation_per_1k == Decimal("0"), "the omitted bucket is inherited from the bundled row"

    @pytest.mark.parametrize(
        "model",
        [
            "us.anthropic.claude-sonnet-4-v1:0",
            "global.anthropic.claude-sonnet-5",
            "us.anthropic.claude-fable-5",
        ],
    )
    def test_claude_on_bedrock_falls_back_to_the_anthropic_multipliers(self, model):
        configured = {"bedrock": {model: {"input_per_1k": "0.003", "output_per_1k": "0.015"}}}
        res = resolve_pricing("bedrock", model, configured)
        assert res.cache_read_per_1k == Decimal("0.0003")
        assert res.cache_creation_per_1k == Decimal("0.00375")

    @pytest.mark.parametrize("model", ["us.amazon.nova-2-lite-v1:0", "amazon.titan-text-express-v1"])
    def test_no_other_bedrock_family_invents_a_multiplier(self, model):
        configured = {"bedrock": {model: {"input_per_1k": "0.001", "output_per_1k": "0.002"}}}
        res = resolve_pricing("bedrock", model, configured)
        assert res.cache_read_per_1k is None
        assert res.cache_creation_per_1k is None

    def test_a_bundled_default_row_never_supplies_cache_rates(self, no_db_rates, monkeypatch):
        monkeypatch.setitem(
            llm_pricing.STATIC_LLM_PRICING_FALLBACK["openrouter"],
            "_default",
            {"input_per_1k": 0.001, "output_per_1k": 0.002, "cache_read_per_1k": 0.5},
        )
        live = llm_pricing.resolve_live_pricing("openrouter", "some/new-model")
        assert live.display_rates["input_per_1k"] == 0.001, "the base rates still come off that row"
        assert live.cache_read_per_1k is None

    def test_an_explicit_zero_is_never_mistaken_for_unresolved(self):
        configured = {
            "bedrock": {
                "us.amazon.nova-2-lite-v1:0": {
                    "input_per_1k": "0.001",
                    "output_per_1k": "0.002",
                    "cache_read_per_1k": "0",
                    "cache_creation_per_1k": "0",
                }
            }
        }
        res = resolve_pricing("bedrock", "us.amazon.nova-2-lite-v1:0", configured)
        assert (res.cache_read_per_1k, res.cache_creation_per_1k) == (Decimal("0"), Decimal("0"))


_READ_ONLY = {"input_per_1k": "0.001", "output_per_1k": "0.002", "cache_read_per_1k": "0.0001"}


class TestBucketIndependence:

    def test_read_activity_prices_from_a_read_rate_alone(self):
        out = _resolve_cost("bedrock", "m", 10, 10, {"bedrock": {"m": _READ_ONLY}}, cache_read_tokens=1000)
        assert out["pricing_status"] == "configured"
        assert out["cost_usd"] == Decimal("0.00013")

    def test_write_activity_without_a_write_rate_is_unpriced(self):
        out = _resolve_cost("bedrock", "m", 10, 10, {"bedrock": {"m": _READ_ONLY}}, cache_creation_tokens=1000)
        assert out["pricing_status"] == "unpriced"
        assert out["cost_usd"] is None
        assert out["cache_read_per_1k"] == Decimal("0.0001"), "the resolved bucket survives on the row"
        assert out["cache_creation_per_1k"] is None

    def test_no_cache_activity_prices_normally_whatever_the_buckets_resolved_to(self):
        base = {"input_per_1k": "0.001", "output_per_1k": "0.002"}
        out = _resolve_cost("bedrock", "m", 1000, 1000, {"bedrock": {"m": base}})
        assert out["pricing_status"] == "configured"
        assert out["cost_usd"] == Decimal("0.003")

    def test_an_inclusive_provider_keeps_pricing_without_any_cache_rate(self):
        out = _resolve_cost("openai", "gpt-4o", 1000, 500, {}, cache_read_tokens=400)
        assert out["pricing_status"] == "fallback"
        assert out["cost_usd"] == _resolve_cost("openai", "gpt-4o", 1000, 500, {})["cost_usd"]


_PARITY_CASES = {
    "bedrock_mirrored_fixture": (("bedrock", "us.amazon.nova-2-lite-v1:0", 7, 20, 3697, 0), MIRRORED_BEDROCK_RATES),
    "anthropic_family_defaults": (("anthropic", "claude-3-5-sonnet", 1000, 200, 500, 100), {}),
    "explicit_zero_rates": (
        ("bedrock", "us.amazon.nova-2-lite-v1:0", 100, 10, 1000, 2000),
        {
            "bedrock": {
                "us.amazon.nova-2-lite-v1:0": {
                    "input_per_1k": "0.0001",
                    "output_per_1k": "0.0004",
                    "cache_read_per_1k": "0.000025",
                    "cache_creation_per_1k": "0",
                }
            }
        },
    ),
    "cache_exceeds_input": (("anthropic", "claude-3-5-sonnet", 100, 0, 600, 0), {}),
    "inclusive_without_cache_rates": (("openai", "gpt-4o", 1000, 500, 400, 100), {}),
    "no_cache_activity": (("openai", "gpt-4o", 1000, 500, 0, 0), {}),
}


class TestLiveLedgerParity:
    @pytest.mark.parametrize("case", sorted(_PARITY_CASES))
    def test_the_display_cost_matches_the_ledger_on_every_priced_case(self, case, monkeypatch):
        args, configured = _PARITY_CASES[case]
        monkeypatch.setattr(llm_pricing, "get_db_pricing_nested", lambda tenant: configured)
        provider, model, input_tokens, output_tokens, cache_read, cache_creation = args

        ledger = _resolve_cost(
            provider,
            model,
            input_tokens,
            output_tokens,
            configured,
            cache_read_tokens=cache_read,
            cache_creation_tokens=cache_creation,
        )
        assert ledger["cost_usd"] is not None, "parity is only claimed where the ledger prices"
        live = LlmCostCalculator().calculate_cost(
            provider, model, input_tokens, output_tokens, cache_read, cache_creation
        )
        assert live == round(float(ledger["cost_usd"]), 6)

    def test_an_unresolved_bedrock_bucket_splits_the_two_surfaces(self, bundled_bedrock_row, no_db_rates):
        args = ("bedrock", "us.amazon.nova-2-lite-v1:0", 7, 20, 3697, 0)

        ledger = _resolve_cost(*args[:4], {}, cache_read_tokens=args[4], cache_creation_tokens=args[5])
        assert ledger["cost_usd"] is None
        assert ledger["pricing_status"] == PricingStatus.UNPRICED.value

        live = LlmCostCalculator().calculate_cost(*args)
        assert live == round((7 / 1000) * 0.001 + (20 / 1000) * 0.002 + (3697 / 1000) * 0.001, 6)
        assert live == LlmCostCalculator().calculate_cost("bedrock", args[1], 7 + 3697, 20)

    def test_the_shipped_bedrock_table_splits_them_the_same_way(self, no_db_rates):
        args = ("bedrock", "us.amazon.nova-2-lite-v1:0", 7, 20, 3697, 0)

        ledger = _resolve_cost(*args[:4], {}, cache_read_tokens=args[4], cache_creation_tokens=args[5])
        assert ledger["cost_usd"] is None

        live = LlmCostCalculator().calculate_cost(*args)
        assert live == round(
            (7 + 3697) / 1000 * DEFAULT_PRICING["input_per_1k"] + (20 / 1000) * DEFAULT_PRICING["output_per_1k"], 6
        )


class TestFindPricingIgnoresTheResolutionLadder:

    def test_inherited_bundled_cache_rates_stay_out_of_the_display_dict(self, monkeypatch, bundled_cache_rates):
        configured = {"bedrock": {"us.amazon.nova-2-lite-v1:0": {"input_per_1k": 0.005, "output_per_1k": 0.02}}}
        monkeypatch.setattr(llm_pricing, "get_db_pricing_nested", lambda tenant: configured)

        assert find_pricing("bedrock", "us.amazon.nova-2-lite-v1:0") == {"input_per_1k": 0.005, "output_per_1k": 0.02}
        live = llm_pricing.resolve_live_pricing("bedrock", "us.amazon.nova-2-lite-v1:0")
        assert live.cache_read_per_1k == 0.0004, "the calculator still gets the inherited rate"
        assert live.cache_creation_per_1k == 0.0

    def test_family_derived_cache_rates_stay_out_of_the_display_dict(self, no_db_rates):
        assert find_pricing("anthropic", "claude-3-5-sonnet") == {"input_per_1k": 0.003, "output_per_1k": 0.015}


class TestPricingLayering:
    def test_llm_pricing_does_not_import_the_workflow_package(self):
        source = Path(llm_pricing.__file__).read_text()
        assert "app.modules.workflow" not in source
        assert "app/modules/workflow" not in source
