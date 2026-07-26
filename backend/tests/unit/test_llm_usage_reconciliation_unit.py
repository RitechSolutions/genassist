"""Unit tests for the reconciliation service: cost self-check, day gating, sweep window"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.core.config.settings import settings
from app.services.llm_usage_reconciliation import LlmUsageReconciliationService
from app.services.llm_usage_shadow_window import GATE_VERSION, SHADOW_QUALIFYING_WINDOW_DAYS


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


class FakeReconRepo:

    def __init__(self):
        self.intervals = []
        self.upserted = []
        self.reports = {}
        self.unpriced = []
        self.analyst_disc = []
        self.report_ranges = []

    def _seen(self, start, end):
        self.intervals.append((start, end))

    async def reports_between(self, from_date, to_date):
        self.report_ranges.append((from_date, to_date))
        return [r for d, r in sorted(self.reports.items()) if from_date <= d <= to_date]

    async def upsert_report(self, **data):
        self.upserted.append(data)
        self.reports[data["report_date"]] = SimpleNamespace(
            report_date=data["report_date"], passed=data["passed"], metrics=data["metrics"]
        )

    async def logs_without_receipts(self, start, end):
        self._seen(start, end)
        return []

    async def recorder_integrity(self, start, end):
        return 0, []

    async def token_parity_mismatches(self, start, end):
        return []

    async def priced_events(self, start, end):
        return []

    async def unpriced_events(self, start, end):
        return list(self.unpriced)

    async def joined_execution_count(self, start, end):
        return 0

    async def capture_run_count(self, start, end):
        return 4

    async def receipts_without_logs(self, start, end):
        return []

    async def ledger_cost_by_status(self, start, end):
        return {}

    async def daily_stats_cost(self, day):
        return Decimal(0)

    async def analyst_completeness(self, start, end):
        return 0, 0

    async def analyst_receipt_discrepancies(self, start, end):
        return list(self.analyst_disc)


class FakeControlRepo:
    def __init__(self, control):
        self.control = control
        self.stamped = 0

    async def get_singleton(self):
        return self.control

    async def mark_shadow_passed(self):
        self.stamped += 1
        return self.control


def _control(**overrides):
    base = dict(
        capture_enabled=True,
        capture_started_at=None,
        shadow_started_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        shadow_passed_at=None,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _service(control=None, repo=None):
    repo = repo or FakeReconRepo()
    control_repo = FakeControlRepo(control if control is not None else _control())
    return LlmUsageReconciliationService(repo, control_repo), repo, control_repo


def _passed_report(day, gate_version=GATE_VERSION, capture_runs=4):
    return SimpleNamespace(
        report_date=day,
        passed=True,
        metrics={"capture_runs": capture_runs, "gate_version": gate_version},
    )


class TestDayGates:
    @pytest.mark.asyncio
    async def test_clean_day_passes(self):
        service, _, _ = _service()
        report = await service._evaluate_day(date(2026, 7, 1))
        assert report["passed"] is True
        assert report["metrics"]["capture_runs"] == 4

    @pytest.mark.asyncio
    async def test_unpriced_event_fails_the_day(self):
        service, repo, _ = _service()
        repo.unpriced = [{"execution_id": "e1", "call_index": 0, "provider": "", "model": ""}]

        report = await service._evaluate_day(date(2026, 7, 1))
        assert report["passed"] is False
        assert report["metrics"]["unpriced_events"] == 1
        assert report["reasons"]["hard_gates"]["unpriced_events"]["passed"] is False

    @pytest.mark.asyncio
    async def test_analyst_receipt_gap_fails_the_day(self):
        service, repo, _ = _service()
        repo.analyst_disc = [{"execution_id": "analyst:1:0", "expected": 1, "persisted": 0, "events": 0}]

        report = await service._evaluate_day(date(2026, 7, 1))
        assert report["passed"] is False
        assert report["metrics"]["analyst_discrepancies"] == 1
        assert report["reasons"]["hard_gates"]["analyst_completeness"]["passed"] is False

    @pytest.mark.asyncio
    async def test_analyst_receipt_whose_event_vanished_fails_the_day(self):
        service, repo, _ = _service()
        repo.analyst_disc = [{"execution_id": "analyst:1:0", "expected": 1, "persisted": 1, "events": 0}]

        report = await service._evaluate_day(date(2026, 7, 1))
        assert report["passed"] is False
        assert report["reasons"]["hard_gates"]["analyst_completeness"]["discrepancies"][0]["events"] == 0

    @pytest.mark.asyncio
    async def test_receipts_without_logs_stay_a_diagnostic(self):
        service, repo, _ = _service()
        repo.receipts_without_logs = lambda start, end: _async([("api-run", "completed")])

        report = await service._evaluate_day(date(2026, 7, 1))
        assert report["passed"] is True
        assert report["reasons"]["soft"]["receipts_without_logs"]["count"] == 1


class TestActivationDay:
    @pytest.mark.asyncio
    async def test_interval_starts_at_midnight_without_capture_stamp(self):
        service, repo, _ = _service()
        report = await service._evaluate_day(date(2026, 7, 1))
        assert report["interval_start"] == datetime(2026, 7, 1, tzinfo=timezone.utc)

    @pytest.mark.asyncio
    async def test_activation_day_starts_when_capture_did(self):
        service, repo, _ = _service()
        started = datetime(2026, 7, 1, 14, 30, tzinfo=timezone.utc)

        report = await service._evaluate_day(date(2026, 7, 1), started)

        assert report["interval_start"] == started
        assert report["interval_end"] == datetime(2026, 7, 2, tzinfo=timezone.utc)
        assert repo.intervals[0][0] == started

    @pytest.mark.asyncio
    async def test_days_after_activation_keep_the_whole_day(self):
        service, repo, _ = _service()
        started = datetime(2026, 6, 20, 14, 30, tzinfo=timezone.utc)

        report = await service._evaluate_day(date(2026, 7, 1), started)
        assert report["interval_start"] == datetime(2026, 7, 1, tzinfo=timezone.utc)


class TestReconcileSweep:
    @staticmethod
    def _today():
        from app.core.utils.date_time_utils import utc_now

        return utc_now().date()

    @pytest.mark.asyncio
    async def test_skips_when_shadow_never_started(self):
        service, _, _ = _service(control=_control(shadow_started_at=None))
        assert (await service.reconcile())["reason"] == "shadow_not_started"

    @pytest.mark.asyncio
    async def test_sweep_is_bounded_by_the_lookback_setting(self, monkeypatch):
        monkeypatch.setattr(settings, "LLM_USAGE_SHADOW_LOOKBACK_DAYS", 14)
        long_ago = datetime.now(timezone.utc) - timedelta(days=400)
        service, repo, _ = _service(control=_control(shadow_started_at=long_ago))

        result = await service.reconcile()

        assert len(result["evaluated"]) == 14
        assert repo.report_ranges[0] == (self._today() - timedelta(days=14), self._today() - timedelta(days=1))

    @pytest.mark.asyncio
    async def test_sweep_never_shrinks_below_the_qualifying_window(self, monkeypatch):
        monkeypatch.setattr(settings, "LLM_USAGE_SHADOW_LOOKBACK_DAYS", 2)
        long_ago = datetime.now(timezone.utc) - timedelta(days=400)
        service, repo, _ = _service(control=_control(shadow_started_at=long_ago))

        result = await service.reconcile()

        assert len(result["evaluated"]) == SHADOW_QUALIFYING_WINDOW_DAYS
        assert repo.report_ranges[0][0] == self._today() - timedelta(days=SHADOW_QUALIFYING_WINDOW_DAYS)

    @pytest.mark.asyncio
    async def test_monitoring_continues_after_the_pass_without_restamping(self, monkeypatch):
        monkeypatch.setattr(settings, "LLM_USAGE_SHADOW_LOOKBACK_DAYS", 7)
        passed_at = datetime(2026, 1, 5, tzinfo=timezone.utc)
        control = _control(shadow_passed_at=passed_at)
        service, repo, control_repo = _service(control=control)

        result = await service.reconcile()

        assert result["status"] == "completed"
        assert len(result["evaluated"]) == 7
        assert result["shadow_passed"] is False
        assert control_repo.stamped == 0
        assert control.shadow_passed_at == passed_at

    @pytest.mark.asyncio
    async def test_passing_days_are_not_re_evaluated(self, monkeypatch):
        monkeypatch.setattr(settings, "LLM_USAGE_SHADOW_LOOKBACK_DAYS", 7)
        service, repo, _ = _service()
        already = self._today() - timedelta(days=2)
        repo.reports[already] = _passed_report(already)

        result = await service.reconcile()

        assert already.isoformat() not in [e["date"] for e in result["evaluated"]]

    @pytest.mark.asyncio
    async def test_failed_days_are_re_evaluated(self, monkeypatch):
        monkeypatch.setattr(settings, "LLM_USAGE_SHADOW_LOOKBACK_DAYS", 7)
        service, repo, _ = _service()
        failed = self._today() - timedelta(days=2)
        repo.reports[failed] = SimpleNamespace(report_date=failed, passed=False, metrics={})

        result = await service.reconcile()

        assert failed.isoformat() in [e["date"] for e in result["evaluated"]]

    @pytest.mark.asyncio
    async def test_days_graded_by_an_older_gate_set_are_re_evaluated(self, monkeypatch):
        monkeypatch.setattr(settings, "LLM_USAGE_SHADOW_LOOKBACK_DAYS", 7)
        service, repo, _ = _service()
        stale = self._today() - timedelta(days=2)
        repo.reports[stale] = _passed_report(stale, gate_version=GATE_VERSION - 1)

        result = await service.reconcile()

        assert stale.isoformat() in [e["date"] for e in result["evaluated"]]

    @pytest.mark.asyncio
    async def test_legacy_reports_without_a_version_are_re_evaluated(self, monkeypatch):
        monkeypatch.setattr(settings, "LLM_USAGE_SHADOW_LOOKBACK_DAYS", 7)
        service, repo, _ = _service()
        legacy = self._today() - timedelta(days=2)
        repo.reports[legacy] = SimpleNamespace(report_date=legacy, passed=True, metrics={"joined_executions": 5})

        result = await service.reconcile()

        assert legacy.isoformat() in [e["date"] for e in result["evaluated"]]

    @pytest.mark.asyncio
    async def test_fresh_reports_carry_the_current_gate_version(self, monkeypatch):
        monkeypatch.setattr(settings, "LLM_USAGE_SHADOW_LOOKBACK_DAYS", 7)
        service, repo, _ = _service()

        await service.reconcile()

        assert all(d["metrics"]["gate_version"] == GATE_VERSION for d in repo.upserted)

    @pytest.mark.asyncio
    async def test_activation_stamp_is_passed_into_each_day(self, monkeypatch):
        monkeypatch.setattr(settings, "LLM_USAGE_SHADOW_LOOKBACK_DAYS", 7)
        started = datetime.now(timezone.utc) - timedelta(days=1, hours=6)
        service, repo, _ = _service(control=_control(capture_started_at=started))

        await service.reconcile()

        assert any(interval[0] == started for interval in repo.intervals)


async def _async(value):
    return value


class TestReportReadsAreFresh:

    @staticmethod
    def _captured_select(coro_factory):
        import asyncio

        class Cap:
            def __init__(self):
                self.stmt = None

            async def execute(self, stmt):
                self.stmt = stmt

                class R:
                    def scalars(self_):
                        class S:
                            def all(s_):
                                return []

                        return S()

                return R()

        from app.repositories.llm_usage_reconciliation import LlmUsageReconciliationRepository

        cap = Cap()
        repo = LlmUsageReconciliationRepository.__new__(LlmUsageReconciliationRepository)
        repo.db = cap
        asyncio.run(coro_factory(repo))
        return cap.stmt

    def test_reports_between_repopulates_loaded_instances(self):
        stmt = self._captured_select(lambda r: r.reports_between(date(2026, 7, 19), date(2026, 7, 25)))
        assert stmt.get_execution_options().get("populate_existing") is True

    def test_upsert_revives_a_soft_deleted_report(self):
        import asyncio

        from sqlalchemy.dialects import postgresql

        from app.repositories.llm_usage_reconciliation import LlmUsageReconciliationRepository

        class Cap:
            def __init__(self):
                self.stmt = None

            async def execute(self, stmt):
                self.stmt = stmt

            async def commit(self):
                pass

        cap = Cap()
        repo = LlmUsageReconciliationRepository.__new__(LlmUsageReconciliationRepository)
        repo.db = cap
        asyncio.run(
            repo.upsert_report(
                report_date=date(2026, 7, 20),
                interval_start=datetime(2026, 7, 20, tzinfo=timezone.utc),
                interval_end=datetime(2026, 7, 21, tzinfo=timezone.utc),
                passed=True,
                reasons={},
                metrics={},
            )
        )
        update_clause = str(cap.stmt.compile(dialect=postgresql.dialect())).split("DO UPDATE SET")[1]
        assert "is_deleted" in update_clause
