"""Unit tests for the workflow-batch evaluation runner: grouping, isolation, cleanup."""
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.services.test_suite import TestSuiteService as EvalService


def _service() -> EvalService:
    return EvalService(
        suite_repo=AsyncMock(),
        case_repo=AsyncMock(),
        run_repo=AsyncMock(),
        result_repo=AsyncMock(),
        evaluation_repo=AsyncMock(),
        workflow_service=AsyncMock(),
        conversation_repo=AsyncMock(),
    )


def _eval(*, suite_id, workflow_id=None, eval_id=None):
    return SimpleNamespace(
        id=eval_id or uuid4(),
        workflow_id=workflow_id,
        suite_id=suite_id,
        input_metadata=None,
        techniques=["no_errors"],
        technique_configs=None,
    )


def _full_eval(*, suite_id, workflow_id=None):
    """A fake that satisfies TestEvaluationInDB.model_validate for list responses."""
    now = datetime(2026, 1, 1)
    return SimpleNamespace(
        id=uuid4(),
        name="eval",
        description=None,
        suite_id=suite_id,
        workflow_id=workflow_id,
        techniques=[],
        technique_configs=None,
        input_metadata=None,
        run_ids=[],
        created_at=now,
        updated_at=now,
    )


class TestEvaluationsForWorkflow:
    @pytest.mark.asyncio
    async def test_run_all_uses_full_db_scope(self):
        """Run all delegates to the DB-filtered full scope (single source of truth).
        The effective-workflow rule itself is exercised by the DB integration test."""
        wf = uuid4()
        rows = [_eval(suite_id=uuid4(), workflow_id=wf) for _ in range(3)]
        service = _service()
        service.evaluation_repo.get_all_for_workflow = AsyncMock(return_value=rows)

        result = await service._evaluations_for_workflow(wf)

        assert result == rows
        service.evaluation_repo.get_all_for_workflow.assert_awaited_once_with(wf)


class TestStartWorkflowEvaluations:
    @pytest.mark.asyncio
    async def test_one_failure_does_not_abort_the_rest(self):
        suite = uuid4()
        evals = [_eval(suite_id=suite, workflow_id=uuid4()) for _ in range(3)]
        service = _service()
        service._evaluations_for_workflow = AsyncMock(return_value=evals)

        async def fake_start(ev, dispatch):
            if ev is evals[1]:
                raise RuntimeError("boom - secret internals")
            return SimpleNamespace(id=uuid4(), suite_id=ev.suite_id, status="queued")

        service._start_evaluation_run = fake_start

        results = await service.start_workflow_evaluations(uuid4(), MagicMock())

        assert len(results) == 3
        failed = [r for r in results if r.status == "failed_to_start"]
        started = [r for r in results if r.run_id is not None]
        assert len(started) == 2
        assert len(failed) == 1 and failed[0].evaluation_id == evals[1].id
        # raw exception text must never reach the client
        assert failed[0].error == "Failed to start evaluation."
        assert "boom" not in (failed[0].error or "")


class TestStartEvaluationRunOrphanCleanup:
    @pytest.mark.asyncio
    async def test_dispatch_failure_marks_run_failed_not_queued(self):
        suite = uuid4()
        ev = _eval(suite_id=suite, workflow_id=uuid4())
        service = _service()

        run = SimpleNamespace(id=uuid4(), suite_id=suite, status="queued")
        service.create_run = AsyncMock(return_value=run)
        service.append_run_to_evaluation = AsyncMock()

        # the persisted row the cleanup path fetches and flips
        row = SimpleNamespace(id=run.id, status="queued", summary_metrics=None)
        service.run_repo.get_by_id = AsyncMock(return_value=row)
        service.run_repo.update = AsyncMock()

        def dispatch(_run, _meta, _configs):
            raise RuntimeError("broker down")

        with pytest.raises(RuntimeError):
            await service._start_evaluation_run(ev, dispatch)

        assert row.status == "failed"  # not left dangling in "queued"
        assert row.summary_metrics == {"error": "Failed to dispatch run"}
        service.run_repo.update.assert_awaited_once()


class TestWorkflowEvaluationSummaries:
    @pytest.mark.asyncio
    async def test_maps_repo_rows_to_summaries(self):
        """Service maps the DB group-by rows to summaries, incl. the unassigned bucket.
        The group-by SQL itself is exercised by the DB integration test / smoke."""
        wf_a, wf_b = uuid4(), uuid4()
        service = _service()
        service.evaluation_repo.count_by_effective_workflow = AsyncMock(
            return_value=[(wf_a, 2), (wf_b, 1), (None, 3)]
        )
        service.evaluation_repo.get_latest_run_pointers = AsyncMock(return_value=[])
        service.run_repo.get_by_ids = AsyncMock(return_value=[])

        summaries = await service.get_workflow_evaluation_summaries()
        by_key = {
            (str(s.workflow_id) if s.workflow_id else None): s for s in summaries
        }
        assert by_key[str(wf_a)].eval_count == 2
        assert by_key[str(wf_b)].eval_count == 1
        assert by_key[None].eval_count == 3  # unassigned bucket preserved
        # No runs anywhere → health is unknown, not 0, and nothing is running.
        assert all(
            s.health is None and s.finished_count == 0 and s.any_running is False
            for s in summaries
        )

    @pytest.mark.asyncio
    async def test_health_counts_failed_runs_as_zero(self):
        """Health is the mean per-eval accuracy over evaluations whose latest run
        has finished, counting a failed run as 0. Never-run evals are excluded."""
        wf = uuid4()
        service = _service()
        service.evaluation_repo.count_by_effective_workflow = AsyncMock(
            return_value=[(wf, 4)]
        )
        # Four evaluations: two completed, one failed, one never run.
        service.evaluation_repo.get_latest_run_pointers = AsyncMock(
            return_value=[
                (wf, ["r1"]),
                (wf, ["r2"]),
                (wf, ["r3"]),
                (wf, []),
            ]
        )
        service.run_repo.get_by_ids = AsyncMock(
            return_value=[
                SimpleNamespace(
                    id="r1",
                    status="completed",
                    summary_metrics={"a": {"accuracy": 1.0}, "b": {"accuracy": 0.5}},
                ),
                SimpleNamespace(
                    id="r2",
                    status="completed",
                    summary_metrics={"a": {"accuracy": 0.5}},
                ),
                SimpleNamespace(
                    id="r3", status="failed", summary_metrics={"error": "boom"}
                ),
            ]
        )

        summaries = await service.get_workflow_evaluation_summaries()
        summary = next(s for s in summaries if s.workflow_id == wf)
        assert summary.eval_count == 4
        assert summary.finished_count == 3  # two completed + one failed
        assert summary.any_running is False
        # eval accuracies: 0.75, 0.5, failed→0.0 → mean (0.75+0.5+0.0)/3
        assert summary.health == pytest.approx((0.75 + 0.5 + 0.0) / 3)

        service.run_repo.get_by_ids.assert_awaited_once()
        requested_ids = set(service.run_repo.get_by_ids.await_args.args[0])
        assert requested_ids == {"r1", "r2", "r3"}  # empty pointer excluded

    @pytest.mark.asyncio
    async def test_running_run_sets_any_running_and_is_not_scored(self):
        """A queued/running latest run flags any_running and does not affect health."""
        wf = uuid4()
        service = _service()
        service.evaluation_repo.count_by_effective_workflow = AsyncMock(
            return_value=[(wf, 2)]
        )
        service.evaluation_repo.get_latest_run_pointers = AsyncMock(
            return_value=[(wf, ["r1"]), (wf, ["r2"])]
        )
        service.run_repo.get_by_ids = AsyncMock(
            return_value=[
                SimpleNamespace(
                    id="r1",
                    status="completed",
                    summary_metrics={"a": {"accuracy": 1.0}},
                ),
                SimpleNamespace(id="r2", status="running", summary_metrics=None),
            ]
        )

        summaries = await service.get_workflow_evaluation_summaries()
        summary = next(s for s in summaries if s.workflow_id == wf)
        assert summary.any_running is True
        assert summary.finished_count == 1  # running run not counted
        assert summary.health == pytest.approx(1.0)


class TestWorkflowHasActiveRun:
    @pytest.mark.asyncio
    async def test_true_when_a_latest_run_is_active(self):
        wf = uuid4()
        service = _service()
        service.evaluation_repo.get_run_pointers_for_workflow = AsyncMock(
            return_value=[["r1"], ["r2"], []]
        )
        service.run_repo.get_by_ids = AsyncMock(
            return_value=[
                SimpleNamespace(id="r1", status="completed"),
                SimpleNamespace(id="r2", status="queued"),
            ]
        )
        assert await service.workflow_has_active_run(wf) is True
        # Only latest-run ids are checked; the empty pointer is skipped.
        assert set(service.run_repo.get_by_ids.await_args.args[0]) == {"r1", "r2"}

    @pytest.mark.asyncio
    async def test_false_when_no_active_run(self):
        wf = uuid4()
        service = _service()
        service.evaluation_repo.get_run_pointers_for_workflow = AsyncMock(
            return_value=[["r1"]]
        )
        service.run_repo.get_by_ids = AsyncMock(
            return_value=[SimpleNamespace(id="r1", status="completed")]
        )
        assert await service.workflow_has_active_run(wf) is False

    @pytest.mark.asyncio
    async def test_false_when_no_runs_at_all(self):
        service = _service()
        service.evaluation_repo.get_run_pointers_for_workflow = AsyncMock(
            return_value=[[], []]
        )
        service.run_repo.get_by_ids = AsyncMock(return_value=[])
        assert await service.workflow_has_active_run(uuid4()) is False
        service.run_repo.get_by_ids.assert_not_awaited()


class TestListWorkflowEvaluations:
    """Service-level: clamping, offset math, and search passthrough. The SQL
    filtering/pagination/search itself is exercised against a real DB (smoke)."""

    def _service_with_repo(self, page_rows, total):
        service = _service()
        service.evaluation_repo.get_page_for_workflow = AsyncMock(return_value=page_rows)
        service.evaluation_repo.count_for_workflow = AsyncMock(return_value=total)
        return service

    @pytest.mark.asyncio
    async def test_clamps_page_and_page_size(self):
        wf = uuid4()
        service = self._service_with_repo([], 0)

        result = await service.list_workflow_evaluations(wf, page=0, page_size=999)

        assert result.page == 1 and result.page_size == 100  # floor + cap
        service.evaluation_repo.get_page_for_workflow.assert_awaited_once_with(
            wf, 0, 100, None
        )

    @pytest.mark.asyncio
    async def test_offset_and_search_are_forwarded(self):
        wf = uuid4()
        rows = [_full_eval(suite_id=uuid4(), workflow_id=wf) for _ in range(20)]
        service = self._service_with_repo(rows, 55)

        result = await service.list_workflow_evaluations(
            wf, page=2, page_size=20, search="alpha"
        )

        assert result.total == 55 and result.page == 2 and len(result.items) == 20
        assert result.total_unfiltered == 55
        # page 2 of 20 -> offset 20, limit 20, search forwarded to the DB layer
        service.evaluation_repo.get_page_for_workflow.assert_awaited_once_with(
            wf, 20, 20, "alpha"
        )
        # Filtered count for the page, plus the unfiltered count for "N of M".
        assert service.evaluation_repo.count_for_workflow.await_count == 2
        service.evaluation_repo.count_for_workflow.assert_any_await(wf, "alpha")
        service.evaluation_repo.count_for_workflow.assert_any_await(wf, None)

    @pytest.mark.asyncio
    async def test_unassigned_is_forwarded(self):
        service = self._service_with_repo([], 0)

        await service.list_workflow_evaluations(None, page=1, page_size=20)

        service.evaluation_repo.get_page_for_workflow.assert_awaited_once_with(
            None, 0, 20, None
        )
