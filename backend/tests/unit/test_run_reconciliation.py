"""Queue-aware reconciliation of orphaned evaluation and scheduled workflow runs."""
import base64
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.config.settings import settings
from app.tasks import run_reconciliation_tasks as reconciliation

EVAL_TASK = reconciliation.EVALUATION_RUN_TASK
WORKFLOW_TASK = reconciliation.WORKFLOW_RUN_TASK


def _message(task_name: str, run_id: str) -> bytes:
    body = json.dumps([[run_id, "acme", None, None], {}, {}]).encode()
    message = {
        "body": base64.b64encode(body).decode(),
        "headers": {"task": task_name, "id": str(uuid4())},
        "properties": {"delivery_info": {"routing_key": "ml"}},
    }
    return json.dumps(message).encode()


class TestMessageParsing:
    def test_reads_run_id_of_matching_task(self):
        run_id = str(uuid4())
        assert reconciliation.run_id_from_message(_message(EVAL_TASK, run_id), EVAL_TASK) == run_id

    def test_reserved_message_wrapper_is_unwrapped(self):
        run_id = str(uuid4())
        wrapped = json.dumps([json.loads(_message(WORKFLOW_TASK, run_id)), "", "ml"]).encode()
        assert reconciliation.run_id_from_message(wrapped, WORKFLOW_TASK) == run_id

    def test_other_tasks_and_garbage_are_ignored(self):
        assert reconciliation.run_id_from_message(_message("other_task", str(uuid4())), EVAL_TASK) is None
        assert reconciliation.run_id_from_message(b"not json", EVAL_TASK) is None

    @pytest.mark.asyncio
    async def test_run_ids_in_broker_collects_waiting_and_reserved_jobs(self):
        first, second = str(uuid4()), str(uuid4())
        messages = [
            _message(EVAL_TASK, first),
            _message(EVAL_TASK, second),
            _message("other_task", str(uuid4())),
        ]
        with patch.object(reconciliation, "_read_broker_messages", return_value=messages):
            assert await reconciliation.run_ids_in_broker(EVAL_TASK) == {first, second}


class TestBrokerScanFailSafe:
    def _channel(self, waiting, reserved, length):
        client = MagicMock()
        client.lrange.return_value = waiting
        client.hvals.return_value = reserved
        client.llen.return_value = length
        channel = MagicMock(client=client, global_keyprefix="{celery}", unacked_key="unacked")
        connection = MagicMock()
        connection.__enter__ = MagicMock(return_value=MagicMock(default_channel=channel))
        connection.__exit__ = MagicMock(return_value=False)
        return connection

    def test_an_unreadable_non_empty_queue_raises_instead_of_reporting_empty(self):
        with patch.object(reconciliation, "current_app") as app:
            app.connection_for_read.return_value = self._channel([], [], 3)
            with pytest.raises(reconciliation.BrokerScanError):
                reconciliation._read_broker_messages("ml")

    def test_a_truly_empty_queue_is_fine(self):
        with patch.object(reconciliation, "current_app") as app:
            app.connection_for_read.return_value = self._channel([], [], 0)
            assert reconciliation._read_broker_messages("ml") == []

    @pytest.mark.asyncio
    async def test_scan_failure_leaves_waiting_runs_alone(self):
        candidates = [str(uuid4()), str(uuid4())]
        with patch.object(
            reconciliation, "run_ids_in_broker", AsyncMock(side_effect=reconciliation.BrokerScanError("x"))
        ):
            assert await reconciliation.orphaned_waiting_runs(candidates, EVAL_TASK) == []


def _session_factory(session):
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=session)
    context.__aexit__ = AsyncMock(return_value=False)
    return MagicMock(return_value=context)


def _repository(waiting_ids):
    repository = MagicMock()
    repository.get_waiting_ids_older_than = AsyncMock(return_value=waiting_ids)
    repository.mark_orphaned_as_failed = AsyncMock(return_value=len(waiting_ids))
    return repository


def _patched(repository, repository_name, present_ids):
    session = AsyncMock()
    return session, (
        patch.object(
            reconciliation.multi_tenant_manager,
            "get_tenant_session_factory",
            return_value=_session_factory(session),
        ),
        patch.object(reconciliation, repository_name, return_value=repository),
        patch.object(reconciliation, "get_tenant_context", return_value="tenant_a"),
        patch.object(reconciliation, "run_ids_in_broker", AsyncMock(return_value=present_ids)),
    )


class TestQueueAwareReconciler:
    @pytest.mark.asyncio
    async def test_waiting_runs_still_in_the_queue_are_not_failed(self):
        """Run all: healthy runs waiting behind others keep their queued status."""
        waiting = [str(uuid4()) for _ in range(3)]
        repository = _repository(waiting)
        session, patches = _patched(repository, "TestRunRepository", set(waiting))

        with patches[0], patches[1], patches[2], patches[3]:
            await reconciliation.reconcile_stuck_test_runs_async()

        kwargs = repository.mark_orphaned_as_failed.await_args.kwargs
        assert kwargs["waiting_ids"] == []
        assert kwargs["running_before"] < datetime.now(timezone.utc)
        assert kwargs["error_message"]
        session.commit.assert_awaited_once()

        waiting_before = repository.get_waiting_ids_older_than.await_args.args[0]
        waited_seconds = (datetime.now(timezone.utc) - waiting_before).total_seconds()
        assert abs(waited_seconds - settings.TEST_RUN_QUEUED_MAX_AGE_SECONDS) < 5

    @pytest.mark.asyncio
    async def test_waiting_run_whose_job_left_the_queue_is_failed(self):
        lost, present = str(uuid4()), str(uuid4())
        repository = _repository([lost, present])
        _, patches = _patched(repository, "TestRunRepository", {present})

        with patches[0], patches[1], patches[2], patches[3]:
            await reconciliation.reconcile_stuck_test_runs_async()

        assert repository.mark_orphaned_as_failed.await_args.kwargs["waiting_ids"] == [lost]

    @pytest.mark.asyncio
    async def test_broker_is_not_read_when_nothing_is_waiting(self):
        repository = _repository([])
        _, patches = _patched(repository, "TestRunRepository", set())

        with patches[0], patches[1], patches[2], patches[3] as broker:
            await reconciliation.reconcile_stuck_test_runs_async()

        broker.assert_not_awaited()
        repository.mark_orphaned_as_failed.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_workflow_reconciler_looks_for_its_own_task(self):
        pending = [str(uuid4())]
        repository = _repository(pending)
        _, patches = _patched(repository, "WorkflowScheduleRunRepository", set())

        with patches[0], patches[1], patches[2], patches[3] as broker:
            await reconciliation.reconcile_stuck_workflow_runs_async()

        broker.assert_awaited_once_with(WORKFLOW_TASK)
        assert repository.mark_orphaned_as_failed.await_args.kwargs["waiting_ids"] == pending

    @pytest.mark.asyncio
    async def test_errors_roll_back_and_do_not_raise(self):
        repository = _repository([str(uuid4())])
        repository.mark_orphaned_as_failed = AsyncMock(side_effect=RuntimeError("db down"))
        session, patches = _patched(repository, "TestRunRepository", set())

        with patches[0], patches[1], patches[2], patches[3]:
            await reconciliation.reconcile_stuck_test_runs_async()

        session.rollback.assert_awaited_once()
        session.commit.assert_not_awaited()
