"""Unit tests for multi-conversation datasets: grouping, turn order, thread isolation."""
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.exceptions.exception_classes import AppException
from app.modules.workflow.engine.workflow_engine import (
    MemoryPersistenceError,
    should_persist_to_memory,
)
from app.services.test_suite import (
    ResultStatus,
    TestSuiteService as EvalService,
    _failure_reason,
    _group_cases_into_conversations,
)


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


def _case(*, conversation_id=None, turn_index=None, message="hi", created_at=None):
    now = created_at or datetime(2026, 1, 1)
    return SimpleNamespace(
        id=uuid4(),
        suite_id=uuid4(),
        source_conversation_id=conversation_id,
        turn_index=turn_index,
        input_data={"message": message},
        expected_output={"value": "ok"},
        tags=["imported"],
        weight=None,
        created_at=now,
        updated_at=now,
    )


def _message(text, speaker, sequence_number):
    return SimpleNamespace(text=text, speaker=speaker, sequence_number=sequence_number)


class TestGroupCasesIntoConversations:
    def test_groups_by_source_conversation(self):
        first, second = uuid4(), uuid4()
        cases = [
            _case(conversation_id=first, turn_index=0),
            _case(conversation_id=second, turn_index=0),
            _case(conversation_id=first, turn_index=1),
        ]

        groups = _group_cases_into_conversations(cases)

        assert [len(group) for group in groups] == [2, 1]
        assert {case.source_conversation_id for case in groups[0]} == {first}
        assert {case.source_conversation_id for case in groups[1]} == {second}

    def test_orders_turns_within_a_conversation(self):
        conversation_id = uuid4()
        cases = [
            _case(conversation_id=conversation_id, turn_index=2, message="third"),
            _case(conversation_id=conversation_id, turn_index=0, message="first"),
            _case(conversation_id=conversation_id, turn_index=1, message="second"),
        ]

        (group,) = _group_cases_into_conversations(cases)

        assert [case.input_data["message"] for case in group] == [
            "first",
            "second",
            "third",
        ]

    def test_cases_without_a_conversation_stay_independent(self):
        """Null must not collapse manual and legacy cases into one shared group."""
        cases = [_case(), _case(), _case()]

        groups = _group_cases_into_conversations(cases)

        assert len(groups) == 3
        assert all(len(group) == 1 for group in groups)


class TestThreadIsolation:
    """Same conversation shares a thread; conversations and runs never do."""

    async def _run(self, service, cases, *, use_memory=True):
        suite = SimpleNamespace(id=uuid4(), default_input_metadata=None)
        workflow = SimpleNamespace(id=uuid4(), nodes=[], edges=[])
        run = SimpleNamespace(
            id=uuid4(), techniques=["no_errors"], status="queued", summary_metrics=None
        )
        service.case_repo.get_all_for_suite.return_value = cases
        service.evaluators = MagicMock()
        service.evaluators.evaluate = AsyncMock(return_value={})

        engine = MagicMock()
        engine.execute_from_node = AsyncMock(
            return_value=SimpleNamespace(
                output="out", format_state_as_response=lambda: {}
            )
        )
        with patch(
            "app.services.test_suite.WorkflowEngine", return_value=engine
        ):
            await service._execute_run(
                suite,
                workflow,
                run,
                run_input_metadata={"use_memory": True} if use_memory else None,
            )
        return [call.kwargs for call in engine.execute_from_node.call_args_list]

    @pytest.mark.asyncio
    async def test_same_conversation_shares_one_thread(self):
        conversation_id = uuid4()
        cases = [
            _case(conversation_id=conversation_id, turn_index=0),
            _case(conversation_id=conversation_id, turn_index=1),
        ]

        calls = await self._run(_service(), cases)

        threads = {call["thread_id"] for call in calls}
        assert len(calls) == 2
        assert len(threads) == 1
        assert None not in threads

    @pytest.mark.asyncio
    async def test_different_conversations_use_different_threads(self):
        first, second = uuid4(), uuid4()
        cases = [
            _case(conversation_id=first, turn_index=0),
            _case(conversation_id=second, turn_index=0),
        ]

        calls = await self._run(_service(), cases)

        assert calls[0]["thread_id"] != calls[1]["thread_id"]

    @pytest.mark.asyncio
    async def test_each_run_generates_new_threads(self):
        conversation_id = uuid4()
        cases = [_case(conversation_id=conversation_id, turn_index=0)]

        first_run = await self._run(_service(), cases)
        second_run = await self._run(_service(), cases)

        assert first_run[0]["thread_id"] != second_run[0]["thread_id"]

    @pytest.mark.asyncio
    async def test_memory_disabled_keeps_every_case_independent(self):
        conversation_id = uuid4()
        cases = [
            _case(conversation_id=conversation_id, turn_index=0),
            _case(conversation_id=conversation_id, turn_index=1),
        ]

        calls = await self._run(_service(), cases, use_memory=False)

        assert all(call["thread_id"] is None for call in calls)
        assert all(call["persist"] is False for call in calls)

    @pytest.mark.asyncio
    async def test_turns_are_persisted_before_the_next_turn_runs(self):
        conversation_id = uuid4()
        cases = [_case(conversation_id=conversation_id, turn_index=0)]

        calls = await self._run(_service(), cases)

        assert calls[0]["await_persist"] is True

    @pytest.mark.asyncio
    async def test_stored_metadata_cannot_override_the_generated_thread(self):
        conversation_id = uuid4()
        case = _case(conversation_id=conversation_id, turn_index=0)
        case.input_data = {"message": "hi", "thread_id": "injected-thread"}

        calls = await self._run(_service(), [case])

        assert calls[0]["thread_id"] != "injected-thread"
        assert calls[0]["input_data"]["thread_id"] == calls[0]["thread_id"]


class TestPersistenceFailureHandling:
    """A broken memory write must stop its own conversation only."""

    async def _run_with_failures(self, service, cases, failing_messages):
        suite = SimpleNamespace(id=uuid4(), default_input_metadata=None)
        workflow = SimpleNamespace(id=uuid4(), nodes=[], edges=[])
        run = SimpleNamespace(
            id=uuid4(), techniques=["no_errors"], status="queued", summary_metrics=None
        )
        service.case_repo.get_all_for_suite.return_value = cases
        service.evaluators = MagicMock()
        service.evaluators.evaluate = AsyncMock(return_value={})

        executed: list[str] = []

        async def execute(**kwargs):
            message = kwargs["input_data"].get("message")
            executed.append(message)
            if message in failing_messages:
                raise MemoryPersistenceError("redis unavailable")
            return SimpleNamespace(output="out", format_state_as_response=lambda: {})

        engine = MagicMock()
        engine.execute_from_node = AsyncMock(side_effect=execute)
        with patch("app.services.test_suite.WorkflowEngine", return_value=engine):
            await service._execute_run(
                suite, workflow, run, run_input_metadata={"use_memory": True}
            )

        errors = [
            call.args[0].error
            for call in service.result_repo.create.call_args_list
            if call.args[0].error
        ]
        return executed, errors

    @pytest.mark.asyncio
    async def test_failed_write_skips_later_turns_of_same_conversation(self):
        conversation_id = uuid4()
        cases = [
            _case(conversation_id=conversation_id, turn_index=0, message="turn1"),
            _case(conversation_id=conversation_id, turn_index=1, message="turn2"),
            _case(conversation_id=conversation_id, turn_index=2, message="turn3"),
        ]

        executed, errors = await self._run_with_failures(
            _service(), cases, {"turn1"}
        )

        assert executed == ["turn1"]
        assert any("Memory write failed" in error for error in errors)
        assert sum("Skipped" in error for error in errors) == 2

    @pytest.mark.asyncio
    async def test_other_conversations_still_run(self):
        first, second = uuid4(), uuid4()
        cases = [
            _case(conversation_id=first, turn_index=0, message="A1"),
            _case(conversation_id=first, turn_index=1, message="A2"),
            _case(conversation_id=second, turn_index=0, message="B1"),
        ]

        executed, _ = await self._run_with_failures(_service(), cases, {"A1"})

        assert "A2" not in executed
        assert "B1" in executed


class TestExecutionFailureSemantics:
    """Only failures that break the memory chain stop a conversation."""

    async def _run(self, service, cases, *, engine_side_effect=None, scoring_error=False):
        suite = SimpleNamespace(id=uuid4(), default_input_metadata=None)
        workflow = SimpleNamespace(id=uuid4(), nodes=[], edges=[])
        run = SimpleNamespace(
            id=uuid4(), techniques=["no_errors"], status="queued", summary_metrics=None
        )
        service.case_repo.get_all_for_suite.return_value = cases
        service.evaluators = MagicMock()
        service.evaluators.evaluate = AsyncMock(
            side_effect=RuntimeError("judge exploded") if scoring_error else None,
            return_value={},
        )

        executed: list[str] = []

        async def execute(**kwargs):
            message = kwargs["input_data"].get("message")
            executed.append(message)
            if engine_side_effect:
                engine_side_effect(message)
            return SimpleNamespace(output="out", format_state_as_response=lambda: {})

        engine = MagicMock()
        engine.execute_from_node = AsyncMock(side_effect=execute)
        with patch("app.services.test_suite.WorkflowEngine", return_value=engine):
            await service._execute_run(
                suite, workflow, run, run_input_metadata={"use_memory": True}
            )

        errors = [
            call.args[0].error
            for call in service.result_repo.create.call_args_list
            if call.args[0].error
        ]
        return executed, errors, run

    @pytest.mark.asyncio
    async def test_engine_failure_stops_the_conversation(self):
        conversation_id = uuid4()
        cases = [
            _case(conversation_id=conversation_id, turn_index=0, message="turn1"),
            _case(conversation_id=conversation_id, turn_index=1, message="turn2"),
        ]

        def blow_up(message):
            if message == "turn1":
                raise RuntimeError("workflow exploded")

        executed, errors, _ = await self._run(
            _service(), cases, engine_side_effect=blow_up
        )

        assert executed == ["turn1"]
        assert any("Execution failed" in error for error in errors)
        assert any("Skipped" in error for error in errors)

    @pytest.mark.asyncio
    async def test_scoring_failure_does_not_stop_the_conversation(self):
        conversation_id = uuid4()
        cases = [
            _case(conversation_id=conversation_id, turn_index=0, message="turn1"),
            _case(conversation_id=conversation_id, turn_index=1, message="turn2"),
        ]

        executed, errors, _ = await self._run(_service(), cases, scoring_error=True)

        assert executed == ["turn1", "turn2"]
        assert all("Skipped" not in error for error in errors)

    @pytest.mark.asyncio
    async def test_missing_message_field_stops_the_conversation(self):
        conversation_id = uuid4()
        first = _case(conversation_id=conversation_id, turn_index=0, message="turn1")
        second = _case(conversation_id=conversation_id, turn_index=1)
        second.input_data = {"document": "no message field"}
        third = _case(conversation_id=conversation_id, turn_index=2, message="turn3")

        executed, errors, _ = await self._run(_service(), [first, second, third])

        assert executed == ["turn1"]
        assert any("no 'message' field" in error for error in errors)
        assert any("Skipped" in error for error in errors)

    @pytest.mark.asyncio
    async def test_failed_state_is_treated_as_an_execution_failure(self):
        """The engine reports some failures on the state rather than raising."""
        conversation_id = uuid4()
        cases = [
            _case(conversation_id=conversation_id, turn_index=0, message="turn1"),
            _case(conversation_id=conversation_id, turn_index=1, message="turn2"),
        ]
        service = _service()
        service.case_repo.get_all_for_suite.return_value = cases
        service.evaluators = MagicMock()
        service.evaluators.evaluate = AsyncMock(return_value={})

        engine = MagicMock()
        engine.execute_from_node = AsyncMock(
            return_value=SimpleNamespace(
                output="boom", status="failed", format_state_as_response=lambda: {}
            )
        )
        run = SimpleNamespace(
            id=uuid4(), techniques=["no_errors"], status="queued", summary_metrics=None
        )
        with patch("app.services.test_suite.WorkflowEngine", return_value=engine):
            await service._execute_run(
                SimpleNamespace(id=uuid4(), default_input_metadata=None),
                SimpleNamespace(id=uuid4(), nodes=[], edges=[]),
                run,
                run_input_metadata={"use_memory": True},
            )

        errors = [
            call.args[0].error
            for call in service.result_repo.create.call_args_list
            if call.args[0].error
        ]
        assert engine.execute_from_node.await_count == 1
        assert any("Execution failed" in error for error in errors)
        assert any("Skipped" in error for error in errors)
        assert service.evaluators.evaluate.await_count == 0

    @pytest.mark.asyncio
    async def test_engine_failure_without_memory_keeps_cases_independent(self):
        conversation_id = uuid4()
        cases = [
            _case(conversation_id=conversation_id, turn_index=0, message="turn1"),
            _case(conversation_id=conversation_id, turn_index=1, message="turn2"),
        ]

        def blow_up(message):
            if message == "turn1":
                raise RuntimeError("workflow exploded")

        service = _service()
        suite = SimpleNamespace(id=uuid4(), default_input_metadata=None)
        workflow = SimpleNamespace(id=uuid4(), nodes=[], edges=[])
        run = SimpleNamespace(
            id=uuid4(), techniques=["no_errors"], status="queued", summary_metrics=None
        )
        service.case_repo.get_all_for_suite.return_value = cases
        service.evaluators = MagicMock()
        service.evaluators.evaluate = AsyncMock(return_value={})

        executed: list[str] = []

        async def execute(**kwargs):
            message = kwargs["input_data"].get("message")
            executed.append(message)
            blow_up(message)
            return SimpleNamespace(
                output="out", status="completed", format_state_as_response=lambda: {}
            )

        engine = MagicMock()
        engine.execute_from_node = AsyncMock(side_effect=execute)
        with patch("app.services.test_suite.WorkflowEngine", return_value=engine):
            # No use_memory: the cases share a conversation but not a thread.
            await service._execute_run(suite, workflow, run, run_input_metadata=None)

        assert executed == ["turn1", "turn2"]

    @pytest.mark.asyncio
    async def test_summary_reports_unexecuted_cases(self):
        conversation_id = uuid4()
        cases = [
            _case(conversation_id=conversation_id, turn_index=0, message="turn1"),
            _case(conversation_id=conversation_id, turn_index=1, message="turn2"),
        ]

        def blow_up(message):
            if message == "turn1":
                raise RuntimeError("workflow exploded")

        _, _, run = await self._run(_service(), cases, engine_side_effect=blow_up)

        assert run.summary_metrics["_totals"] == {
            "cases": 2,
            "executed": 0,
            "scored": 0,
            "scoring_failed": 0,
            "execution_failed": 1,
            "skipped": 1,
        }

    @pytest.mark.asyncio
    async def test_scoring_failure_still_counts_as_executed(self):
        """A turn that ran but failed scoring is executed-but-unscored, not skipped."""
        conversation_id = uuid4()
        cases = [_case(conversation_id=conversation_id, turn_index=0, message="t1")]

        _, _, run = await self._run(_service(), cases, scoring_error=True)

        totals = run.summary_metrics["_totals"]
        assert totals["executed"] == 1
        assert totals["scored"] == 0
        assert totals["scoring_failed"] == 1
        assert totals["skipped"] == 0
        assert totals["execution_failed"] == 0

    @pytest.mark.asyncio
    async def test_statuses_are_recorded_on_results(self):
        conversation_id = uuid4()
        cases = [
            _case(conversation_id=conversation_id, turn_index=0, message="t1"),
            _case(conversation_id=conversation_id, turn_index=1, message="t2"),
        ]

        def blow_up(message):
            if message == "t1":
                raise RuntimeError("boom")

        service = _service()
        await self._run(service, cases, engine_side_effect=blow_up)

        statuses = [
            call.args[0].status for call in service.result_repo.create.call_args_list
        ]
        assert statuses == [ResultStatus.EXECUTION_FAILED, ResultStatus.SKIPPED]


class TestRemoveConversationFromSuite:
    @pytest.mark.asyncio
    async def test_removes_only_the_named_conversation(self):
        service = _service()
        suite_id, conversation_a = uuid4(), uuid4()
        service.suite_repo.get_by_id.return_value = SimpleNamespace(id=suite_id)

        await service.remove_conversation_from_suite(suite_id, conversation_a)

        service.case_repo.soft_delete_for_conversation.assert_awaited_once_with(
            suite_id, conversation_a
        )
        service.case_repo.soft_delete_all_for_suite.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_conversation_b_cases_are_untouched(self):
        """The delete is scoped by conversation, so B's rows never match."""
        suite_id, conversation_a, conversation_b = uuid4(), uuid4(), uuid4()
        remaining = [
            _case(conversation_id=conversation_b, turn_index=0),
            _case(conversation_id=conversation_b, turn_index=1),
        ]
        service = _service()
        service.suite_repo.get_by_id.return_value = SimpleNamespace(id=suite_id)
        service.case_repo.get_all_for_suite.return_value = remaining

        await service.remove_conversation_from_suite(suite_id, conversation_a)

        target_suite, target_conversation = (
            service.case_repo.soft_delete_for_conversation.await_args.args
        )
        assert target_conversation == conversation_a
        assert target_conversation != conversation_b
        assert target_suite == suite_id

        survivors = await service.list_cases_for_suite(suite_id)
        assert len(survivors) == 2
        assert all(c.source_conversation_id == conversation_b for c in survivors)

    @pytest.mark.asyncio
    async def test_unknown_suite_is_rejected(self):
        service = _service()
        service.suite_repo.get_by_id.return_value = None

        with pytest.raises(AppException):
            await service.remove_conversation_from_suite(uuid4(), uuid4())

        service.case_repo.soft_delete_for_conversation.assert_not_awaited()


class TestFailureReason:
    """Failures live on state.errors; state.output is empty for a failed run."""

    def test_uses_last_error_message(self):
        state = SimpleNamespace(
            output="",
            errors=[{"message": "first"}, {"message": "node X exploded"}],
        )
        assert _failure_reason(state) == "node X exploded"

    def test_falls_back_when_no_errors(self):
        assert _failure_reason(SimpleNamespace(output="", errors=[])) == (
            "Workflow execution failed"
        )

    def test_falls_back_when_message_is_empty(self):
        state = SimpleNamespace(output="", errors=[{"message": ""}])
        assert _failure_reason(state) == "Workflow execution failed"


class TestEmptyMessagePersistence:
    """Presence of a message field decides persistence, not its truthiness."""

    def test_empty_message_is_persisted(self):
        assert should_persist_to_memory({"message": ""}, True, "completed") is True

    def test_normal_message_is_persisted(self):
        assert should_persist_to_memory({"message": "hi"}, True, "completed") is True

    def test_missing_message_field_is_not_persisted(self):
        assert should_persist_to_memory({"document": "x"}, True, "completed") is False

    def test_persist_disabled_wins(self):
        assert should_persist_to_memory({"message": "hi"}, False, "completed") is False

    def test_failed_run_is_never_persisted(self):
        assert should_persist_to_memory({"message": "hi"}, True, "failed") is False


class TestEngineMemoryFailureConversion:
    """A real memory write failure must surface as MemoryPersistenceError."""

    @pytest.mark.asyncio
    async def test_awaited_write_failure_is_converted(self):
        from app.modules.workflow.engine.workflow_engine import WorkflowEngine

        engine = WorkflowEngine(
            {"id": str(uuid4()), "nodes": [{"id": "n1", "type": "inputNode"}], "edges": []}
        )

        memory = MagicMock()
        memory.add_input_output = AsyncMock(side_effect=RuntimeError("redis down"))

        with patch.object(
            WorkflowEngine, "_execute_from_node_recursive", new=AsyncMock()
        ), patch(
            "app.modules.workflow.engine.workflow_state.ConversationMemory.get_instance",
            return_value=memory,
        ):
            with pytest.raises(MemoryPersistenceError):
                await engine.execute_from_node(
                    start_node_id="n1",
                    input_data={"message": "hello"},
                    thread_id=str(uuid4()),
                    await_persist=True,
                )

        memory.add_input_output.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_background_write_failure_does_not_raise(self):
        """Interactive chat keeps its fire-and-forget behaviour."""
        from app.modules.workflow.engine.workflow_engine import WorkflowEngine

        engine = WorkflowEngine(
            {"id": str(uuid4()), "nodes": [{"id": "n1", "type": "inputNode"}], "edges": []}
        )

        memory = MagicMock()
        memory.add_input_output = AsyncMock(side_effect=RuntimeError("redis down"))

        with patch.object(
            WorkflowEngine, "_execute_from_node_recursive", new=AsyncMock()
        ), patch(
            "app.modules.workflow.engine.workflow_state.ConversationMemory.get_instance",
            return_value=memory,
        ):
            state = await engine.execute_from_node(
                start_node_id="n1",
                input_data={"message": "hello"},
                thread_id=str(uuid4()),
                await_persist=False,
            )

        assert state is not None


class TestImportFromConversation:
    def _conversation(self):
        return SimpleNamespace(
            messages=[
                _message("q1", "customer", 0),
                _message("a1", "agent", 1),
                _message("q2", "customer", 2),
                _message("a2", "agent", 3),
            ]
        )

    def _persist(self, cases):
        """Stand in for the insert, which assigns the id and timestamps."""
        now = datetime(2026, 1, 1)
        for case in cases:
            case.id = uuid4()
            case.created_at = now
            case.updated_at = now
        return cases

    async def _import(self, service, *, suite_id, conversation_id, replace=False):
        service.suite_repo.get_by_id.return_value = SimpleNamespace(id=suite_id)
        service.conversation_repo.fetch_conversation_by_id.return_value = (
            self._conversation()
        )
        service.case_repo.create_many.side_effect = self._persist
        return await service.import_cases_from_conversation(
            suite_id, conversation_id, replace=replace
        )

    @pytest.mark.asyncio
    async def test_stamps_conversation_and_turn_index(self):
        service = _service()
        conversation_id = uuid4()

        created = await self._import(
            service, suite_id=uuid4(), conversation_id=conversation_id
        )

        assert [case.turn_index for case in created] == [0, 1]
        assert all(case.source_conversation_id == conversation_id for case in created)

    @pytest.mark.asyncio
    async def test_append_replaces_only_that_conversation(self):
        service = _service()
        suite_id, conversation_id = uuid4(), uuid4()

        await self._import(
            service, suite_id=suite_id, conversation_id=conversation_id
        )

        service.case_repo.soft_delete_for_conversation.assert_awaited_once_with(
            suite_id, conversation_id, commit=False
        )
        service.case_repo.soft_delete_all_for_suite.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_replace_clears_the_whole_suite(self):
        service = _service()
        suite_id = uuid4()

        await self._import(
            service, suite_id=suite_id, conversation_id=uuid4(), replace=True
        )

        service.case_repo.soft_delete_all_for_suite.assert_awaited_once_with(
            suite_id, commit=False
        )
        service.case_repo.soft_delete_for_conversation.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_empty_conversation_is_rejected_before_deleting_anything(self):
        service = _service()
        service.suite_repo.get_by_id.return_value = SimpleNamespace(id=uuid4())
        service.conversation_repo.fetch_conversation_by_id.return_value = (
            SimpleNamespace(messages=[])
        )

        with pytest.raises(AppException):
            await service.import_cases_from_conversation(uuid4(), uuid4())

        service.case_repo.soft_delete_all_for_suite.assert_not_awaited()
        service.case_repo.soft_delete_for_conversation.assert_not_awaited()
        service.case_repo.create_many.assert_not_awaited()
