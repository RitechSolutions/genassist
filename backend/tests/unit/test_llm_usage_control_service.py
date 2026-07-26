"""Unit tests for LlmUsageControlService gate logic"""

from datetime import datetime, timezone

import pytest

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.utils.date_time_utils import utc_now
from app.schemas.llm_usage_control import COST_SOURCE_DAILY_STATS, COST_SOURCE_LEDGER
from app.services.llm_usage_control import SHADOW_QUALIFYING_WINDOW_DAYS, LlmUsageControlService
from app.services.llm_usage_shadow_window import GATE_VERSION, qualifying_days


class FakeControl:
    def __init__(self):
        self.capture_enabled = False
        self.capture_started_at = None
        self.shadow_started_at = None
        self.shadow_passed_at = None
        self.ledger_cutover_enabled = False


class FakeControlRepo:

    def __init__(self, control):
        self.control = control
        self.activate_calls = 0

    async def get_singleton(self):
        return self.control

    async def activate_capture(self):
        self.activate_calls += 1
        self.control.capture_enabled = True
        if self.control.capture_started_at is None:
            self.control.capture_started_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        return self.control

    async def start_shadow(self):
        if self.control.shadow_started_at is not None:
            return False
        self.control.shadow_started_at = datetime(2026, 1, 2, tzinfo=timezone.utc)
        return True

    async def set_cutover(self, enabled):
        self.control.ledger_cutover_enabled = enabled
        return self.control


class MissingControlRepo:
    async def get_singleton(self):
        return None


class FakeReport:
    def __init__(self, day, passed, capture_runs=3, gate_version=GATE_VERSION):
        self.report_date = day
        self.passed = passed
        self.metrics = {"capture_runs": capture_runs, "gate_version": gate_version}


class FakeReconRepo:
    def __init__(self, reports=None):
        self.reports = reports or []

    async def reports_between(self, from_date, to_date):
        return [r for r in self.reports if from_date <= r.report_date <= to_date]


def _service(control=None, reports=None):
    control = control if control is not None else FakeControl()
    repo = FakeControlRepo(control)
    return LlmUsageControlService(repo, FakeReconRepo(reports)), repo, control


def _passing_window(capture_runs=3):
    return [FakeReport(day, True, capture_runs) for day in qualifying_days(utc_now().date())]


def test_window_length_constant_is_still_importable_from_this_module():
    from app.services.llm_usage_shadow_window import SHADOW_QUALIFYING_WINDOW_DAYS as shared

    assert SHADOW_QUALIFYING_WINDOW_DAYS is shared
    assert len(_passing_window()) == SHADOW_QUALIFYING_WINDOW_DAYS


@pytest.mark.asyncio
async def test_get_control_reports_daily_stats_when_off():
    service, _, _ = _service()
    read = await service.get_control()
    assert read.capture_enabled is False
    assert read.cost_source == COST_SOURCE_DAILY_STATS


@pytest.mark.asyncio
async def test_control_missing_raises_404():
    service = LlmUsageControlService(MissingControlRepo(), FakeReconRepo())
    with pytest.raises(AppException) as exc:
        await service.get_control()
    assert exc.value.status_code == 404
    assert exc.value.error_key is ErrorKey.LLM_USAGE_CONTROL_NOT_FOUND


@pytest.mark.asyncio
async def test_activate_capture_first_time_stamps_boundary():
    service, repo, _ = _service()
    read = await service.activate_capture()
    assert read.capture_enabled is True
    assert read.capture_started_at is not None
    assert repo.activate_calls == 1


@pytest.mark.asyncio
async def test_activate_capture_is_idempotent_no_restamp():
    control = FakeControl()
    control.capture_enabled = True
    control.capture_started_at = datetime(2025, 6, 1, tzinfo=timezone.utc)
    service, repo, _ = _service(control=control)

    read = await service.activate_capture()

    assert read.capture_enabled is True
    assert read.capture_started_at == datetime(2025, 6, 1, tzinfo=timezone.utc)
    assert repo.activate_calls == 0  # short-circuits, never touches the stamp


@pytest.mark.asyncio
async def test_shadow_start_requires_capture():
    service, _, _ = _service()
    with pytest.raises(AppException) as exc:
        await service.start_shadow()
    assert exc.value.status_code == 409
    assert exc.value.error_key is ErrorKey.LLM_USAGE_CAPTURE_NOT_ENABLED


@pytest.mark.asyncio
async def test_shadow_start_success():
    control = FakeControl()
    control.capture_enabled = True
    service, _, _ = _service(control=control)
    read = await service.start_shadow()
    assert read.shadow_started_at is not None


@pytest.mark.asyncio
async def test_shadow_start_conflicts_when_already_running():
    control = FakeControl()
    control.capture_enabled = True
    control.shadow_started_at = datetime(2026, 1, 2, tzinfo=timezone.utc)
    service, _, _ = _service(control=control)
    with pytest.raises(AppException) as exc:
        await service.start_shadow()
    assert exc.value.status_code == 409
    assert exc.value.error_key is ErrorKey.LLM_USAGE_SHADOW_ALREADY_RUNNING


@pytest.mark.asyncio
async def test_shadow_start_conflicts_when_already_passed():
    control = FakeControl()
    control.capture_enabled = True
    control.shadow_passed_at = datetime(2026, 1, 9, tzinfo=timezone.utc)
    service, _, _ = _service(control=control)
    with pytest.raises(AppException) as exc:
        await service.start_shadow()
    assert exc.value.status_code == 409
    assert exc.value.error_key is ErrorKey.LLM_USAGE_SHADOW_ALREADY_PASSED


@pytest.mark.asyncio
async def test_cutover_disable_always_allowed():
    service, _, control = _service()
    read = await service.set_cutover(False)
    assert read.ledger_cutover_enabled is False
    assert read.cost_source == COST_SOURCE_DAILY_STATS


@pytest.mark.asyncio
async def test_cutover_enable_requires_capture():
    service, _, _ = _service()
    with pytest.raises(AppException) as exc:
        await service.set_cutover(True)
    assert exc.value.status_code == 409
    assert exc.value.error_key is ErrorKey.LLM_USAGE_CAPTURE_NOT_ENABLED


@pytest.mark.asyncio
async def test_cutover_enable_requires_shadow_pass():
    control = FakeControl()
    control.capture_enabled = True
    service, _, _ = _service(control=control)
    with pytest.raises(AppException) as exc:
        await service.set_cutover(True)
    assert exc.value.status_code == 409
    assert exc.value.error_key is ErrorKey.LLM_USAGE_SHADOW_NOT_PASSED


@pytest.mark.asyncio
async def test_cutover_enable_blocked_when_window_incomplete():
    control = FakeControl()
    control.capture_enabled = True
    control.shadow_passed_at = datetime(2026, 1, 9, tzinfo=timezone.utc)
    service, _, _ = _service(control=control, reports=_passing_window()[:3])
    with pytest.raises(AppException) as exc:
        await service.set_cutover(True)
    assert exc.value.status_code == 409
    assert exc.value.error_key is ErrorKey.LLM_USAGE_SHADOW_WINDOW_STALE


@pytest.mark.asyncio
async def test_cutover_enable_blocked_when_a_day_failed():
    control = FakeControl()
    control.capture_enabled = True
    control.shadow_passed_at = datetime(2026, 1, 9, tzinfo=timezone.utc)
    reports = _passing_window()
    reports[2].passed = False
    service, _, _ = _service(control=control, reports=reports)
    with pytest.raises(AppException) as exc:
        await service.set_cutover(True)
    assert exc.value.status_code == 409
    assert exc.value.error_key is ErrorKey.LLM_USAGE_SHADOW_WINDOW_STALE


@pytest.mark.asyncio
async def test_cutover_detail_separates_missing_from_failing_days():
    control = FakeControl()
    control.capture_enabled = True
    control.shadow_passed_at = datetime(2026, 1, 9, tzinfo=timezone.utc)
    reports = _passing_window()
    failed_day = reports[1].report_date
    reports[1].passed = False
    missing_day = reports[4].report_date
    del reports[4]
    service, _, _ = _service(control=control, reports=reports)

    with pytest.raises(AppException) as exc:
        await service.set_cutover(True)
    detail = exc.value.error_detail
    assert f"missing days: ['{missing_day.isoformat()}']" in detail
    assert f"failing days: ['{failed_day.isoformat()}']" in detail


@pytest.mark.asyncio
async def test_cutover_blocked_when_window_has_no_capture_runs():
    control = FakeControl()
    control.capture_enabled = True
    control.shadow_passed_at = datetime(2026, 1, 9, tzinfo=timezone.utc)
    service, _, _ = _service(control=control, reports=_passing_window(capture_runs=0))
    with pytest.raises(AppException) as exc:
        await service.set_cutover(True)
    assert exc.value.status_code == 409
    assert "below minimum" in exc.value.error_detail


@pytest.mark.asyncio
async def test_older_passing_streak_does_not_qualify():
    """A green week from a month ago is history, not current health"""
    from datetime import timedelta

    control = FakeControl()
    control.capture_enabled = True
    control.shadow_passed_at = datetime(2026, 1, 9, tzinfo=timezone.utc)
    stale = [FakeReport(r.report_date - timedelta(days=30), True) for r in _passing_window()]
    service, _, _ = _service(control=control, reports=stale)

    with pytest.raises(AppException) as exc:
        await service.set_cutover(True)
    assert exc.value.error_key is ErrorKey.LLM_USAGE_SHADOW_WINDOW_STALE


@pytest.mark.asyncio
async def test_concurrent_shadow_start_yields_one_409():
    control = FakeControl()
    control.capture_enabled = True
    service, _, _ = _service(control=control)

    first = await service.start_shadow()
    assert first.shadow_started_at is not None
    with pytest.raises(AppException) as exc:
        await service.start_shadow()
    assert exc.value.status_code == 409
    assert exc.value.error_key is ErrorKey.LLM_USAGE_SHADOW_ALREADY_RUNNING


@pytest.mark.asyncio
async def test_shadow_start_409_when_the_claim_is_lost():

    class RacingRepo(FakeControlRepo):
        async def start_shadow(self):
            return False

    control = FakeControl()
    control.capture_enabled = True
    service = LlmUsageControlService(RacingRepo(control), FakeReconRepo())
    with pytest.raises(AppException) as exc:
        await service.start_shadow()
    assert exc.value.status_code == 409
    assert exc.value.error_key is ErrorKey.LLM_USAGE_SHADOW_ALREADY_RUNNING


@pytest.mark.asyncio
async def test_cutover_blocked_when_a_window_day_predates_the_current_gates():
    control = FakeControl()
    control.capture_enabled = True
    control.shadow_passed_at = datetime(2026, 1, 9, tzinfo=timezone.utc)
    reports = _passing_window()
    reports[3].metrics = {"capture_runs": 3, "gate_version": GATE_VERSION - 1}
    service, _, _ = _service(control=control, reports=reports)

    with pytest.raises(AppException) as exc:
        await service.set_cutover(True)
    assert exc.value.status_code == 409
    assert "awaiting re-check" in exc.value.error_detail


@pytest.mark.asyncio
async def test_cutover_never_toggles_capture_or_shadow():
    control = FakeControl()
    control.capture_enabled = True
    control.shadow_passed_at = datetime(2026, 1, 9, tzinfo=timezone.utc)
    control.shadow_started_at = datetime(2026, 1, 2, tzinfo=timezone.utc)
    service, _, _ = _service(control=control, reports=_passing_window())

    await service.set_cutover(True)
    assert control.capture_enabled is True
    assert control.shadow_passed_at == datetime(2026, 1, 9, tzinfo=timezone.utc)
    assert control.shadow_started_at == datetime(2026, 1, 2, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_cutover_enable_success_flips_cost_source():
    control = FakeControl()
    control.capture_enabled = True
    control.shadow_passed_at = datetime(2026, 1, 9, tzinfo=timezone.utc)
    service, _, _ = _service(control=control, reports=_passing_window())
    read = await service.set_cutover(True)
    assert read.ledger_cutover_enabled is True
    assert read.cost_source == COST_SOURCE_LEDGER
