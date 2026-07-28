"""Unit tests for LlmUsageControlService capture activation"""

from datetime import datetime, timezone

import pytest

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.db.models.llm_usage import LlmUsageControlModel
from app.services.llm_usage_control import LlmUsageControlService


class FakeControl:
    def __init__(self):
        self.capture_enabled = False
        self.capture_started_at = None


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


class MissingControlRepo:
    async def get_singleton(self):
        return None


def _service(control=None):
    control = control if control is not None else FakeControl()
    repo = FakeControlRepo(control)
    return LlmUsageControlService(repo), repo, control


@pytest.mark.asyncio
async def test_get_control_reads_capture_state_when_off():
    service, _, _ = _service()
    read = await service.get_control()
    assert read.capture_enabled is False


@pytest.mark.asyncio
async def test_control_missing_raises_404():
    service = LlmUsageControlService(MissingControlRepo())
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
async def test_activate_capture_repairs_enabled_row_with_no_stamp():
    control = FakeControl()
    control.capture_enabled = True
    service, repo, _ = _service(control=control)

    read = await service.activate_capture()

    assert read.capture_started_at is not None
    assert repo.activate_calls == 1


class TestCaptureShipsOn:

    columns = LlmUsageControlModel.__table__.c

    def test_capture_enabled_defaults_to_true(self):
        assert self.columns.capture_enabled.default.arg is True
        assert "true" in str(self.columns.capture_enabled.server_default.arg).lower()

    def test_capture_started_at_is_stamped_on_insert(self):
        assert self.columns.capture_started_at.server_default is not None
