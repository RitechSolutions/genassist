"""Unit tests for the reconciliation cost self-consistency check (WS11)"""

from decimal import Decimal

from app.services.llm_usage_reconciliation import LlmUsageReconciliationService


def _row(execution_id, in_tok, out_tok, in_rate, out_rate, stored):
    return (execution_id, in_tok, out_tok, Decimal(in_rate), Decimal(out_rate), Decimal(stored))


class TestCostSelfConsistency:
    def test_consistent_cost_has_no_mismatch(self):
        # 1000/1000*0.001 + 1000/1000*0.002 = 0.003
        rows = [_row("a", 1000, 1000, "0.001", "0.002", "0.003")]
        assert LlmUsageReconciliationService._cost_self_consistency(rows) == []

    def test_corrupted_cost_flagged(self):
        rows = [_row("a", 1000, 1000, "0.001", "0.002", "9.9")]
        out = LlmUsageReconciliationService._cost_self_consistency(rows)
        assert len(out) == 1 and out[0]["execution_id"] == "a"

    def test_within_storage_precision_passes(self):
        # a sub-1e-9 difference is storage rounding, not corruption
        rows = [_row("a", 1000, 1000, "0.001", "0.002", "0.0030000000")]
        assert LlmUsageReconciliationService._cost_self_consistency(rows) == []

    def test_null_stored_cost_is_a_mismatch(self):
        rows = [("a", 1000, 1000, Decimal("0.001"), Decimal("0.002"), None)]
        out = LlmUsageReconciliationService._cost_self_consistency(rows)
        assert len(out) == 1
