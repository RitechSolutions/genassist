"""Unit tests for the analytics Celery wrappers' failure surfacing"""

import asyncio

import pytest

import app.tasks.base as task_base
from app.core.config.settings import settings
from app.tasks.analytics_aggregation_tasks import (
    _sum_nested_result,
    aggregate_agent_analytics_async_with_scope,
    backfill_agent_analytics_async_with_scope,
)

SUCCESS_ENTRY = {"tenant_id": None, "tenant_name": "master", "tenant_slug": "master", "result": {"status": "completed"}}


def _run_scheduled(monkeypatch, payload, v2):
    async def fake_run(*args, **kwargs):
        return payload

    monkeypatch.setattr(task_base, "run_task_with_tenant_support", fake_run)
    monkeypatch.setattr(settings, "ANALYTICS_AGG_V2", v2)
    return asyncio.run(aggregate_agent_analytics_async_with_scope())


def _run_backfill(monkeypatch, result, v2):
    async def fake_run(*args, **kwargs):
        return result

    monkeypatch.setattr(task_base, "run_task_for_tenant", fake_run)
    monkeypatch.setattr(settings, "ANALYTICS_AGG_V2", v2)
    return asyncio.run(backfill_agent_analytics_async_with_scope(tenant_id="master"))


class TestScheduledAggregationWrapper:
    def test_v18_tenant_error_entry_raises_with_count_only(self, monkeypatch):
        payload = {
            "status": "success",
            "results": [SUCCESS_ENTRY, {"tenant_id": "t1", "tenant_slug": "t1", "error": "boom"}],
        }
        with pytest.raises(RuntimeError) as exc:
            _run_scheduled(monkeypatch, payload, v2=True)
        assert "1 tenant run(s)" in str(exc.value)
        assert "boom" not in str(exc.value)

    def test_v18_outer_failed_status_raises(self, monkeypatch):
        with pytest.raises(RuntimeError):
            _run_scheduled(monkeypatch, {"status": "failed", "error": "helper blew up"}, v2=True)

    def test_v19_error_entry_is_surfaced_whatever_its_message(self, monkeypatch):
        payload = {"status": "success", "results": [{"tenant_id": "t1", "error": "SoftTimeLimitExceeded()"}]}
        with pytest.raises(RuntimeError):
            _run_scheduled(monkeypatch, payload, v2=True)

    def test_v19b_empty_error_string_still_detected_by_key(self, monkeypatch):
        payload = {"status": "success", "results": [{"tenant_id": "t1", "error": ""}]}
        with pytest.raises(RuntimeError):
            _run_scheduled(monkeypatch, payload, v2=True)

    def test_all_success_returns_payload_untouched(self, monkeypatch):
        payload = {"status": "success", "results": [SUCCESS_ENTRY]}
        assert _run_scheduled(monkeypatch, payload, v2=True) is payload

    def test_incomplete_dates_fail_the_run_without_any_tenant_error(self, monkeypatch):
        payload = {
            "status": "success",
            "results": [{"tenant_id": "t1", "result": {"dates_not_reconciled": 2}}],
        }
        with pytest.raises(RuntimeError) as exc:
            _run_scheduled(monkeypatch, payload, v2=True)
        assert "0 tenant run(s)" in str(exc.value)
        assert "2 date(s) left incomplete" in str(exc.value)
        assert "t1" not in str(exc.value)

    def test_a_skipped_today_rebuild_also_fails_the_run(self, monkeypatch):
        payload = {
            "status": "success",
            "results": [{"tenant_id": "t1", "result": {"today_rebuild_failed": True}}],
        }
        with pytest.raises(RuntimeError):
            _run_scheduled(monkeypatch, payload, v2=True)

    def test_flag_off_never_raises_on_incomplete_dates(self, monkeypatch):
        payload = {
            "status": "success",
            "results": [{"tenant_id": "t1", "result": {"dates_not_reconciled": 2}}],
        }
        assert _run_scheduled(monkeypatch, payload, v2=False) is payload

    def test_empty_result_set_counts_as_failure_under_v2(self, monkeypatch):
        payload = {"status": "success", "results": []}
        with pytest.raises(RuntimeError):
            _run_scheduled(monkeypatch, payload, v2=True)
        assert _run_scheduled(monkeypatch, payload, v2=False) is payload

    def test_flag_off_never_raises_on_failures(self, monkeypatch):
        payload = {"status": "success", "results": [{"tenant_id": "t1", "error": "SoftTimeLimitExceeded()"}]}
        assert _run_scheduled(monkeypatch, payload, v2=False) is payload
        outer = {"status": "failed", "error": "x"}
        assert _run_scheduled(monkeypatch, outer, v2=False) is outer


class TestNestedResultCounters:
    def test_summed_from_the_nested_tenant_result(self):
        results = [
            SUCCESS_ENTRY,
            {"tenant_id": "t1", "result": {"today_rebuild_failed": True, "dates_not_reconciled": 2}},
            {"tenant_id": "t2", "result": {"today_rebuild_failed": False, "dates_not_reconciled": 1}},
        ]
        assert _sum_nested_result(results, "today_rebuild_failed") == 1
        assert _sum_nested_result(results, "dates_not_reconciled") == 3

    def test_error_and_legacy_entries_are_ignored(self):
        results = [
            {"tenant_id": "t1", "error": "boom"},
            {"tenant_id": "t2", "result": {"agent_stats_upserted": 0}},
        ]
        assert _sum_nested_result(results, "today_rebuild_failed") == 0
        assert _sum_nested_result(results, "dates_not_reconciled") == 0


class TestBackfillWrapper:
    def test_v20_failed_payload_raises_under_v2(self, monkeypatch):
        result = {"status": "failed", "tenant_id": "t1", "error": "SoftTimeLimitExceeded()"}
        with pytest.raises(RuntimeError):
            _run_backfill(monkeypatch, result, v2=True)

    def test_v20_flag_off_returns_failed_payload_unchanged(self, monkeypatch):
        result = {"status": "failed", "tenant_id": "t1", "error": "boom"}
        assert _run_backfill(monkeypatch, result, v2=False) is result

    def test_success_passes_through_under_v2(self, monkeypatch):
        result = {"status": "success", "tenant_id": "t1", "result": {"status": "completed"}}
        assert _run_backfill(monkeypatch, result, v2=True) is result

    def test_incomplete_dates_raise_on_an_otherwise_successful_backfill(self, monkeypatch):
        result = {"status": "success", "tenant_id": "t1", "result": {"dates_not_reconciled": 1}}
        with pytest.raises(RuntimeError) as exc:
            _run_backfill(monkeypatch, result, v2=True)
        assert "1 date(s) left incomplete" in str(exc.value)
