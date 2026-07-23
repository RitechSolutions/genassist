"""Unit tests for token/cost aggregation into agent daily-stat buckets"""

import json
from datetime import date
from types import SimpleNamespace
from uuid import uuid4

from app.services.analytics_aggregation import AnalyticsAggregationService

AGENT_ID = uuid4()
STAT_DATE = date(2026, 7, 1)


def _log(payload_extra: dict | None = None, **typed):
    payload = {"agent_id": str(AGENT_ID), "status": "success"}
    if payload_extra:
        payload.update(payload_extra)
    return SimpleNamespace(
        id=uuid4(),
        raw_response=json.dumps(payload),
        conversation_id=None,
        conversation=None,
        input_tokens=typed.get("input_tokens"),
        output_tokens=typed.get("output_tokens"),
        cost_usd=typed.get("cost_usd"),
    )


def _agent_stats_row(logs: list) -> dict:
    service = AnalyticsAggregationService(repo=None)
    agent_buckets, _ = service._build_buckets_from_logs(logs, STAT_DATE)
    return service._build_agent_stats_from_buckets(agent_buckets)[0]


class TestTokenCostBuckets:
    def test_typed_columns_preferred_over_payload(self):
        log = _log(
            payload_extra={"token_usage": {"input_tokens": 999, "output_tokens": 999}, "cost_usd": 9.9},
            input_tokens=10,
            output_tokens=20,
            cost_usd=0.5,
        )
        row = _agent_stats_row([log])
        assert row["total_input_tokens"] == 10
        assert row["total_output_tokens"] == 20
        assert row["total_cost_usd"] == 0.5

    def test_payload_fallback_when_typed_columns_missing(self):
        log = _log(payload_extra={"token_usage": {"input_tokens": 7, "output_tokens": 3}, "cost_usd": 0.001})
        row = _agent_stats_row([log])
        assert row["total_input_tokens"] == 7
        assert row["total_output_tokens"] == 3
        assert row["total_cost_usd"] == 0.001

    def test_payload_fills_only_none_gaps_per_field(self):
        log = _log(
            payload_extra={"token_usage": {"input_tokens": 999, "output_tokens": 4}},
            input_tokens=5,
        )
        row = _agent_stats_row([log])
        assert row["total_input_tokens"] == 5
        assert row["total_output_tokens"] == 4

    def test_explicit_zero_usage_counts_as_data(self):
        log = _log(input_tokens=0, output_tokens=0, cost_usd=0.0)
        row = _agent_stats_row([log])
        assert row["total_input_tokens"] == 0
        assert row["total_output_tokens"] == 0
        assert row["total_cost_usd"] == 0.0

    def test_no_usage_data_anywhere_stays_null(self):
        row = _agent_stats_row([_log()])
        assert row["total_input_tokens"] is None
        assert row["total_output_tokens"] is None
        assert row["total_cost_usd"] is None

    def test_mixed_logs_sum_only_data_bearing_rows(self):
        logs = [
            _log(input_tokens=2, output_tokens=3, cost_usd=0.1),
            _log(),
            _log(input_tokens=4, output_tokens=1, cost_usd=0.2),
        ]
        row = _agent_stats_row(logs)
        assert row["total_input_tokens"] == 6
        assert row["total_output_tokens"] == 4
        assert row["total_cost_usd"] == round(0.1 + 0.2, 6)

    def test_non_numeric_payload_values_are_skipped(self):
        log = _log(payload_extra={"token_usage": {"input_tokens": "garbage"}, "cost_usd": "n/a"})
        row = _agent_stats_row([log])
        assert row["total_input_tokens"] is None
        assert row["total_cost_usd"] is None

    def test_tokens_without_cost_leave_cost_null(self):
        log = _log(input_tokens=8, output_tokens=2)
        row = _agent_stats_row([log])
        assert row["total_input_tokens"] == 8
        assert row["total_output_tokens"] == 2
        assert row["total_cost_usd"] is None
