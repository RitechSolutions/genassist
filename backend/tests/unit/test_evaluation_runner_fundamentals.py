"""Runner fundamentals: turn inputs carry forward, runs report progress and keep their
configuration, failed turns keep a trace, and evaluation threads leave no memory behind."""
import asyncio
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.config.settings import settings
from app.modules.workflow.agents.memory import ConversationMemory
from app.modules.workflow.engine.nodes.workflow_executor_node import WorkflowExecutorNode
from app.modules.workflow.engine.workflow_engine import WorkflowEngine
from app.modules.workflow.engine.workflow_state import WorkflowState
from app.schemas.test_suite import TestRunCreate
from app.services.test_suite import (
    ResultStatus,
    TestSuiteService as EvalService,
    _carry_forward,
    _run_config_snapshot,
    _stateful_inputs,
    _stateful_values,
)
from app.tasks.test_suite_tasks import _execute_test_suite_run_async, _run_config


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


def _case(conversation_id, turn_index, input_data, expected=None):
    now = datetime(2026, 1, 1)
    return SimpleNamespace(
        id=uuid4(),
        suite_id=uuid4(),
        source_conversation_id=conversation_id,
        turn_index=turn_index,
        input_data=input_data,
        expected_output=expected,
        tags=[],
        weight=None,
        created_at=now,
        updated_at=now,
    )


def _run(techniques=("no_errors",)):
    return SimpleNamespace(id=uuid4(), techniques=list(techniques), status="queued", summary_metrics=None)


async def _execute(service, cases, *, engine, run=None, use_memory=True, suite_defaults=None, nodes=()):
    service.case_repo.get_all_for_suite.return_value = cases
    created = []
    service.result_repo.create = AsyncMock(side_effect=created.append)
    run = run or _run()
    with patch("app.services.test_suite.WorkflowEngine", return_value=engine):
        await service._execute_run(
            SimpleNamespace(id=uuid4(), default_input_metadata=suite_defaults),
            SimpleNamespace(id=uuid4(), nodes=list(nodes), edges=[], agent_id=None),
            run,
            run_input_metadata={"use_memory": True} if use_memory else None,
        )
    return created, run


def _mock_engine(side_effect=None):
    engine = MagicMock()
    engine.workflow_id = str(uuid4())
    engine.execute_from_node = AsyncMock(
        side_effect=side_effect
        or (lambda **_: SimpleNamespace(output="out", format_state_as_response=lambda: {}))
    )
    return engine


class TestCarryForward:
    def test_conversation_inputs_carry_and_per_message_inputs_do_not(self):
        carried = {}
        _carry_forward(
            carried,
            {"message": "hi", "region": "uk", "attachments": [1], "audio_data": "b64", "thread_id": "t"},
        )
        assert carried == {"region": "uk"}

    def test_an_explicit_null_drops_a_carried_input(self):
        carried = {"region": "uk", "mode": "refund"}
        _carry_forward(carried, {"message": "hi", "region": None})
        assert carried == {"mode": "refund"}

    @pytest.mark.asyncio
    async def test_later_turns_receive_earlier_inputs_within_their_conversation_only(self):
        first, second = uuid4(), uuid4()
        cases = [
            _case(first, 0, {"message": "A1", "region": "uk", "mode": "standard"}),
            _case(first, 1, {"message": "A2"}),
            _case(first, 2, {"message": "A3", "mode": "refund", "region": None}),
            _case(first, 3, {"message": "A4"}),
            _case(second, 0, {"message": "B1"}),
        ]
        engine = _mock_engine()

        await _execute(_service(), cases, engine=engine, suite_defaults={"region": "default", "tier": "gold"})

        inputs = [call.kwargs["input_data"] for call in engine.execute_from_node.call_args_list]
        drop = {"thread_id"}
        seen = [{k: v for k, v in data.items() if k not in drop} for data in inputs]
        assert seen == [
            {"message": "A1", "region": "uk", "mode": "standard", "tier": "gold"},
            {"message": "A2", "region": "uk", "mode": "standard", "tier": "gold"},
            # A null falls back to the dataset default, on its own turn and the ones after.
            {"message": "A3", "region": "default", "mode": "refund", "tier": "gold"},
            {"message": "A4", "region": "default", "mode": "refund", "tier": "gold"},
            {"message": "B1", "region": "default", "tier": "gold"},
        ]

    @pytest.mark.asyncio
    async def test_a_form_answer_belongs_to_its_own_turn(self):
        """A carried answer would silently fill the next human-in-the-loop form."""
        conversation = uuid4()
        cases = [
            _case(conversation, 0, {"message": "A1", "approval": "yes", "region": "uk"}),
            _case(conversation, 1, {"message": "A2"}),
        ]
        engine = _mock_engine()
        nodes = [{"id": "hil", "type": "humanInTheLoopNode", "data": {"form_fields": [{"name": "approval"}]}}]

        await _execute(_service(), cases, engine=engine, nodes=nodes)

        first, second = (call.kwargs["input_data"] for call in engine.execute_from_node.call_args_list)
        assert first["approval"] == "yes"
        assert "approval" not in second
        assert second["region"] == "uk"

    @pytest.mark.asyncio
    async def test_inputs_carry_without_memory_too(self):
        conversation = uuid4()
        cases = [_case(conversation, 0, {"message": "A1", "region": "uk"}), _case(conversation, 1, {"message": "A2"})]
        engine = _mock_engine()

        await _execute(_service(), cases, engine=engine, use_memory=False)

        assert engine.execute_from_node.call_args_list[1].kwargs["input_data"]["region"] == "uk"


class TestProgress:
    @pytest.mark.asyncio
    async def test_turns_publish_progress_and_conversations_commit_it(self):
        """Results still commit per conversation; turn progress goes out in its own transaction."""
        service = _service()
        events = []
        run = _run()

        async def commit():
            events.append(("commit", dict(run.progress) if getattr(run, "progress", None) else None))

        async def publish(run_id, progress):
            events.append(("publish", progress))

        service.run_repo.db.commit = AsyncMock(side_effect=commit)
        service.run_repo.publish_progress = AsyncMock(side_effect=publish)
        conversation = uuid4()
        cases = [_case(conversation, 0, {"message": "A1"}), _case(conversation, 1, {"message": "A2"})]

        await _execute(service, cases, engine=_mock_engine(), run=run)

        progress = lambda conversations, turns: {
            "conversations_done": conversations, "conversations_total": 1, "turns_done": turns, "turns_total": 2,
        }
        assert events == [
            ("commit", None),
            ("commit", progress(0, 0)),
            ("publish", progress(0, 1)),
            ("commit", progress(1, 2)),
        ]

    @pytest.mark.asyncio
    async def test_a_progress_write_that_fails_does_not_stop_the_run(self):
        service = _service()
        service.run_repo.publish_progress = AsyncMock(side_effect=OSError("db busy"))
        conversation = uuid4()
        cases = [_case(conversation, 0, {"message": "A1"}), _case(conversation, 1, {"message": "A2"})]

        _, run = await _execute(service, cases, engine=_mock_engine())

        assert run.status == "completed"
        assert run.progress["turns_done"] == 2

    @pytest.mark.asyncio
    async def test_skipped_and_failed_turns_count_as_done(self):
        conversation = uuid4()
        cases = [_case(conversation, 0, {"message": "A1"}), _case(conversation, 1, {"message": "A2"})]
        engine = _mock_engine(side_effect=RuntimeError("boom"))

        _, run = await _execute(_service(), cases, engine=engine)

        assert run.progress["turns_done"] == 2
        assert run.progress["conversations_done"] == 1


class TestConfigSnapshot:
    def test_the_snapshot_keeps_the_run_configuration_and_its_memory_setting(self):
        data = TestRunCreate(
            techniques=["contains"],
            technique_configs={"contains": {}},
            input_metadata={"use_memory": True, "region": "uk"},
        )
        # Techniques live on the run row itself, so the snapshot does not repeat them.
        assert _run_config_snapshot(data) == {
            "technique_configs": {"contains": {}},
            "input_metadata": {"use_memory": True, "region": "uk"},
        }

    def test_a_run_without_settings_snapshots_none(self):
        snapshot = _run_config_snapshot(TestRunCreate(techniques=["contains"]))
        assert snapshot == {"technique_configs": None, "input_metadata": None}

    @pytest.mark.asyncio
    async def test_create_run_stores_the_snapshot(self):
        service = _service()
        service.suite_repo.get_by_id.return_value = SimpleNamespace(id=uuid4(), workflow_id=uuid4())
        service.workflow_service.get_by_id.return_value = SimpleNamespace(id=uuid4())
        stored = []

        async def create(model):
            stored.append(model)
            now = datetime(2026, 1, 1)
            return SimpleNamespace(
                id=uuid4(), suite_id=model.suite_id, workflow_id=model.workflow_id, status=model.status,
                techniques=model.techniques, summary_metrics=None, progress=None, created_at=now, updated_at=now,
            )

        service.run_repo.create = AsyncMock(side_effect=create)
        data = TestRunCreate(techniques=["contains"], input_metadata={"use_memory": True})

        await service.create_run(uuid4(), data)

        assert stored[0].config_snapshot == _run_config_snapshot(data)

    def test_the_task_prefers_the_snapshot(self):
        run = SimpleNamespace(config_snapshot={"input_metadata": {"a": 1}, "technique_configs": {"b": {}}})
        assert _run_config(run, {"old": 1}, {"old": {}}) == ({"a": 1}, {"b": {}})

    def test_runs_queued_before_snapshots_use_the_task_arguments(self):
        run = SimpleNamespace(config_snapshot=None)
        assert _run_config(run, {"old": 1}, {"old": {}}) == ({"old": 1}, {"old": {}})

    @pytest.mark.asyncio
    async def test_the_task_executes_with_the_snapshot(self):
        run = SimpleNamespace(
            id=uuid4(), status="queued", summary_metrics=None, suite_id=uuid4(), workflow_id=uuid4(),
            config_snapshot={"input_metadata": {"use_memory": True}, "technique_configs": {"contains": {}}},
        )
        service = MagicMock()
        service.run_repo.get_by_id = AsyncMock(return_value=run)
        service.suite_repo.get_by_id = AsyncMock(return_value=SimpleNamespace(id=run.suite_id))
        service.workflow_service.get_by_id = AsyncMock(return_value=SimpleNamespace(id=run.workflow_id))
        service._execute_run = AsyncMock()

        with patch("app.dependencies.injector.injector") as injector:
            injector.get.return_value = service
            await _execute_test_suite_run_async(uuid4(), None, None)

        kwargs = service._execute_run.await_args.kwargs
        assert kwargs["run_input_metadata"] == {"use_memory": True}
        assert kwargs["technique_configs"] == {"contains": {}}


class TestFailedTurnTrace:
    @staticmethod
    def _partial_state():
        return SimpleNamespace(
            format_state_as_response=lambda: {"state": {"nodeExecutionStatus": {"n1": {"status": "error"}}}}
        )

    @pytest.mark.asyncio
    async def test_a_turn_that_raises_keeps_how_far_it_got(self):
        partial = self._partial_state()

        async def execute(**kwargs):
            kwargs["state_sink"].append(partial)
            raise RuntimeError("boom")

        created, _ = await _execute(_service(), [_case(uuid4(), 0, {"message": "A1"})], engine=_mock_engine(execute))

        (result,) = created
        assert result.status == ResultStatus.EXECUTION_FAILED
        assert result.execution_trace["state"]["nodeExecutionStatus"] == {"n1": {"status": "error"}}

    @pytest.mark.asyncio
    async def test_a_turn_that_times_out_keeps_how_far_it_got(self):
        partial = self._partial_state()

        async def execute(**kwargs):
            kwargs["state_sink"].append(partial)
            await asyncio.sleep(5)

        with patch("app.services.test_suite.CASE_EXECUTION_TIMEOUT_SECONDS", 0.01):
            created, _ = await _execute(
                _service(), [_case(uuid4(), 0, {"message": "A1"})], engine=_mock_engine(execute)
            )

        (result,) = created
        assert result.error.startswith("Execution timed out")
        assert result.execution_trace["state"]["nodeExecutionStatus"] == {"n1": {"status": "error"}}

    @pytest.mark.asyncio
    async def test_a_turn_that_never_started_has_no_trace(self):
        engine = _mock_engine(side_effect=RuntimeError("boom"))

        created, _ = await _execute(_service(), [_case(uuid4(), 0, {"message": "A1"})], engine=engine)

        assert created[0].execution_trace is None


class TestStatefulValues:
    NODES = [
        {
            "id": "start",
            "type": "chatInputNode",
            "data": {
                "inputSchema": {
                    "message": {"type": "string"},
                    "region": {"type": "string", "stateful": True},
                    "mode": {"type": "string", "stateful": True},
                }
            },
        },
        {"id": "other", "type": "templateNode", "data": {}},
    ]

    def test_only_chat_input_parameters_marked_stateful_are_tracked(self):
        assert _stateful_inputs(self.NODES) == {"start": ["region", "mode"]}

    @pytest.mark.asyncio
    async def test_set_state_writes_win_over_the_values_the_turn_started_with(self):
        trace = {"state": {"nodeExecutionStatus": {"start": {"output": {"message": "hi", "region": "uk", "mode": "standard"}}}}}
        memory = SimpleNamespace(get_all_stateful_values=AsyncMock(return_value={"mode": "refund"}))
        state = SimpleNamespace(get_memory=lambda: memory)

        values = await _stateful_values(state, trace, _stateful_inputs(self.NODES))

        assert values == {"region": "uk", "mode": "refund"}

    @pytest.mark.asyncio
    async def test_unreadable_memory_falls_back_to_the_values_the_turn_used(self):
        trace = {"state": {"nodeExecutionStatus": {"start": {"output": {"region": "uk"}}}}}
        memory = SimpleNamespace(get_all_stateful_values=AsyncMock(side_effect=OSError("redis down")))

        values = await _stateful_values(SimpleNamespace(get_memory=lambda: memory), trace, {"start": ["region"]})

        assert values == {"region": "uk"}


class TestForgetThread:
    @pytest.fixture(autouse=True)
    def isolated_instances(self, monkeypatch):
        monkeypatch.setattr(ConversationMemory, "_instances", {})

    @pytest.mark.asyncio
    async def test_stored_memory_is_deleted_and_the_cache_entry_dropped(self):
        stored = SimpleNamespace(delete_conversation=AsyncMock())
        ConversationMemory._instances["t1"] = stored

        await ConversationMemory.forget("t1")

        stored.delete_conversation.assert_awaited_once()
        assert "t1" not in ConversationMemory._instances

    @pytest.mark.asyncio
    async def test_a_tracked_threads_sub_agent_threads_go_with_it(self, monkeypatch):
        monkeypatch.setattr(ConversationMemory, "_children", {})
        made = {}

        def new_instance(thread_id):
            made[thread_id] = SimpleNamespace(delete_conversation=AsyncMock())
            return made[thread_id]

        monkeypatch.setattr(ConversationMemory, "_new_instance", new_instance)
        ConversationMemory.track_children("root")
        ConversationMemory.get_instance("root")
        ConversationMemory.get_instance("root:sub:n1:inv1")
        # The orchestrator drops a finished sub-agent from the cache; its stored data stays.
        ConversationMemory.discard("root:sub:n1:inv1")

        await ConversationMemory.forget("root")

        made["root"].delete_conversation.assert_awaited_once()
        assert made["root:sub:n1:inv1"].delete_conversation.await_count == 1
        assert ConversationMemory._children == {}

    @pytest.mark.asyncio
    async def test_live_threads_are_never_tracked(self, monkeypatch):
        monkeypatch.setattr(ConversationMemory, "_children", {})
        monkeypatch.setattr(ConversationMemory, "_new_instance", lambda _tid: SimpleNamespace())

        ConversationMemory.get_instance("live:sub:n1:inv1")

        assert ConversationMemory._children == {}

    @pytest.mark.asyncio
    async def test_a_failed_parent_delete_still_deletes_the_children(self, monkeypatch):
        monkeypatch.setattr(ConversationMemory, "_children", {"root": {"root:sub:a"}})
        child = SimpleNamespace(delete_conversation=AsyncMock())
        ConversationMemory._instances["root"] = SimpleNamespace(
            delete_conversation=AsyncMock(side_effect=OSError("redis timeout"))
        )
        ConversationMemory._instances["root:sub:a"] = child

        with pytest.raises(OSError):
            await ConversationMemory.forget("root")

        child.delete_conversation.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_a_thread_nothing_created_touches_no_storage(self):
        await ConversationMemory.forget("never-used")

        assert ConversationMemory._instances == {}

    @pytest.mark.asyncio
    async def test_an_adopted_thread_and_its_sub_agent_threads_go_with_it(self, monkeypatch):
        monkeypatch.setattr(ConversationMemory, "_children", {})
        monkeypatch.setattr(ConversationMemory, "_owners", {})
        made = {}

        def new_instance(thread_id):
            made[thread_id] = SimpleNamespace(delete_conversation=AsyncMock())
            return made[thread_id]

        monkeypatch.setattr(ConversationMemory, "_new_instance", new_instance)
        ConversationMemory.track_children("root")
        ConversationMemory.get_instance("root")
        # A sub-workflow started by one of the thread's sub-agents, with a sub-agent of its own.
        ConversationMemory.adopt("root:sub:n1:inv1", "child-wf")
        ConversationMemory.get_instance("child-wf")
        ConversationMemory.get_instance("child-wf:sub:n2:inv1")

        await ConversationMemory.forget("root")

        for thread_id in ("root", "child-wf", "child-wf:sub:n2:inv1"):
            made[thread_id].delete_conversation.assert_awaited_once()
        assert ConversationMemory._children == {}
        assert ConversationMemory._owners == {}

    def test_live_threads_adopt_nothing(self, monkeypatch):
        monkeypatch.setattr(ConversationMemory, "_children", {})
        monkeypatch.setattr(ConversationMemory, "_owners", {})

        ConversationMemory.adopt("live", "child-wf")

        assert ConversationMemory._children == {}
        assert ConversationMemory._owners == {}

    def test_a_thread_id_that_is_not_a_string_still_gets_its_memory(self, monkeypatch):
        monkeypatch.setattr(ConversationMemory, "_children", {"root": set()})
        monkeypatch.setattr(ConversationMemory, "_new_instance", lambda _tid: SimpleNamespace())

        assert ConversationMemory.get_instance(12345) is ConversationMemory._instances[12345]

    @pytest.mark.asyncio
    async def test_a_sub_workflow_without_a_thread_id_runs_on_a_thread_the_evaluation_adopts(self, monkeypatch):
        monkeypatch.setattr(settings, "REDIS_FOR_CONVERSATION", False)
        monkeypatch.setattr(ConversationMemory, "_children", {})
        monkeypatch.setattr(ConversationMemory, "_owners", {})
        ConversationMemory.track_children("eval-thread")
        parent = WorkflowState(workflow={"config": {"id": "parent"}, "nodes": [], "edges": []}, thread_id="eval-thread")
        child_workflow = SimpleNamespace(id=uuid4(), name="Child", nodes=[], edges=[])
        workflows = SimpleNamespace(get_by_id=AsyncMock(return_value=child_workflow))
        threads = []

        async def execute(_engine, *, thread_id, **_kwargs):
            threads.append(thread_id)
            return WorkflowState(workflow={"config": {"id": "child"}, "nodes": [], "edges": []}, thread_id=thread_id)

        with patch("app.dependencies.injector.injector", SimpleNamespace(get=lambda _cls: workflows)), patch.object(
            WorkflowEngine, "execute_from_node", execute
        ):
            for params in ({}, {"threadId": "shared-thread"}):
                node = WorkflowExecutorNode("exec", {"type": "workflowExecutorNode", "data": {}}, parent)
                await node.process({"workflowId": str(child_workflow.id), "inputParameters": params})

        own_thread, shared_thread = threads
        assert own_thread in ConversationMemory._children["eval-thread"]
        # A configured thread may be shared with live conversations, so it is never adopted.
        assert shared_thread not in ConversationMemory._children["eval-thread"]


class TestEngineStateSink:
    @pytest.mark.asyncio
    async def test_the_state_reaches_the_caller_even_when_the_run_raises(self):
        engine = WorkflowEngine({"id": str(uuid4()), "nodes": [{"id": "n1", "type": "inputNode"}], "edges": []})
        sink = []
        with patch.object(
            WorkflowEngine, "_execute_from_node_recursive", new=AsyncMock(side_effect=RuntimeError("boom"))
        ):
            with pytest.raises(RuntimeError):
                await engine.execute_from_node(input_data={"message": "hi"}, persist=False, state_sink=sink)

        assert len(sink) == 1
        assert sink[0].status == "failed"


class TestEndToEnd:
    """A real workflow: Chat Input (region required, mode stateful) -> Set State -> Template."""

    WORKFLOW_NODES = [
        {
            "id": "start",
            "type": "chatInputNode",
            "data": {
                "name": "Start",
                "inputSchema": {
                    "message": {"type": "string", "required": True},
                    "region": {"type": "string", "required": True},
                    "mode": {"type": "string", "stateful": True, "defaultValue": "standard"},
                },
            },
        },
        {"id": "set", "type": "setStateNode", "data": {"name": "Set mode", "states": [{"key": "mode", "value": "refund"}]}},
        {"id": "reply", "type": "templateNode", "data": {"name": "Reply", "template": "Mode is {{session.mode}}"}},
    ]
    WORKFLOW_EDGES = [
        {"source": "start", "target": "set", "sourceHandle": "output", "targetHandle": "input"},
        {"source": "set", "target": "reply", "sourceHandle": "output", "targetHandle": "input"},
    ]

    @pytest.mark.asyncio
    async def test_a_conversation_replays_with_carried_inputs_and_set_state_precedence(self, monkeypatch):
        monkeypatch.setattr(settings, "REDIS_FOR_CONVERSATION", False)
        monkeypatch.setattr(ConversationMemory, "_instances", {})
        monkeypatch.setattr(WorkflowEngine, "_record_llm_usage_safe", AsyncMock())

        refund, no_region = uuid4(), uuid4()
        cases = [
            _case(refund, 0, {"message": "I want my money back", "region": "uk", "mode": "standard"}),
            # Region comes from turn 1; mode "standard" is carried too, but Set State wrote "refund".
            _case(refund, 1, {"message": "Yes please"}, expected={"value": "refund"}),
            _case(no_region, 0, {"message": "Hello"}),
        ]
        service = _service()
        service.case_repo.get_all_for_suite.return_value = cases
        created = []
        service.result_repo.create = AsyncMock(side_effect=created.append)
        run = _run(techniques=["contains"])

        await service._execute_run(
            SimpleNamespace(id=uuid4(), default_input_metadata=None),
            SimpleNamespace(id=uuid4(), nodes=self.WORKFLOW_NODES, edges=self.WORKFLOW_EDGES, agent_id=None),
            run,
            run_input_metadata={"use_memory": True},
        )

        first, second, unanswered = (next(r for r in created if r.case_id == case.id) for case in cases)
        start_output = lambda result: result.execution_trace["state"]["nodeExecutionStatus"]["start"]["output"]

        assert first.status == ResultStatus.SCORED
        assert first.metrics["contains"]["not_evaluated"] is True
        assert start_output(first)["mode"] == "standard"
        assert first.execution_trace["stateful_values"] == {"mode": "refund"}

        assert second.status == ResultStatus.SCORED
        assert start_output(second)["region"] == "uk"
        assert start_output(second)["mode"] == "refund"
        assert second.metrics["contains"]["passed"] is True

        # Nothing carries into another conversation, so its Chat Input rejects the missing region.
        (failed_node,) = unanswered.execution_trace["failed_nodes"]
        assert failed_node["node_id"] == "start"
        assert "region" in failed_node["error"]

        assert run.status == "completed"
        assert run.progress == {"conversations_done": 2, "conversations_total": 2, "turns_done": 3, "turns_total": 3}
        # Only the turn with an expected reply is graded; it passed.
        assert run.summary_metrics["contains"]["evaluated"] == 1
        assert run.summary_metrics["contains"]["not_evaluated"] == 2
        assert run.summary_metrics["contains"]["accuracy"] == 1.0
        assert ConversationMemory._instances == {}


class TestStoredRowsMaskHiddenInputs:
    NODES = [
        {
            "id": "start",
            "type": "chatInputNode",
            "data": {"inputSchema": {"message": {"type": "string"}, "api_token": {"type": "string", "hidden": True}}},
        }
    ]
    SECRET = "tok-secret-123456"

    def _state(self):
        trace = {
            "state": {"nodeExecutionStatus": {"start": {"type": "chatInputNode", "output": {"api_token": self.SECRET}}}},
            "output": f"Your token is {self.SECRET}",
        }
        return SimpleNamespace(
            output=f"Your token is {self.SECRET}", format_state_as_response=lambda: dict(trace)
        )

    @pytest.mark.asyncio
    async def test_a_hidden_value_is_graded_for_real_but_stored_masked(self):
        service = _service()
        case = _case(uuid4(), 0, {"message": "token?", "api_token": self.SECRET}, expected={"value": self.SECRET})
        engine = _mock_engine(side_effect=lambda **_: self._state())

        created, run = await _execute(
            service, [case], engine=engine, run=_run(techniques=["contains"]), nodes=self.NODES
        )

        (row,) = created
        assert row.metrics["contains"]["passed"] is True
        stored = str({"output": row.actual_output, "trace": row.execution_trace, "metrics": row.metrics})
        assert self.SECRET not in stored
        assert "[API_TOKEN]" in stored

    @pytest.mark.asyncio
    async def test_a_failed_turn_is_stored_masked_too(self):
        partial = self._state()

        async def execute(**kwargs):
            kwargs["state_sink"].append(partial)
            raise RuntimeError(f"bad token {self.SECRET}")

        created, _ = await _execute(
            _service(), [_case(uuid4(), 0, {"message": "x", "api_token": self.SECRET})],
            engine=_mock_engine(execute), nodes=self.NODES,
        )

        (row,) = created
        assert self.SECRET not in str(row.execution_trace) + row.error

    @pytest.mark.asyncio
    async def test_a_hidden_value_set_state_overwrites_is_stored_masked_too(self, monkeypatch):
        monkeypatch.setattr(settings, "REDIS_FOR_CONVERSATION", False)
        monkeypatch.setattr(ConversationMemory, "_instances", {})
        monkeypatch.setattr(WorkflowEngine, "_record_llm_usage_safe", AsyncMock())
        rotated = "tok-rotated-987654"
        nodes = [
            {**self.NODES[0], "data": {**self.NODES[0]["data"], "name": "Start"}},
            {"id": "set", "type": "setStateNode", "data": {"name": "Rotate", "states": [{"key": "api_token", "value": rotated}]}},
            {"id": "reply", "type": "templateNode", "data": {"name": "Reply", "template": "Token {{session.api_token}}"}},
        ]
        edges = [
            {"source": "start", "target": "set", "sourceHandle": "output", "targetHandle": "input"},
            {"source": "set", "target": "reply", "sourceHandle": "output", "targetHandle": "input"},
        ]
        service = _service()
        service.case_repo.get_all_for_suite.return_value = [_case(uuid4(), 0, {"message": "x", "api_token": self.SECRET})]
        created = []
        service.result_repo.create = AsyncMock(side_effect=created.append)

        await service._execute_run(
            SimpleNamespace(id=uuid4(), default_input_metadata=None),
            SimpleNamespace(id=uuid4(), nodes=nodes, edges=edges, agent_id=None),
            _run(),
            run_input_metadata={"use_memory": True},
        )

        (row,) = created
        assert row.execution_trace["output"] == "Token [API_TOKEN]"
        stored = str({"output": row.actual_output, "trace": row.execution_trace})
        assert rotated not in stored
        assert self.SECRET not in stored


class TestScoringFailureKeepsTrace:
    @pytest.mark.asyncio
    async def test_a_turn_that_ran_but_failed_scoring_keeps_its_trace(self):
        service = _service()
        service.evaluators = MagicMock()
        service.evaluators.evaluate = AsyncMock(side_effect=RuntimeError("judge down"))
        engine = _mock_engine(
            side_effect=lambda **_: SimpleNamespace(output="out", format_state_as_response=lambda: {"output": "out"})
        )

        created, _ = await _execute(service, [_case(uuid4(), 0, {"message": "A1"})], engine=engine)

        (row,) = created
        assert row.status == ResultStatus.SCORING_FAILED
        assert row.execution_trace["output"] == "out"
