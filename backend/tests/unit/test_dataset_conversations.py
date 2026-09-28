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
        tool_rule_result_repo=AsyncMock(),
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

    def _import_recording_dates(self, service, *, suite_id, conversation_id):
        """Import, capturing created_at as it was at insert time.

        ``_persist`` stands in for the database and overwrites the timestamps,
        so the value under test has to be read before it runs.
        """
        stamped = []

        def persist(cases):
            stamped.extend(case.created_at for case in cases)
            return self._persist(cases)

        service.suite_repo.get_by_id.return_value = SimpleNamespace(id=suite_id)
        service.conversation_repo.fetch_conversation_by_id.return_value = (
            self._conversation()
        )
        service.case_repo.create_many.side_effect = persist
        return stamped

    @pytest.mark.asyncio
    async def test_reimport_keeps_the_date_the_conversation_first_joined(self):
        service = _service()
        suite_id, conversation_id = uuid4(), uuid4()
        first_joined = datetime(2025, 6, 1)
        service.case_repo.get_all_for_suite.return_value = [
            _case(
                conversation_id=conversation_id,
                turn_index=0,
                created_at=first_joined,
            ),
            _case(
                conversation_id=conversation_id,
                turn_index=1,
                created_at=datetime(2025, 6, 2),
            ),
            # An older conversation must not donate its date to this one.
            _case(
                conversation_id=uuid4(),
                turn_index=0,
                created_at=datetime(2024, 1, 1),
            ),
        ]
        stamped = self._import_recording_dates(
            service, suite_id=suite_id, conversation_id=conversation_id
        )

        await service.import_cases_from_conversation(suite_id, conversation_id)

        assert stamped == [first_joined, first_joined]

    @pytest.mark.asyncio
    async def test_first_import_lets_the_database_set_the_date(self):
        service = _service()
        suite_id, conversation_id = uuid4(), uuid4()
        service.case_repo.get_all_for_suite.return_value = []
        stamped = self._import_recording_dates(
            service, suite_id=suite_id, conversation_id=conversation_id
        )

        await service.import_cases_from_conversation(suite_id, conversation_id)

        assert stamped == [None, None]

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


class TestImportFromConversations:
    """Importing a selection of conversations in one request."""

    def _conversation(self, turns=2):
        messages = []
        for turn in range(turns):
            messages.append(_message(f"q{turn}", "customer", turn * 2))
            messages.append(_message(f"a{turn}", "agent", turn * 2 + 1))
        return SimpleNamespace(messages=messages)

    def _persist(self, cases):
        """Stand in for the insert, which assigns the id and timestamps."""
        now = datetime(2026, 1, 1)
        for case in cases:
            case.id = uuid4()
            case.created_at = now
            case.updated_at = now
        return cases

    def _arrange(self, service, transcripts):
        """Wire the repos so each conversation id resolves to its own transcript."""
        service.suite_repo.get_by_id.return_value = SimpleNamespace(id=uuid4())
        service.conversation_repo.fetch_conversation_by_id.side_effect = (
            lambda conversation_id, **_: transcripts.get(conversation_id)
        )
        service.case_repo.create_many.side_effect = self._persist

    @pytest.mark.asyncio
    async def test_imports_every_selected_conversation(self):
        service = _service()
        suite_id, first, second = uuid4(), uuid4(), uuid4()
        self._arrange(
            service,
            {first: self._conversation(turns=2), second: self._conversation(turns=3)},
        )

        result = await service.import_cases_from_conversations(
            suite_id, [first, second]
        )

        assert result.imported == 2
        assert result.failed == 0
        assert [entry.turns for entry in result.results] == [2, 3]
        assert len(result.cases) == 5

    @pytest.mark.asyncio
    async def test_turn_index_restarts_for_each_conversation(self):
        service = _service()
        first, second = uuid4(), uuid4()
        self._arrange(
            service,
            {first: self._conversation(turns=2), second: self._conversation(turns=2)},
        )

        result = await service.import_cases_from_conversations(
            uuid4(), [first, second]
        )

        by_conversation = {}
        for case in result.cases:
            by_conversation.setdefault(case.source_conversation_id, []).append(
                case.turn_index
            )
        assert by_conversation[first] == [0, 1]
        assert by_conversation[second] == [0, 1]

    @pytest.mark.asyncio
    async def test_the_whole_selection_is_written_as_one_insert(self):
        service = _service()
        first, second = uuid4(), uuid4()
        self._arrange(
            service,
            {first: self._conversation(), second: self._conversation()},
        )

        await service.import_cases_from_conversations(uuid4(), [first, second])

        service.case_repo.create_many.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_one_unusable_conversation_does_not_block_the_rest(self):
        service = _service()
        suite_id, good, empty = uuid4(), uuid4(), uuid4()
        self._arrange(
            service,
            {good: self._conversation(turns=2), empty: SimpleNamespace(messages=[])},
        )

        result = await service.import_cases_from_conversations(
            suite_id, [empty, good]
        )

        assert result.imported == 1
        assert result.failed == 1
        assert [entry.status for entry in result.results] == ["failed", "imported"]
        assert result.results[0].detail == "No question and answer turns to import."
        assert len(result.cases) == 2
        # Only the importable conversation gives up its old turns.
        service.case_repo.soft_delete_for_conversation.assert_awaited_once_with(
            suite_id, good, commit=False
        )

    @pytest.mark.asyncio
    async def test_a_missing_conversation_is_reported_rather_than_raised(self):
        service = _service()
        good, missing = uuid4(), uuid4()
        self._arrange(service, {good: self._conversation()})

        result = await service.import_cases_from_conversations(
            uuid4(), [good, missing]
        )

        assert result.results[1].status == "failed"
        assert result.results[1].detail == "Conversation not found."
        assert result.imported == 1

    @pytest.mark.asyncio
    async def test_nothing_is_deleted_when_no_conversation_can_be_imported(self):
        service = _service()
        first, second = uuid4(), uuid4()
        self._arrange(
            service,
            {
                first: SimpleNamespace(messages=[]),
                second: SimpleNamespace(messages=[]),
            },
        )

        result = await service.import_cases_from_conversations(
            uuid4(), [first, second]
        )

        assert result.failed == 2
        assert result.cases == []
        service.case_repo.soft_delete_all_for_suite.assert_not_awaited()
        service.case_repo.soft_delete_for_conversation.assert_not_awaited()
        service.case_repo.create_many.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_replace_wipes_the_suite_once_for_the_whole_selection(self):
        service = _service()
        suite_id, first, second = uuid4(), uuid4(), uuid4()
        self._arrange(
            service,
            {first: self._conversation(), second: self._conversation()},
        )

        await service.import_cases_from_conversations(
            suite_id, [first, second], replace=True
        )

        service.case_repo.soft_delete_all_for_suite.assert_awaited_once_with(
            suite_id, commit=False
        )
        service.case_repo.soft_delete_for_conversation.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_replace_leaves_the_suite_alone_when_nothing_is_importable(self):
        service = _service()
        self._arrange(service, {})

        result = await service.import_cases_from_conversations(
            uuid4(), [uuid4()], replace=True
        )

        assert result.failed == 1
        service.case_repo.soft_delete_all_for_suite.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_the_same_conversation_picked_twice_is_imported_once(self):
        service = _service()
        conversation_id = uuid4()
        self._arrange(service, {conversation_id: self._conversation(turns=2)})

        result = await service.import_cases_from_conversations(
            uuid4(), [conversation_id, conversation_id]
        )

        assert len(result.results) == 1
        assert len(result.cases) == 2

    @pytest.mark.asyncio
    async def test_a_conversation_already_in_the_dataset_reads_as_replaced(self):
        service = _service()
        suite_id, existing_id, fresh_id = uuid4(), uuid4(), uuid4()
        first_joined = datetime(2025, 6, 1)
        service.case_repo.get_all_for_suite.return_value = [
            _case(conversation_id=existing_id, turn_index=0, created_at=first_joined),
        ]
        self._arrange(
            service,
            {existing_id: self._conversation(), fresh_id: self._conversation()},
        )

        result = await service.import_cases_from_conversations(
            suite_id, [existing_id, fresh_id]
        )

        assert [entry.status for entry in result.results] == ["replaced", "imported"]
        assert result.replaced == 1
        assert result.imported == 1

    @pytest.mark.asyncio
    async def test_a_reimported_conversation_keeps_the_date_it_first_joined(self):
        service = _service()
        suite_id, existing_id = uuid4(), uuid4()
        first_joined = datetime(2025, 6, 1)
        service.case_repo.get_all_for_suite.return_value = [
            _case(conversation_id=existing_id, turn_index=0, created_at=first_joined),
            # An older conversation must not donate its date to this one.
            _case(conversation_id=uuid4(), turn_index=0, created_at=datetime(2024, 1, 1)),
        ]
        stamped = []

        def persist(cases):
            stamped.extend(case.created_at for case in cases)
            return self._persist(cases)

        self._arrange(service, {existing_id: self._conversation(turns=2)})
        service.case_repo.create_many.side_effect = persist

        await service.import_cases_from_conversations(suite_id, [existing_id])

        assert stamped == [first_joined, first_joined]

    @pytest.mark.asyncio
    async def test_a_missing_suite_still_fails_the_whole_request(self):
        service = _service()
        service.suite_repo.get_by_id.return_value = None

        with pytest.raises(AppException):
            await service.import_cases_from_conversations(uuid4(), [uuid4()])

        service.conversation_repo.fetch_conversation_by_id.assert_not_awaited()


def _suite(name, suite_id=None, description=None):
    return SimpleNamespace(
        id=suite_id or uuid4(), name=name, description=description
    )


class TestListSuitesForConversation:
    """Answering "which datasets hold this conversation" from a conversation."""

    @pytest.mark.asyncio
    async def test_lists_every_dataset_including_ones_without_the_conversation(self):
        service = _service()
        holder, other = _suite("Refunds"), _suite("Billing")
        service.suite_repo.get_all.return_value = [holder, other]
        service.case_repo.get_conversation_membership.return_value = [
            (holder.id, 3, datetime(2026, 2, 1))
        ]

        entries = await service.list_suites_for_conversation(uuid4())

        by_id = {entry.suite_id: entry for entry in entries}
        assert by_id[holder.id].turns == 3
        assert by_id[holder.id].added_at == datetime(2026, 2, 1)
        assert by_id[other.id].turns == 0
        assert by_id[other.id].added_at is None

    @pytest.mark.asyncio
    async def test_orders_datasets_by_name_ignoring_case(self):
        service = _service()
        service.suite_repo.get_all.return_value = [
            _suite("zeta"),
            _suite("Alpha"),
            _suite("beta"),
        ]
        service.case_repo.get_conversation_membership.return_value = []

        entries = await service.list_suites_for_conversation(uuid4())

        assert [entry.name for entry in entries] == ["Alpha", "beta", "zeta"]

    @pytest.mark.asyncio
    async def test_carries_the_description_through(self):
        service = _service()
        service.suite_repo.get_all.return_value = [
            _suite("Refunds", description="Angry customers")
        ]
        service.case_repo.get_conversation_membership.return_value = []

        entries = await service.list_suites_for_conversation(uuid4())

        assert entries[0].description == "Angry customers"

    @pytest.mark.asyncio
    async def test_no_datasets_is_an_empty_list_not_an_error(self):
        service = _service()
        service.suite_repo.get_all.return_value = []
        service.case_repo.get_conversation_membership.return_value = []

        assert await service.list_suites_for_conversation(uuid4()) == []


class TestAddConversationToSuites:
    """Adding one conversation to several datasets from a conversation surface."""

    def _conversation(self, turns=2):
        messages = []
        for turn in range(turns):
            messages.append(_message(f"q{turn}", "customer", turn * 2))
            messages.append(_message(f"a{turn}", "agent", turn * 2 + 1))
        return SimpleNamespace(messages=messages)

    def _persist(self, cases):
        now = datetime(2026, 1, 1)
        for case in cases:
            case.id = uuid4()
            case.created_at = now
            case.updated_at = now
        return cases

    def _arrange(self, service, conversation, existing_by_suite=None):
        """Wire the repos so every suite exists and holds what the test says."""
        existing_by_suite = existing_by_suite or {}
        service.conversation_repo.fetch_conversation_by_id.return_value = conversation
        service.suite_repo.get_by_id.side_effect = (
            lambda suite_id: SimpleNamespace(id=suite_id)
        )
        service.case_repo.get_all_for_suite.side_effect = (
            lambda suite_id: existing_by_suite.get(suite_id, [])
        )
        service.case_repo.create_many.side_effect = self._persist

    @pytest.mark.asyncio
    async def test_adds_the_conversation_to_every_selected_dataset(self):
        service = _service()
        conversation_id, first, second = uuid4(), uuid4(), uuid4()
        self._arrange(service, self._conversation(turns=2))

        result = await service.add_conversation_to_suites(
            conversation_id, [first, second]
        )

        assert result.imported == 2
        assert result.replaced == 0
        assert result.failed == 0
        assert [entry.suite_id for entry in result.results] == [first, second]
        assert all(entry.turns == 2 for entry in result.results)

    @pytest.mark.asyncio
    async def test_a_dataset_that_already_holds_it_is_reported_as_replaced(self):
        service = _service()
        conversation_id, holder, fresh = uuid4(), uuid4(), uuid4()
        self._arrange(
            service,
            self._conversation(turns=2),
            existing_by_suite={
                holder: [
                    _case(
                        conversation_id=conversation_id,
                        turn_index=0,
                        created_at=datetime(2025, 5, 1),
                    )
                ]
            },
        )

        result = await service.add_conversation_to_suites(
            conversation_id, [holder, fresh]
        )

        statuses = {entry.suite_id: entry.status for entry in result.results}
        assert statuses[holder] == "replaced"
        assert statuses[fresh] == "imported"
        assert result.imported == 1
        assert result.replaced == 1

    @pytest.mark.asyncio
    async def test_re_import_refreshes_that_datasets_turns_only(self):
        service = _service()
        conversation_id, holder = uuid4(), uuid4()
        self._arrange(
            service,
            self._conversation(turns=2),
            existing_by_suite={
                holder: [_case(conversation_id=conversation_id, turn_index=0)]
            },
        )

        await service.add_conversation_to_suites(conversation_id, [holder])

        service.case_repo.soft_delete_for_conversation.assert_awaited_once_with(
            holder, conversation_id, commit=False
        )
        service.case_repo.soft_delete_all_for_suite.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_the_same_dataset_picked_twice_is_one_add(self):
        service = _service()
        conversation_id, suite_id = uuid4(), uuid4()
        self._arrange(service, self._conversation(turns=1))

        result = await service.add_conversation_to_suites(
            conversation_id, [suite_id, suite_id]
        )

        assert len(result.results) == 1
        assert result.imported == 1

    @pytest.mark.asyncio
    async def test_a_missing_dataset_fails_alone(self):
        service = _service()
        conversation_id, missing, good = uuid4(), uuid4(), uuid4()
        self._arrange(service, self._conversation(turns=2))
        service.suite_repo.get_by_id.side_effect = (
            lambda suite_id: None if suite_id == missing else SimpleNamespace(id=suite_id)
        )

        result = await service.add_conversation_to_suites(
            conversation_id, [missing, good]
        )

        assert result.failed == 1
        assert result.imported == 1
        failure = next(e for e in result.results if e.suite_id == missing)
        assert failure.status == "failed"
        assert failure.detail == "Dataset not found."
        assert failure.turns == 0

    @pytest.mark.asyncio
    async def test_a_missing_conversation_fails_before_any_dataset_is_touched(self):
        service = _service()
        service.conversation_repo.fetch_conversation_by_id.return_value = None

        with pytest.raises(AppException) as excinfo:
            await service.add_conversation_to_suites(uuid4(), [uuid4()])

        assert excinfo.value.status_code == 404
        service.suite_repo.get_by_id.assert_not_awaited()
        service.case_repo.create_many.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_a_conversation_with_no_turns_fails_before_any_dataset_is_touched(self):
        service = _service()
        service.conversation_repo.fetch_conversation_by_id.return_value = (
            SimpleNamespace(messages=[_message("hi?", "customer", 0)])
        )

        with pytest.raises(AppException) as excinfo:
            await service.add_conversation_to_suites(uuid4(), [uuid4()])

        assert excinfo.value.status_code == 400
        service.suite_repo.get_by_id.assert_not_awaited()
        service.case_repo.create_many.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_the_conversation_is_read_once_per_dataset_but_validated_first(self):
        service = _service()
        conversation_id = uuid4()
        self._arrange(service, self._conversation(turns=1))

        await service.add_conversation_to_suites(
            conversation_id, [uuid4(), uuid4()]
        )

        # One validating read plus one per dataset, all for the same conversation.
        assert service.conversation_repo.fetch_conversation_by_id.await_count == 3
