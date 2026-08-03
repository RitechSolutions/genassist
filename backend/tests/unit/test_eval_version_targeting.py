"""Unit tests for version-targeted evaluation runs: the same-workflow guard and
how a run resolves which workflow version to execute."""
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.exceptions.exception_classes import AppException
from app.schemas.test_suite import TestRunInDB
from app.services.test_suite import TestSuiteService as EvalService


def _service() -> EvalService:
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


def _eval(*, suite_id=None, workflow_id=None, technique_configs=None):
    return SimpleNamespace(
        id=uuid4(),
        workflow_id=workflow_id,
        suite_id=suite_id or uuid4(),
        input_metadata=None,
        techniques=["no_errors"],
        technique_configs=technique_configs,
    )


def _workflow(*, workflow_id=None, agent_id=None):
    return SimpleNamespace(id=workflow_id or uuid4(), agent_id=agent_id)


class TestSameWorkflowGuard:
    @pytest.mark.asyncio
    async def test_same_id_passes_without_lookups(self):
        service = _service()
        workflow_id = uuid4()

        await service._ensure_version_of_same_workflow(workflow_id, workflow_id)

        service.workflow_service.get_by_id.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_same_agent_passes(self):
        service = _service()
        agent_id = uuid4()
        base, target = uuid4(), uuid4()
        service.workflow_service.get_by_id = AsyncMock(
            side_effect=[
                _workflow(workflow_id=base, agent_id=agent_id),
                _workflow(workflow_id=target, agent_id=agent_id),
            ]
        )

        await service._ensure_version_of_same_workflow(base, target)

    @pytest.mark.asyncio
    async def test_different_agent_is_rejected(self):
        service = _service()
        base, target = uuid4(), uuid4()
        service.workflow_service.get_by_id = AsyncMock(
            side_effect=[
                _workflow(workflow_id=base, agent_id=uuid4()),
                _workflow(workflow_id=target, agent_id=uuid4()),
            ]
        )

        with pytest.raises(AppException) as excinfo:
            await service._ensure_version_of_same_workflow(base, target)
        assert excinfo.value.status_code == 400

    @pytest.mark.asyncio
    async def test_missing_agent_is_rejected(self):
        """Workflows without an agent cannot be proven related — refuse."""
        service = _service()
        base, target = uuid4(), uuid4()
        service.workflow_service.get_by_id = AsyncMock(
            side_effect=[
                _workflow(workflow_id=base, agent_id=None),
                _workflow(workflow_id=target, agent_id=None),
            ]
        )

        with pytest.raises(AppException):
            await service._ensure_version_of_same_workflow(base, target)

    @pytest.mark.asyncio
    async def test_no_base_workflow_is_rejected(self):
        service = _service()

        with pytest.raises(AppException) as excinfo:
            await service._ensure_version_of_same_workflow(None, uuid4())
        assert excinfo.value.status_code == 400


class TestVersionTargetedRuns:
    def _run_in_db(self, *, suite_id, workflow_id):
        from datetime import datetime

        return TestRunInDB(
            id=uuid4(),
            suite_id=suite_id,
            workflow_id=workflow_id,
            status="queued",
            techniques=["no_errors"],
            summary_metrics=None,
            created_at=datetime(2026, 1, 1),
            updated_at=datetime(2026, 1, 1),
        )

    @pytest.mark.asyncio
    async def test_single_run_uses_target_version(self):
        service = _service()
        target = uuid4()
        ev = _eval(workflow_id=uuid4())
        service.evaluation_repo.get_by_id = AsyncMock(return_value=ev)
        service._ensure_version_of_same_workflow = AsyncMock()
        service.create_run = AsyncMock(
            return_value=self._run_in_db(suite_id=ev.suite_id, workflow_id=target)
        )
        service.append_run_to_evaluation = AsyncMock()

        await service.start_evaluation_run(ev.id, lambda *args: None, target)

        data = service.create_run.await_args.args[1]
        assert data.workflow_id == target
        service._ensure_version_of_same_workflow.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_single_run_defaults_to_the_active_version(self):
        """No explicit target runs what is live, not the pinned version."""
        service = _service()
        active = uuid4()
        ev = _eval(workflow_id=uuid4())
        service.evaluation_repo.get_by_id = AsyncMock(return_value=ev)
        service._ensure_version_of_same_workflow = AsyncMock()
        service.workflow_service.get_active_version_id = AsyncMock(return_value=active)
        service.create_run = AsyncMock(
            return_value=self._run_in_db(suite_id=ev.suite_id, workflow_id=active)
        )
        service.append_run_to_evaluation = AsyncMock()

        await service.start_evaluation_run(ev.id, lambda *args: None)

        data = service.create_run.await_args.args[1]
        assert data.workflow_id == active
        service._ensure_version_of_same_workflow.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_single_run_falls_back_to_pinned_without_an_active_version(self):
        service = _service()
        ev = _eval(workflow_id=uuid4())
        service.evaluation_repo.get_by_id = AsyncMock(return_value=ev)
        service.workflow_service.get_active_version_id = AsyncMock(return_value=None)
        service.create_run = AsyncMock(
            return_value=self._run_in_db(suite_id=ev.suite_id, workflow_id=ev.workflow_id)
        )
        service.append_run_to_evaluation = AsyncMock()

        await service.start_evaluation_run(ev.id, lambda *args: None)

        data = service.create_run.await_args.args[1]
        assert data.workflow_id == ev.workflow_id

    @pytest.mark.asyncio
    async def test_explicit_target_wins_over_the_active_version(self):
        service = _service()
        target = uuid4()
        ev = _eval(workflow_id=uuid4())
        service.evaluation_repo.get_by_id = AsyncMock(return_value=ev)
        service._ensure_version_of_same_workflow = AsyncMock()
        service.workflow_service.get_active_version_id = AsyncMock(return_value=uuid4())
        service.create_run = AsyncMock(
            return_value=self._run_in_db(suite_id=ev.suite_id, workflow_id=target)
        )
        service.append_run_to_evaluation = AsyncMock()

        await service.start_evaluation_run(ev.id, lambda *args: None, target)

        data = service.create_run.await_args.args[1]
        assert data.workflow_id == target
        service.workflow_service.get_active_version_id.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_default_uses_the_dataset_workflow_when_evaluation_has_none(self):
        """An evaluation with no workflow resolves through its dataset, then to active."""
        service = _service()
        suite_workflow, active = uuid4(), uuid4()
        ev = _eval(workflow_id=None)
        service.suite_repo.get_by_id = AsyncMock(
            return_value=SimpleNamespace(id=ev.suite_id, workflow_id=suite_workflow)
        )
        service.workflow_service.get_active_version_id = AsyncMock(return_value=active)

        resolved = await service._default_run_workflow_id(ev)

        assert resolved == active
        service.workflow_service.get_active_version_id.assert_awaited_once_with(
            suite_workflow
        )

    @pytest.mark.asyncio
    async def test_run_all_resolves_the_active_version_once_for_the_batch(self):
        """Every evaluation in the scope shares the workflow, so the lookup must
        not repeat per evaluation."""
        service = _service()
        workflow_id, active = uuid4(), uuid4()
        rows = [_eval(workflow_id=workflow_id) for _ in range(4)]
        service.evaluation_repo.get_all_for_workflow = AsyncMock(return_value=rows)
        service.workflow_service.get_active_version_id = AsyncMock(return_value=active)
        service._start_evaluation_run = AsyncMock(
            return_value=self._run_in_db(suite_id=rows[0].suite_id, workflow_id=active)
        )

        await service.start_workflow_evaluations(workflow_id, lambda *args: None)

        service.workflow_service.get_active_version_id.assert_awaited_once_with(
            workflow_id
        )
        for call in service._start_evaluation_run.await_args_list:
            assert call.args[2] == active

    @pytest.mark.asyncio
    async def test_run_all_skips_the_lookup_when_no_evaluations_match(self):
        service = _service()
        service.evaluation_repo.get_all_for_workflow = AsyncMock(return_value=[])
        service.workflow_service.get_active_version_id = AsyncMock()

        results = await service.start_workflow_evaluations(uuid4(), lambda *args: None)

        assert results == []
        service.workflow_service.get_active_version_id.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_run_all_passes_target_to_every_evaluation(self):
        service = _service()
        workflow_id, target = uuid4(), uuid4()
        rows = [_eval(workflow_id=workflow_id) for _ in range(2)]
        service.evaluation_repo.get_all_for_workflow = AsyncMock(return_value=rows)
        service._ensure_version_of_same_workflow = AsyncMock()
        service._start_evaluation_run = AsyncMock(
            return_value=self._run_in_db(suite_id=rows[0].suite_id, workflow_id=target)
        )

        dispatch = lambda *args: None  # noqa: E731
        await service.start_workflow_evaluations(workflow_id, dispatch, target)

        service._ensure_version_of_same_workflow.assert_awaited_once_with(
            workflow_id, target
        )
        for call in service._start_evaluation_run.await_args_list:
            assert call.args[2] == target
