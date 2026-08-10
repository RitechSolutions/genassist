"""Unit tests for the legacy backfill eligibility + pricing-status logic"""

import json
from decimal import Decimal

from app.repositories.llm_usage_backfill import _FORCE_UPDATE_COLUMNS
from app.services.llm_usage_backfill import _check_parity, _payload_usage, resolve_backfill_usage


def test_force_update_restamps_attribution():
    assert {"agent_id", "workflow_id"} <= set(_FORCE_UPDATE_COLUMNS)


EMPTY = {"input_tokens": None, "output_tokens": None, "total_tokens": None, "cost_usd": None}


def _typed(**overrides):
    return {**EMPTY, **overrides}


class TestPayloadUsage:
    def test_extracts_token_usage_and_cost(self):
        raw = json.dumps({"token_usage": {"input_tokens": 3, "output_tokens": 4, "total_tokens": 7}, "cost_usd": 0.5})
        assert _payload_usage(raw) == {
            "input_tokens": 3,
            "output_tokens": 4,
            "total_tokens": 7,
            "cost_usd": 0.5,
        }

    def test_accepts_already_parsed_dict(self):
        payload = {"token_usage": {"input_tokens": 1}, "cost_usd": None}
        assert _payload_usage(payload)["input_tokens"] == 1

    def test_bad_json_returns_empty(self):
        assert _payload_usage("{not json") == {}

    def test_non_dict_payload_returns_empty(self):
        assert _payload_usage(json.dumps([1, 2, 3])) == {}
        assert _payload_usage("") == {}
        assert _payload_usage(None) == {}

    def test_missing_token_usage_yields_none_fields(self):
        assert _payload_usage(json.dumps({"cost_usd": 1})) == {
            "input_tokens": None,
            "output_tokens": None,
            "total_tokens": None,
            "cost_usd": 1,
        }


class TestResolveBackfillUsage:
    def test_all_none_is_skipped(self):
        assert resolve_backfill_usage(_typed(), {}) is None

    def test_typed_values_win_over_payload(self):
        payload = {"input_tokens": 99, "output_tokens": 99, "total_tokens": 99, "cost_usd": 9.9}
        out = resolve_backfill_usage(_typed(input_tokens=1, output_tokens=2, total_tokens=3, cost_usd=0.4), payload)
        assert (out.input_tokens, out.output_tokens, out.total_tokens) == (1, 2, 3)
        assert out.cost_usd == Decimal("0.4")
        assert out.pricing_status == "legacy_estimate"

    def test_payload_fills_only_none_gaps(self):
        out = resolve_backfill_usage(
            _typed(input_tokens=10, output_tokens=5, total_tokens=15),
            {"input_tokens": 999, "cost_usd": 0.25},
        )
        assert (out.input_tokens, out.output_tokens, out.total_tokens) == (10, 5, 15)
        assert out.cost_usd == Decimal("0.25")
        assert out.pricing_status == "legacy_estimate"

    def test_tokens_without_cost_are_unpriced(self):
        out = resolve_backfill_usage(_typed(input_tokens=10, output_tokens=5, total_tokens=15), {})
        assert out.cost_usd is None
        assert out.pricing_status == "unpriced"

    def test_explicit_zero_cost_is_legacy_estimate(self):
        out = resolve_backfill_usage(
            _typed(input_tokens=1, output_tokens=1, total_tokens=2, cost_usd=0.0),
            {"cost_usd": 5.0},
        )
        assert out.cost_usd == Decimal("0.0")
        assert out.pricing_status == "legacy_estimate"

    def test_explicit_zero_tokens_insert_as_zero(self):
        out = resolve_backfill_usage(_typed(input_tokens=0, output_tokens=0, total_tokens=0), {})
        assert (out.input_tokens, out.output_tokens, out.total_tokens) == (0, 0, 0)
        assert out.pricing_status == "unpriced"

    def test_cost_only_row_inserts_with_zero_tokens(self):
        out = resolve_backfill_usage(_typed(cost_usd=1.5), {})
        assert (out.input_tokens, out.output_tokens, out.total_tokens) == (0, 0, 0)
        assert out.cost_usd == Decimal("1.5")

    def test_total_defaults_to_parts_when_absent(self):
        out = resolve_backfill_usage(_typed(input_tokens=4, output_tokens=6), {})
        assert out.total_tokens == 10

    def test_total_is_bumped_when_below_parts(self):
        out = resolve_backfill_usage(_typed(input_tokens=10, output_tokens=10, total_tokens=5), {})
        assert out.total_tokens == 20

    def test_cost_copied_via_decimal_str_avoids_float_noise(self):
        out = resolve_backfill_usage(_typed(input_tokens=1, cost_usd=0.1), {})
        assert out.cost_usd == Decimal("0.1")

    def test_negative_tokens_are_clamped_to_zero(self):
        out = resolve_backfill_usage(_typed(input_tokens=-5, output_tokens=-2, total_tokens=-9), {})
        assert (out.input_tokens, out.output_tokens, out.total_tokens) == (0, 0, 0)

    def test_non_numeric_payload_values_are_dropped_not_raised(self):
        out = resolve_backfill_usage(
            _typed(),
            {"input_tokens": 7, "output_tokens": "bad", "total_tokens": [1], "cost_usd": "nope"},
        )
        assert (out.input_tokens, out.output_tokens, out.total_tokens) == (7, 0, 7)
        assert out.cost_usd is None and out.pricing_status == "unpriced"

    def test_all_non_numeric_payload_is_skipped(self):
        assert resolve_backfill_usage(_typed(), {"input_tokens": "x", "cost_usd": "y"}) is None

    def test_bool_values_are_not_treated_as_numbers(self):
        assert resolve_backfill_usage(_typed(), {"cost_usd": True}) is None


class TestCheckParity:
    def _args(self, **kw):
        base = dict(
            eligible=2,
            input_sum=30,
            output_sum=15,
            total_sum=45,
            cost_sum=Decimal("0.5"),
            ledger_count=2,
            ledger_in=30,
            ledger_out=15,
            ledger_total=45,
            ledger_cost=Decimal("0.5"),
        )
        base.update(kw)
        return base

    def test_exact_match_passes(self):
        assert _check_parity(**self._args())["ok"] is True

    def test_count_mismatch_fails(self):
        out = _check_parity(**self._args(ledger_count=1))
        assert out["ok"] is False and out["counts_match"] is False

    def test_token_mismatch_fails(self):
        out = _check_parity(**self._args(ledger_total=44))
        assert out["ok"] is False and out["tokens_match"] is False

    def test_cost_within_absolute_tolerance_passes(self):
        out = _check_parity(**self._args(ledger_cost=Decimal("0.505")))
        assert out["ok"] is True and out["cost_within_tolerance"] is True

    def test_cost_beyond_tolerance_fails(self):
        out = _check_parity(**self._args(cost_sum=Decimal("100"), ledger_cost=Decimal("100.2")))
        assert out["ok"] is False and out["cost_within_tolerance"] is False
