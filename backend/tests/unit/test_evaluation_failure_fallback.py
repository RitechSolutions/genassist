"""A failed run gets its failed status written and its user notified exactly once,
even when the run's own session is unusable."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.exc import InvalidRequestError

from app.services.test_suite import UNEXPECTED_RUN_FAILURE_ERROR, TestSuiteService as EvalService
from app.tasks.test_suite_tasks import _persist_failure

ERROR = "Run failed unexpectedly: boom"
BUSY = InvalidRequestError(
    "This session is provisioning a new connection; concurrent operations are not permitted"
)


def _run(status="running"):
    # A run whose own failed-status write broke keeps its status but carries the error.
    return SimpleNamespace(id=uuid4(), status=status, summary_metrics={"error": ERROR})


def _service(*, busy: bool):
    service = SimpleNamespace(run_repo=SimpleNamespace(db=AsyncMock(), update=AsyncMock()), _fail_run=AsyncMock())
    if busy:
        # What a session still in use by an unfinished coroutine raises.
        service.run_repo.db.rollback.side_effect = BUSY
    return service


def _session_factory(rowcount=1):
    session = AsyncMock()
    session.execute.return_value = SimpleNamespace(rowcount=rowcount)
    factory = MagicMock()
    factory.return_value.__aenter__.return_value = session
    return factory, session


async def _persist(service, run, factory):
    with patch("app.db.multi_tenant_session.multi_tenant_manager") as manager, patch(
        "app.tasks.test_suite_tasks.get_tenant_context", return_value="master"
    ), patch("app.tasks.test_suite_tasks.emit_notification") as emit, patch(
        "app.tasks.test_suite_tasks.injector"
    ):
        manager.get_tenant_session_factory.return_value = factory
        await _persist_failure(service, run, RuntimeError("boom"))
    return manager, emit


def _eval_service() -> EvalService:
    return EvalService(
        suite_repo=AsyncMock(),
        case_repo=AsyncMock(),
        run_repo=AsyncMock(),
        result_repo=AsyncMock(),
        evaluation_repo=AsyncMock(),
        tool_rule_result_repo=AsyncMock(),
        workflow_service=AsyncMock(),
        conversation_repo=AsyncMock(),
    )


@pytest.mark.asyncio
async def test_failure_is_written_on_a_new_session_when_the_run_session_is_busy():
    run = _run()
    factory, session = _session_factory(rowcount=1)

    _, emit = await _persist(_service(busy=True), run, factory)

    lock_timeout, update = (call.args[0] for call in session.execute.await_args_list)
    assert "lock_timeout" in str(lock_timeout)
    assert str(update).startswith("UPDATE test_runs")
    params = update.compile().params
    assert params["status"] == "failed"
    assert params["summary_metrics"] == {"error": ERROR}
    assert run.id in params.values()
    session.commit.assert_awaited_once()
    emit.assert_called_once()


@pytest.mark.asyncio
async def test_a_user_already_notified_is_not_notified_again():
    factory, session = _session_factory(rowcount=1)

    _, emit = await _persist(_service(busy=True), _run(status="failed"), factory)

    session.commit.assert_awaited_once()
    emit.assert_not_called()


@pytest.mark.asyncio
async def test_a_run_that_already_finished_is_left_alone():
    factory, session = _session_factory(rowcount=0)

    _, emit = await _persist(_service(busy=True), _run(), factory)

    session.commit.assert_awaited_once()
    emit.assert_not_called()


@pytest.mark.asyncio
async def test_a_new_session_that_fails_too_is_logged_not_raised():
    factory = MagicMock(side_effect=OSError("database unreachable"))

    _, emit = await _persist(_service(busy=True), _run(), factory)

    emit.assert_not_called()


@pytest.mark.asyncio
async def test_a_working_run_session_needs_no_second_one():
    service = _service(busy=False)
    factory, _ = _session_factory()

    manager, _ = await _persist(service, _run(), factory)

    service._fail_run.assert_awaited_once()
    service.run_repo.db.commit.assert_awaited_once()
    manager.get_tenant_session_factory.assert_not_called()


class TestFailRunThatCannotWrite:
    @pytest.mark.asyncio
    async def test_status_is_restored_and_nobody_is_told_yet(self):
        """A failed status in memory means "written and notified" to _persist_failure."""
        service = _eval_service()
        service.run_repo.update.side_effect = BUSY
        run = SimpleNamespace(id=uuid4(), status="running", summary_metrics=None)

        with patch("app.services.test_suite.emit_notification") as emit, patch(
            "app.services.test_suite.injector"
        ):
            with pytest.raises(InvalidRequestError):
                await service._fail_run(run, "boom")

        assert run.status == "running"
        assert run.summary_metrics == {"error": "boom"}
        emit.assert_not_called()

    @pytest.mark.asyncio
    async def test_the_run_error_still_surfaces(self):
        """The write failure used to replace the error that actually failed the run."""
        service = _eval_service()
        service.run_repo.update.side_effect = BUSY
        service._execute_run_inner = AsyncMock(side_effect=RuntimeError("judge down"))
        run = SimpleNamespace(id=uuid4(), status="running", summary_metrics=None)

        with patch("app.services.test_suite.emit_notification"), patch("app.services.test_suite.injector"):
            with pytest.raises(RuntimeError, match="judge down"):
                await service._execute_run(MagicMock(), MagicMock(), run)

    @pytest.mark.asyncio
    async def test_the_retry_writes_and_notifies_once(self):
        """A database error broke the first write; the task's retry must still tell the user."""
        service = _eval_service()
        service.run_repo.update.side_effect = [BUSY, None]
        service._execute_run_inner = AsyncMock(side_effect=RuntimeError("judge down"))
        run = SimpleNamespace(id=uuid4(), status="running", summary_metrics=None)

        async def refresh(instance):
            instance.status = "running"

        service.run_repo.db = SimpleNamespace(rollback=AsyncMock(), refresh=AsyncMock(side_effect=refresh), commit=AsyncMock())

        with patch("app.services.test_suite.emit_notification") as emit, patch("app.services.test_suite.injector"):
            with pytest.raises(RuntimeError) as raised:
                await service._execute_run(MagicMock(), MagicMock(), run)
            await _persist_failure(service, run, raised.value)

        assert run.status == "failed"
        assert run.summary_metrics == {"error": UNEXPECTED_RUN_FAILURE_ERROR}
        emit.assert_called_once()
        service.run_repo.db.commit.assert_awaited_once()
