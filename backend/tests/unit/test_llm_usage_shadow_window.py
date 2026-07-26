"""Unit tests for the shared shadow qualifying-window check"""

from datetime import date, timedelta

import pytest

from app.core.config.settings import settings
from app.services.llm_usage_shadow_window import (
    GATE_VERSION,
    SHADOW_QUALIFYING_WINDOW_DAYS,
    ShadowWindow,
    evaluate_window,
    is_stale_verdict,
    qualifying_days,
)

TODAY = date(2026, 7, 26)


class FakeReport:
    def __init__(self, report_date, passed=True, capture_runs=3, gate_version=GATE_VERSION):
        self.report_date = report_date
        self.passed = passed
        self.metrics = {"capture_runs": capture_runs, "gate_version": gate_version}


class FakeRepo:
    def __init__(self, reports):
        self.reports = reports
        self.requested = None

    async def reports_between(self, from_date, to_date):
        self.requested = (from_date, to_date)
        return [r for r in self.reports if from_date <= r.report_date <= to_date]


def _full_window(**kwargs):
    return [FakeReport(day, **kwargs) for day in qualifying_days(TODAY)]


class TestQualifyingDays:
    def test_spans_the_seven_days_before_today(self):
        days = qualifying_days(TODAY)
        assert len(days) == SHADOW_QUALIFYING_WINDOW_DAYS
        assert days[0] == TODAY - timedelta(days=7)
        assert days[-1] == TODAY - timedelta(days=1)

    def test_today_is_never_required(self):
        assert TODAY not in qualifying_days(TODAY)


class TestEvaluateWindow:
    @pytest.mark.asyncio
    async def test_full_green_window_passes(self):
        window = await evaluate_window(FakeRepo(_full_window()), TODAY)
        assert window.passed is True
        assert window.missing == [] and window.failed == []
        assert window.capture_runs == 3 * SHADOW_QUALIFYING_WINDOW_DAYS

    @pytest.mark.asyncio
    async def test_queries_exact_dates_not_a_row_limit(self):
        repo = FakeRepo(_full_window())
        await evaluate_window(repo, TODAY)
        assert repo.requested == (TODAY - timedelta(days=7), TODAY - timedelta(days=1))

    @pytest.mark.asyncio
    async def test_absent_day_is_missing_not_failed(self):
        reports = _full_window()
        gone = reports.pop(3)
        window = await evaluate_window(FakeRepo(reports), TODAY)
        assert window.missing == [gone.report_date]
        assert window.failed == []
        assert window.passed is False

    @pytest.mark.asyncio
    async def test_failed_day_is_reported_separately(self):
        reports = _full_window()
        reports[2].passed = False
        window = await evaluate_window(FakeRepo(reports), TODAY)
        assert window.failed == [reports[2].report_date]
        assert window.missing == []
        assert window.passed is False

    @pytest.mark.asyncio
    async def test_older_passing_streak_never_qualifies(self):
        stale = [FakeReport(day - timedelta(days=30)) for day in qualifying_days(TODAY)]
        window = await evaluate_window(FakeRepo(stale), TODAY)
        assert len(window.missing) == SHADOW_QUALIFYING_WINDOW_DAYS
        assert window.passed is False

    @pytest.mark.asyncio
    async def test_empty_week_fails_the_volume_gate(self):
        window = await evaluate_window(FakeRepo(_full_window(capture_runs=0)), TODAY)
        assert window.missing == [] and window.failed == []
        assert window.has_volume is False
        assert window.passed is False

    @pytest.mark.asyncio
    async def test_volume_sums_across_the_window(self, monkeypatch):
        monkeypatch.setattr(settings, "LLM_USAGE_SHADOW_MIN_CAPTURE_RUNS", 14)
        assert (await evaluate_window(FakeRepo(_full_window(capture_runs=2)), TODAY)).passed is True
        assert (await evaluate_window(FakeRepo(_full_window(capture_runs=1)), TODAY)).passed is False

    @pytest.mark.asyncio
    async def test_reports_without_metrics_count_as_no_volume(self):
        reports = _full_window()
        for r in reports:
            r.metrics = None
        window = await evaluate_window(FakeRepo(reports), TODAY)
        assert window.capture_runs == 0
        assert window.passed is False


class TestStaleVerdicts:

    def test_report_from_an_older_gate_set_is_stale(self):
        assert is_stale_verdict(FakeReport(TODAY, gate_version=GATE_VERSION - 1)) is True

    def test_report_at_the_current_version_is_fresh(self):
        assert is_stale_verdict(FakeReport(TODAY)) is False

    def test_report_predating_versioning_is_stale(self):
        legacy = FakeReport(TODAY)
        legacy.metrics = {"joined_executions": 5}
        assert is_stale_verdict(legacy) is True

    def test_missing_metrics_is_stale(self):
        legacy = FakeReport(TODAY)
        legacy.metrics = None
        assert is_stale_verdict(legacy) is True

    @pytest.mark.parametrize("metrics", [["a"], "junk", 42, {"gate_version": None}, {"gate_version": "two"}])
    def test_unreadable_metrics_count_as_stale_rather_than_raising(self, metrics):
        report = FakeReport(TODAY)
        report.metrics = metrics
        assert is_stale_verdict(report) is True

    def test_numeric_string_version_is_understood(self):
        report = FakeReport(TODAY)
        report.metrics = {"gate_version": str(GATE_VERSION)}
        assert is_stale_verdict(report) is False

    @pytest.mark.asyncio
    async def test_stale_day_blocks_the_window_and_is_named_separately(self):
        reports = _full_window()
        reports[3].metrics = {"capture_runs": 3, "gate_version": GATE_VERSION - 1}
        window = await evaluate_window(FakeRepo(reports), TODAY)

        assert window.stale == [reports[3].report_date]
        assert window.missing == [] and window.failed == []
        assert window.passed is False
        assert "awaiting re-check" in window.describe()

    @pytest.mark.asyncio
    async def test_a_failed_stale_day_is_reported_as_failed_not_stale(self):
        reports = _full_window()
        reports[2].passed = False
        reports[2].metrics = {"capture_runs": 3, "gate_version": GATE_VERSION - 1}
        window = await evaluate_window(FakeRepo(reports), TODAY)

        assert window.failed == [reports[2].report_date]
        assert window.stale == []


class TestDescribe:
    def test_green_window_says_so(self):
        window = ShadowWindow(required=qualifying_days(TODAY), capture_runs=99)
        assert window.describe() == "window is current"

    def test_lists_each_problem_it_found(self):
        window = ShadowWindow(
            required=qualifying_days(TODAY),
            missing=[date(2026, 7, 20)],
            failed=[date(2026, 7, 21)],
            stale=[date(2026, 7, 22)],
            capture_runs=0,
        )
        detail = window.describe()
        assert "missing days: ['2026-07-20']" in detail
        assert "failing days: ['2026-07-21']" in detail
        assert "awaiting re-check under the current gates: ['2026-07-22']" in detail
        assert "below minimum" in detail
