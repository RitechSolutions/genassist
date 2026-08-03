"""Unit tests for evaluation run reliability: terminal state, watchdog, timeouts."""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
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
        tool_rule_result_repo=AsyncMock(),
        workflow_service=AsyncMock(),
        conversation_repo=AsyncMock(),
    )


def _run(status="running"):
    return SimpleNamespace(id=uuid4(), status=status, summary_metrics=None)


class TestTerminalState:
    @pytest.mark.asyncio
    async def test_fail_run_marks_failed_and_notifies(self):
        service = _service()
        run = _run()
        with patch("app.services.test_suite.emit_notification") as emit, patch(
            "app.services.test_suite.injector"
        ):
            await service._fail_run(run, "boom")

        assert run.status == "failed"
        assert run.summary_metrics == {"error": "boom"}
        service.run_repo.update.assert_awaited_once_with(run)
        emit.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_run_marks_failed_on_unhandled_error(self):
        service = _service()
        run = _run()
        service._execute_run_inner = AsyncMock(side_effect=RuntimeError("kaboom"))
        with patch("app.services.test_suite.emit_notification"), patch(
            "app.services.test_suite.injector"
        ):
            with pytest.raises(RuntimeError):
                await service._execute_run(MagicMock(), MagicMock(), run)

        assert run.status == "failed"
        assert "kaboom" in run.summary_metrics["error"]

    @pytest.mark.asyncio
    async def test_execute_run_does_not_overwrite_terminal_status(self):
        """A run the inner body already completed is not reset to failed."""
        service = _service()
        run = _run(status="completed")

        async def _inner(*_args, **_kwargs):
            raise RuntimeError("after completion")

        service._execute_run_inner = _inner
        service._fail_run = AsyncMock()
        with pytest.raises(RuntimeError):
            await service._execute_run(MagicMock(), MagicMock(), run)

        service._fail_run.assert_not_awaited()
        assert run.status == "completed"

    @pytest.mark.asyncio
    async def test_execute_run_inner_fails_when_no_cases(self):
        service = _service()
        run = _run()
        service.list_cases_for_suite = AsyncMock(return_value=[])
        suite = SimpleNamespace(id=uuid4())
        with patch("app.services.test_suite.emit_notification"), patch(
            "app.services.test_suite.injector"
        ):
            await service._execute_run_inner(suite, MagicMock(), run)

        assert run.status == "failed"
        assert run.summary_metrics == {"error": "No test cases in suite"}


class TestPausedToolEvent:
    @pytest.mark.asyncio
    async def test_paused_tool_records_paused_event_and_reraises(self):
        from app.modules.workflow.agents.base_tool import BaseTool
        from app.modules.workflow.engine.workflow_state import (
            WorkflowPausedException,
        )

        state = MagicMock()
        recorded = {}

        def _capture(**kwargs):
            recorded.update(kwargs)

        state.add_tool_event = _capture

        def _pause(_payload):
            raise WorkflowPausedException({"reason": "needs human"})

        tool = BaseTool(
            node_id="n1",
            name="escalate",
            description="",
            parameters={},
            function=_pause,
            agent_id="a1",
            state=state,
        )

        with pytest.raises(WorkflowPausedException):
            await tool.invoke(foo="bar")

        assert recorded["status"] == "paused"
        assert recorded["tool_id"] == "n1"
        assert recorded["error"] is None


class TestToolResultRecording:
    @pytest.mark.asyncio
    async def test_recorded_tool_result_feeds_result_checks_and_retrievals(self):
        """End-to-end over the real recording chain: a tool invoked through
        BaseTool on a real WorkflowState must surface its result to the
        result-content checks and the retrieved-context collector."""
        from app.modules.workflow.agents.base_tool import BaseTool
        from app.modules.workflow.engine.workflow_state import WorkflowState
        from app.services.test_suite import SimpleEvaluatorRegistry, _build_grading_context

        workflow = {
            "id": "wf1",
            "nodes": [
                {"id": "agent1", "type": "agentNode", "data": {"name": "HR Agent"}},
                {"id": "kb1", "type": "knowledgeToolNode", "data": {"name": "Search Handbook"}},
            ],
            "edges": [{"source": "kb1", "target": "agent1", "targetHandle": "tools"}],
        }
        state = WorkflowState(workflow=workflow)
        handbook_text = "Employees receive 25 vacation days per year."

        # The tool's function is the node's execute, which tracks node status
        # around the actual work — mirrored here without a full engine run.
        async def _node_execute(_payload):
            state.start_node_execution("kb1")
            state.complete_node_execution("kb1", output=handbook_text)
            return handbook_text

        tool = BaseTool(
            node_id="kb1",
            name="search_handbook",
            description="",
            parameters={},
            function=_node_execute,
            agent_id="agent1",
            state=state,
        )
        # The agent node executes as a workflow step and calls the tool mid-run.
        state.start_node_execution("agent1")
        result = await tool.invoke(topic="vacation days")
        state.complete_node_execution("agent1", output={"message": "answered"})
        assert result == handbook_text

        trace = state.format_state_as_response()
        events = trace.get("tool_events") or []
        assert events and events[0]["result"] == handbook_text

        context = _build_grading_context(trace)
        assert any(
            handbook_text in str(retrieval.get("results")) for retrieval in context["retrievals"]
        )

        registry = SimpleEvaluatorRegistry()
        metrics = await registry.evaluate(
            ["tool_used"],
            inputs={"message": "How many vacation days do I get?"},
            outputs="You get 25 vacation days per year.",
            reference_outputs=None,
            execution_trace=trace,
            technique_configs={
                "tool_used": {"tool": "search_handbook", "result_contains": "25 vacation days"}
            },
            workflow=workflow,
        )
        assert metrics["tool_used"]["passed"] is True

        failing = await registry.evaluate(
            ["tool_used"],
            inputs={},
            outputs="",
            reference_outputs=None,
            execution_trace=trace,
            technique_configs={
                "tool_used": {"tool": "search_handbook", "result_contains": "unlimited holidays"}
            },
            workflow=workflow,
        )
        assert failing["tool_used"]["passed"] is False


class TestMetricResultContract:
    def test_accepts_not_evaluated_without_a_score(self):
        from app.schemas.test_suite import TestResultMetrics

        metric = TestResultMetrics.model_validate(
            {
                "score": None,
                "passed": False,
                "not_evaluated": True,
                "comment": "No grounding source was available.",
            }
        )

        assert metric.score is None
        assert metric.not_evaluated is True
        assert metric.error is False

    def test_accepts_evaluator_error_without_a_score(self):
        from app.schemas.test_suite import TestResultMetrics

        metric = TestResultMetrics.model_validate(
            {
                "score": None,
                "passed": False,
                "error": True,
                "comment": "Evaluator failed to run.",
            }
        )

        assert metric.score is None
        assert metric.error is True
        assert metric.not_evaluated is False


class TestCoverageAggregation:
    async def _summary(self, metric_by_case):
        """Run N single, independent cases whose evaluator returns the given
        metric dicts, and return the run's summary_metrics."""
        service = _service()
        now = datetime(2026, 1, 1)
        cases = [
            SimpleNamespace(
                id=uuid4(),
                suite_id=uuid4(),
                source_conversation_id=None,
                turn_index=None,
                input_data={"message": "hi"},
                expected_output={"value": "ok"},
                tags=["imported"],
                weight=None,
                created_at=now,
                updated_at=now,
            )
            for _ in metric_by_case
        ]
        service.case_repo.get_all_for_suite.return_value = cases
        service.evaluators = MagicMock()
        service.evaluators.default_techniques = MagicMock(return_value=["exact_match"])
        service.evaluators.evaluate = AsyncMock(side_effect=list(metric_by_case))

        suite = SimpleNamespace(id=uuid4(), default_input_metadata=None)
        workflow = SimpleNamespace(id=uuid4(), nodes=[], edges=[])
        run = SimpleNamespace(
            id=uuid4(), techniques=["exact_match"], status="queued", summary_metrics=None
        )
        engine = MagicMock()
        engine.execute_from_node = AsyncMock(
            return_value=SimpleNamespace(
                output="out", status="ok", format_state_as_response=lambda: {}
            )
        )
        with patch("app.services.test_suite.WorkflowEngine", return_value=engine):
            await service._execute_run(suite, workflow, run)
        return run.summary_metrics

    @pytest.mark.asyncio
    async def test_evaluator_error_excluded_from_pass_fail(self):
        summary = await self._summary([
            {"exact_match": {"key": "exact_match", "passed": True, "score": True}},
            {"exact_match": {"key": "exact_match", "passed": False, "error": True, "score": None}},
        ])
        metric = summary["exact_match"]
        assert metric["cases"] == 2
        assert metric["evaluated"] == 1
        assert metric["errors"] == 1
        assert metric["accuracy"] == 1.0  # the one scored case passed

    @pytest.mark.asyncio
    async def test_not_evaluated_excluded_and_null_when_none_scored(self):
        summary = await self._summary([
            {"exact_match": {"key": "exact_match", "not_evaluated": True, "score": None}},
        ])
        metric = summary["exact_match"]
        assert metric["evaluated"] == 0
        assert metric["not_evaluated"] == 1
        assert metric["accuracy"] is None
        assert metric["avg_score"] is None

    @pytest.mark.asyncio
    async def test_scored_cases_report_pass_rate_and_coverage(self):
        summary = await self._summary([
            {"exact_match": {"key": "exact_match", "passed": True, "score": True}},
            {"exact_match": {"key": "exact_match", "passed": False, "score": False}},
        ])
        metric = summary["exact_match"]
        assert metric["cases"] == 2
        assert metric["evaluated"] == 2
        assert metric["accuracy"] == 0.5


class TestRunPathLabelResolution:
    @pytest.mark.asyncio
    async def test_run_loop_passes_workflow_so_comments_use_node_labels(self):
        """The run loop must hand the workflow graph to the evaluators — without
        it, route/action comments degrade to 'unknown node' for real runs."""
        service = _service()
        now = datetime(2026, 1, 1)
        router_id = str(uuid4())
        case = SimpleNamespace(
            id=uuid4(),
            suite_id=uuid4(),
            source_conversation_id=None,
            turn_index=None,
            input_data={"message": "hi"},
            expected_output={"value": "ok"},
            tags=["imported"],
            weight=None,
            created_at=now,
            updated_at=now,
        )
        service.case_repo.get_all_for_suite.return_value = [case]

        suite = SimpleNamespace(id=uuid4(), default_input_metadata=None)
        workflow = SimpleNamespace(
            id=uuid4(),
            nodes=[{"id": router_id, "type": "routerNode", "data": {"name": "Escalation Router"}}],
            edges=[],
        )
        run = SimpleNamespace(
            id=uuid4(), techniques=["route_taken"], status="queued", summary_metrics=None
        )
        engine = MagicMock()
        engine.execute_from_node = AsyncMock(
            return_value=SimpleNamespace(
                output="out",
                status="ok",
                # The router never ran, so only the workflow graph can name it.
                format_state_as_response=lambda: {"state": {"nodeExecutionStatus": {}}},
            )
        )
        with patch("app.services.test_suite.WorkflowEngine", return_value=engine):
            await service._execute_run(
                suite,
                workflow,
                run,
                technique_configs={
                    "route_taken": {"rules": [{"router": router_id, "expected": "true"}]}
                },
            )

        persisted = service.result_repo.create.call_args[0][0]
        comment = persisted.metrics["route_taken"]["comment"]
        assert "Escalation Router" in comment
        assert router_id not in comment
        assert "unknown node" not in comment


class TestPausedConversationExecution:
    @staticmethod
    def _case(*, suite_id, conversation_id, turn_index, message):
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        return SimpleNamespace(
            id=uuid4(),
            suite_id=suite_id,
            source_conversation_id=conversation_id,
            turn_index=turn_index,
            input_data={"message": message},
            expected_output={"value": "answer"},
            tags=["imported"],
            weight=None,
            created_at=now,
            updated_at=now,
        )

    @staticmethod
    def _state(output):
        return SimpleNamespace(
            output=output,
            status="completed",
            format_state_as_response=lambda: {
                "output": output,
                "state": {"errors": [], "nodeExecutionStatus": {}},
            },
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("use_memory", [False, True])
    async def test_pause_skips_only_later_turns_in_that_conversation(
        self, use_memory
    ):
        service = _service()
        suite_id = uuid4()
        paused_conversation_id = uuid4()
        other_conversation_id = uuid4()
        first = self._case(
            suite_id=suite_id,
            conversation_id=paused_conversation_id,
            turn_index=0,
            message="First turn",
        )
        paused = self._case(
            suite_id=suite_id,
            conversation_id=paused_conversation_id,
            turn_index=1,
            message="Needs employee details",
        )
        skipped = self._case(
            suite_id=suite_id,
            conversation_id=paused_conversation_id,
            turn_index=2,
            message="Must not execute before the human reply",
        )
        independent = self._case(
            suite_id=suite_id,
            conversation_id=other_conversation_id,
            turn_index=0,
            message="Independent conversation",
        )
        service.case_repo.get_all_for_suite.return_value = [
            first,
            paused,
            skipped,
            independent,
        ]

        engine = MagicMock()
        engine.execute_from_node = AsyncMock(
            side_effect=[
                self._state("First answer"),
                self._state(
                    {
                        "status": "awaiting_input",
                        "form_schema": {"fields": [{"name": "employee_id"}]},
                    }
                ),
                self._state("Independent answer"),
            ]
        )
        suite = SimpleNamespace(
            id=suite_id,
            default_input_metadata=None,
        )
        workflow = SimpleNamespace(id=uuid4(), nodes=[], edges=[])
        run = SimpleNamespace(
            id=uuid4(),
            techniques=["no_errors"],
            status="queued",
            summary_metrics=None,
        )

        with patch("app.services.test_suite.WorkflowEngine", return_value=engine):
            await service._execute_run(
                suite,
                workflow,
                run,
                run_input_metadata={"use_memory": use_memory},
            )

        executed_messages = [
            call.kwargs["input_data"]["message"]
            for call in engine.execute_from_node.await_args_list
        ]
        assert executed_messages == [
            "First turn",
            "Needs employee details",
            "Independent conversation",
        ]

        created_results = [
            call.args[0] for call in service.result_repo.create.await_args_list
        ]
        skipped_result = next(
            result for result in created_results if result.case_id == skipped.id
        )
        assert skipped_result.status == "skipped"
        assert skipped_result.error == (
            "Skipped: an earlier turn is waiting for human input"
        )
        assert run.status == "completed"
        assert run.summary_metrics["_totals"]["executed"] == 3
        assert run.summary_metrics["_totals"]["skipped"] == 1


class TestWatchdogRepo:
    @pytest.mark.asyncio
    async def test_mark_stuck_as_failed_commits_and_returns_rowcount(self):
        from app.repositories.test_suite import TestRunRepository

        db = MagicMock()
        db.execute = AsyncMock(return_value=SimpleNamespace(rowcount=3))
        db.commit = AsyncMock()
        repo = TestRunRepository(db)

        now = datetime.now(timezone.utc)
        failed = await repo.mark_stuck_as_failed(
            queued_before=now, running_before=now, error_message="stuck"
        )

        assert failed == 3
        db.execute.assert_awaited_once()
        db.commit.assert_awaited_once()


class TestWatchdogTask:
    @pytest.mark.asyncio
    async def test_reconcile_calls_repo_with_thresholds(self):
        from app.tasks import test_suite_tasks

        repo = MagicMock()
        repo.mark_stuck_as_failed = AsyncMock(return_value=2)

        session = AsyncMock()
        session_cm = MagicMock()
        session_cm.__aenter__ = AsyncMock(return_value=session)
        session_cm.__aexit__ = AsyncMock(return_value=False)
        factory = MagicMock(return_value=session_cm)

        with patch.object(
            test_suite_tasks.multi_tenant_manager,
            "get_tenant_session_factory",
            return_value=factory,
        ), patch.object(
            test_suite_tasks, "TestRunRepository", return_value=repo
        ), patch.object(
            test_suite_tasks, "get_tenant_context", return_value="tenant_a"
        ):
            await test_suite_tasks.reconcile_stuck_test_runs_async()

        repo.mark_stuck_as_failed.assert_awaited_once()
        kwargs = repo.mark_stuck_as_failed.await_args.kwargs
        # 15-min queued cutoff is more recent than the 2h10m running cutoff.
        assert kwargs["queued_before"] > kwargs["running_before"]
        assert kwargs["error_message"]
