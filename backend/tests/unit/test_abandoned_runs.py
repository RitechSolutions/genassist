"""A run whose worker was lost is failed on redelivery, never run a second time."""
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.tasks.base import ABANDONED_RUN_ERROR, was_abandoned_by_worker


class TestAbandonedDetection:
    def test_only_a_running_status_counts_as_abandoned(self):
        assert was_abandoned_by_worker("running") is True
        for status in ("queued", "pending", "completed", "failed", "cancelled"):
            assert was_abandoned_by_worker(status) is False

    def test_enum_statuses_are_understood(self):
        from app.db.models.ml_model_pipeline import PipelineRunStatus

        assert was_abandoned_by_worker(PipelineRunStatus.RUNNING) is True
        assert was_abandoned_by_worker(PipelineRunStatus.PENDING) is False


class TestWorkflowRunAbandoned:
    @pytest.mark.asyncio
    async def test_run_is_failed_committed_and_reported(self):
        from app.core.utils.enums.workflow_schedule_enum import WorkflowScheduleRunStatus
        from app.tasks import workflow_schedule_tasks as module

        repository, session, run_id = AsyncMock(), AsyncMock(), uuid4()
        with patch.object(module, "_notify_run_failed") as notify:
            await module._fail_abandoned_run(repository, session, run_id, "tenant-a")

        repository.update_status.assert_awaited_once_with(
            run_id, WorkflowScheduleRunStatus.FAILED, error_message=ABANDONED_RUN_ERROR
        )
        session.commit.assert_awaited_once()
        notify.assert_called_once_with("tenant-a", run_id)


class TestPipelineRunAbandoned:
    @pytest.mark.asyncio
    async def test_run_is_failed_committed_and_reported(self):
        from app.db.models.ml_model_pipeline import PipelineRunStatus
        from app.tasks import ml_model_pipeline_tasks as module

        repository, session, run_id = AsyncMock(), AsyncMock(), uuid4()
        with patch.object(module, "_notify_run_failed") as notify:
            await module._fail_abandoned_run(repository, session, run_id, "tenant-a")

        repository.update_status.assert_awaited_once_with(
            run_id, PipelineRunStatus.FAILED, error_message=ABANDONED_RUN_ERROR
        )
        session.commit.assert_awaited_once()
        notify.assert_called_once_with("tenant-a", run_id)
