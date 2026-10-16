"""Checks in a run: graded on what each turn did, stored one row each, masked, summarized by conversation."""
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage

from app.core.config.settings import settings
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.modules.workflow.agents.memory import ConversationMemory
from app.modules.workflow.engine.workflow_engine import WorkflowEngine
from app.modules.workflow.engine.workflow_state import RAW_TOOL_ARGUMENTS, WorkflowState
from app.schemas.test_suite import TestEvaluationCreate, TestEvaluationUpdate
from app.services.scenario_checks import Check, JudgeRequest, TurnRecord
from app.services.test_suite import TestSuiteService as EvalService
from app.services.tool_catalog import resolve_state_keys

NODES = [
    {
        "id": "start",
        "type": "chatInputNode",
        "data": {
            "name": "Start",
            "inputSchema": {
                "message": {"type": "string", "required": True},
                "region": {"type": "string", "required": True},
                "mode": {"type": "string", "stateful": True, "defaultValue": "standard"},
                "api_token": {"type": "string", "stateful": True, "hidden": True},
            },
        },
    },
    {"id": "set", "type": "setStateNode", "data": {"name": "Set mode", "states": [{"key": "mode", "value": "refund"}]}},
    {"id": "reply", "type": "templateNode", "data": {"name": "Reply", "template": "Mode is {{session.mode}}"}},
]
EDGES = [
    {"source": "start", "target": "set", "sourceHandle": "output", "targetHandle": "input"},
    {"source": "set", "target": "reply", "sourceHandle": "output", "targetHandle": "input"},
]
SECRET = "tok-secret-123456"


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


def _case(conversation_id, turn_index, input_data):
    now = datetime(2026, 1, 1)
    return SimpleNamespace(
        id=uuid4(), suite_id=uuid4(), source_conversation_id=conversation_id, turn_index=turn_index,
        input_data=input_data, expected_output=None, tags=[], weight=None, created_at=now, updated_at=now,
    )


def _run():
    return SimpleNamespace(id=uuid4(), techniques=["checks"], status="queued", summary_metrics=None)


def _rows(service):
    return [row for call in service.tool_rule_result_repo.create_many.await_args_list for row in call.args[0]]


async def _execute(service, cases, checks, *, nodes=NODES, edges=EDGES, engine=None):
    service.case_repo.get_all_for_suite.return_value = cases
    service.result_repo.create = AsyncMock()
    workflow = SimpleNamespace(id=uuid4(), nodes=nodes, edges=edges, agent_id=None)
    service.workflow_service.get_by_id = AsyncMock(return_value=workflow)
    run = _run()
    patcher = patch("app.services.test_suite.WorkflowEngine", return_value=engine) if engine else None
    if patcher:
        patcher.start()
    try:
        await service._execute_run(
            SimpleNamespace(id=uuid4(), default_input_metadata=None),
            workflow,
            run,
            run_input_metadata={"use_memory": True},
            technique_configs={"checks": {"checks": checks}},
        )
    finally:
        if patcher:
            patcher.stop()
    return run


@pytest.fixture
def in_memory(monkeypatch):
    monkeypatch.setattr(settings, "REDIS_FOR_CONVERSATION", False)
    monkeypatch.setattr(ConversationMemory, "_instances", {})
    monkeypatch.setattr(WorkflowEngine, "_record_llm_usage_safe", AsyncMock())


class TestChecksInARun:
    @pytest.mark.asyncio
    async def test_a_real_run_grades_each_check_and_masks_hidden_values(self, in_memory):
        refund, other = uuid4(), uuid4()
        first = _case(refund, 0, {"message": "I want my money back", "region": "uk", "api_token": SECRET})
        cases = [first, _case(refund, 1, {"message": "Yes please"}), _case(other, 0, {"message": "Hello", "region": "fr"})]
        checks = [
            {"id": "mentions", "kind": "reply_mentions", "text": "mode is refund"},
            {"id": "state", "kind": "state_equals", "key": "mode", "value": "refund", "level": "turn",
             "case_id": str(first.id)},
            {"id": "no-step", "kind": "step_runs", "step_name": "Set mode", "expect": "should_not",
             "level": "conversation", "conversation_id": str(refund)},
            {"id": "token", "kind": "state_equals", "key": "api_token", "value": SECRET,
             "level": "conversation", "conversation_id": str(refund)},
            {"id": "gone", "kind": "reply_mentions", "text": "x", "level": "turn", "case_id": str(uuid4())},
        ]
        service = _service()

        run = await _execute(service, cases, checks)

        rows = _rows(service)
        assert {row.technique for row in rows} == {"checks"}
        by_check = {}
        for row in rows:
            by_check.setdefault(row.rule_id, []).append(row)
        assert [row.status for row in by_check["mentions"]] == ["passed", "passed"]
        assert by_check["state"][0].status == "passed"
        assert by_check["state"][0].case_id == str(first.id)
        (no_step,) = by_check["no-step"]
        assert no_step.status == "failed"
        assert no_step.details["observed"] == "Turn 1: The step ran."
        assert no_step.details["rule_summary"] == 'The step "Set mode" should never run.'
        assert no_step.details["target"]["type"] == "conversation"
        assert by_check["token"][0].status == "passed"
        assert by_check["gone"][0].status == "not_evaluated"

        # The token is graded for real but never stored, not even inside the check itself.
        assert SECRET not in str([row.details for row in rows])
        assert "[API_TOKEN]" in str(by_check["token"][0].details)

        summary = run.summary_metrics["checks"]
        assert summary["conversations"] == {"total": 2, "passed": 1, "failed": 1, "not_evaluated": 0}
        assert summary["accuracy"] == 0.5
        assert summary["coverage"]["total"] == 6

    @pytest.mark.asyncio
    async def test_a_short_hidden_value_masks_texts_but_not_the_grading(self, in_memory):
        cases = [_case(uuid4(), 0, {"message": "Hello", "api_token": "no"})]
        checks = [
            {"id": "never", "kind": "reply_mentions", "text": "zebra", "expect": "should_not"},
            {"id": "gone", "kind": "reply_mentions", "text": "x", "level": "turn", "case_id": str(uuid4())},
        ]
        service = _service()

        run = await _execute(service, cases, checks)

        rows = {row.rule_id: row for row in _rows(service)}
        assert {key: row.status for key, row in rows.items()} == {"never": "passed", "gone": "not_evaluated"}
        assert rows["never"].details["expect"] == "should_not"
        assert rows["never"].details["rule"]["expect"] == "should_not"
        assert run.summary_metrics["checks"]["conversations"]["passed"] == 1

    @pytest.mark.asyncio
    async def test_a_crashed_turn_fails_its_conversation(self):
        conversation = uuid4()
        cases = [_case(conversation, 0, {"message": "Hi"}), _case(conversation, 1, {"message": "Then?"})]

        async def execute(**_kwargs):
            raise RuntimeError("boom")

        engine = MagicMock()
        engine.workflow_id = str(uuid4())
        engine.execute_from_node = AsyncMock(side_effect=execute)
        checks = [
            {"id": "first", "kind": "reply_mentions", "text": "x", "level": "turn", "case_id": str(cases[0].id)},
            {"id": "second", "kind": "reply_mentions", "text": "x", "level": "turn", "case_id": str(cases[1].id)},
        ]
        service = _service()

        run = await _execute(service, cases, checks, nodes=[], edges=[], engine=engine)

        first, second = sorted(_rows(service), key=lambda row: row.rule_id)
        assert first.status == "failed"
        assert first.details["observed"] == "The turn did not finish: Execution failed: boom"
        assert second.status == "not_evaluated"
        assert second.details["comment"] == "This turn did not run because an earlier turn failed."
        assert run.summary_metrics["checks"]["conversations"]["failed"] == 1

    @pytest.mark.asyncio
    async def test_a_turn_whose_result_cannot_be_read_says_so(self, in_memory, monkeypatch):
        async def unreadable(*_args, **_kwargs):
            raise RuntimeError("unreadable")

        monkeypatch.setattr("app.services.test_suite._stateful_values", unreadable)
        case = _case(uuid4(), 0, {"message": "Hi", "region": "uk"})
        service = _service()

        await _execute(service, [case], [
            {"id": "a", "kind": "reply_mentions", "text": "x", "level": "turn", "case_id": str(case.id)},
        ])

        (row,) = _rows(service)
        assert row.status == "not_evaluated"
        assert row.details["comment"] == "This turn ran, but its result could not be read."

    @pytest.mark.asyncio
    async def test_checks_are_not_graded_per_case(self, in_memory):
        service = _service()
        run = await _execute(service, [_case(uuid4(), 0, {"message": "Hi", "region": "uk"})],
                             [{"id": "a", "kind": "reply_mentions", "text": "mode"}])
        assert set(run.summary_metrics) == {"checks", "_totals"}


class TestJudgeInARun:
    @pytest.mark.asyncio
    async def test_the_grader_reads_one_reply_or_the_whole_conversation(self):
        sent = []

        async def ainvoke(messages):
            sent.append(messages)
            return AIMessage(content='{"score": 0.9, "reason": "Asked for the plate."}')

        provider = SimpleNamespace(get_model=AsyncMock(return_value=SimpleNamespace(ainvoke=ainvoke)))
        service = _service()
        service._flush_judge_usage = AsyncMock()
        turns = [
            TurnRecord(case_id="a1", conversation_key="a", turn_index=0, position=0, message="Hi", reply="Hello"),
            TurnRecord(case_id="a2", conversation_key="a", turn_index=1, position=1, message="Plate?", reply="AB12"),
        ]
        whole = Check(id="w", kind="reply_meets", rubric="Ask for the plate", expect="should_not")
        one = Check(id="o", kind="reply_meets", rubric="Greet", level="turn", case_id="a1")

        with patch("app.services.test_suite.injector", SimpleNamespace(get=lambda _cls: provider)):
            verdicts = await service._judge_checks(
                [JudgeRequest(whole, turns), JudgeRequest(one, turns[:1])],
                "provider-1",
                run=SimpleNamespace(id=uuid4()),
                workflow=SimpleNamespace(id=uuid4(), agent_id=None),
                provider_name_cache={},
                metering_state={"timed_out": False},
            )

        assert verdicts[("w", ("a1", "a2"))].score == 0.9
        assert verdicts[("o", ("a1",))].met
        whole_prompt = next(messages for messages in sent if "CONVERSATION" in messages[1].content)
        assert "At no point in the conversation should the assistant do this: Ask for the plate" in whole_prompt[0].content
        assert whole_prompt[1].content == "CONVERSATION:\nUSER: Hi\nASSISTANT: Hello\nUSER: Plate?\nASSISTANT: AB12"
        one_prompt = next(messages for messages in sent if "QUESTION" in messages[1].content)
        assert one_prompt[1].content == "QUESTION:\nHi\n\nANSWER:\nHello"
        provider.get_model.assert_awaited_once_with("provider-1")
        service._flush_judge_usage.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_an_unreachable_grader_leaves_the_checks_not_evaluated(self):
        provider = SimpleNamespace(get_model=AsyncMock(side_effect=RuntimeError("no provider")))
        service = _service()
        turn = TurnRecord(case_id="a1", conversation_key="a", turn_index=0, position=0, message="Hi", reply="Hello")
        with patch("app.services.test_suite.injector", SimpleNamespace(get=lambda _cls: provider)):
            verdicts = await service._judge_checks(
                [JudgeRequest(Check(id="w", kind="reply_meets", rubric="Greet"), [turn])],
                None,
                run=SimpleNamespace(id=uuid4()),
                workflow=SimpleNamespace(id=uuid4(), agent_id=None),
                provider_name_cache={},
                metering_state={"timed_out": False},
            )
        assert verdicts[("w", ("a1",))].error


class TestSavingAnEvaluation:
    @pytest.mark.asyncio
    async def test_an_evaluation_needs_something_to_grade(self):
        service = _service()
        with pytest.raises(AppException) as raised:
            await service.create_evaluation(TestEvaluationCreate(name="x", suite_id=uuid4(), techniques=[]))
        assert raised.value.error_key == ErrorKey.EVALUATION_TECHNIQUES_REQUIRED

        service.evaluation_repo.get_by_id.return_value = SimpleNamespace(
            suite_id=uuid4(), workflow_id=None, techniques=["contains"], technique_configs={}
        )
        with pytest.raises(AppException) as raised:
            await service.update_evaluation(uuid4(), TestEvaluationUpdate(techniques=[]))
        assert raised.value.error_key == ErrorKey.EVALUATION_TECHNIQUES_REQUIRED

        # Checks with no check grade nothing either, also when only the checks are emptied.
        with pytest.raises(AppException) as raised:
            await service.create_evaluation(TestEvaluationCreate(
                name="x", suite_id=uuid4(), techniques=["checks"], technique_configs={"checks": {"checks": []}},
            ))
        assert raised.value.error_key == ErrorKey.EVALUATION_TECHNIQUES_REQUIRED
        service.evaluation_repo.get_by_id.return_value = SimpleNamespace(
            suite_id=uuid4(), workflow_id=None, techniques=["checks"],
            technique_configs={"checks": {"checks": [{"id": "a", "kind": "reply_mentions", "text": "Hi"}]}},
        )
        with pytest.raises(AppException) as raised:
            await service.update_evaluation(uuid4(), TestEvaluationUpdate(technique_configs={"checks": {"checks": []}}))
        assert raised.value.error_key == ErrorKey.EVALUATION_TECHNIQUES_REQUIRED

    @pytest.mark.asyncio
    async def test_incomplete_checks_are_refused(self):
        service = _service()
        data = TestEvaluationCreate(
            name="x", suite_id=uuid4(), techniques=["checks"],
            technique_configs={"checks": {"checks": [{"id": "a", "kind": "reply_mentions", "level": "turn"}]}},
        )
        with pytest.raises(AppException) as raised:
            await service.create_evaluation(data)
        assert raised.value.error_key == ErrorKey.RULE_CONFIG_INVALID
        assert raised.value.status_code == 400

    @pytest.mark.asyncio
    async def test_complete_checks_are_saved(self):
        service = _service()
        service.evaluation_repo.create = AsyncMock(side_effect=lambda orm: SimpleNamespace(
            id=uuid4(), run_ids=[], created_at=datetime(2026, 1, 1), updated_at=datetime(2026, 1, 1),
            **{key: getattr(orm, key) for key in
               ("name", "description", "suite_id", "workflow_id", "techniques", "technique_configs", "input_metadata")},
        ))
        config = {"checks": [{"id": "a", "kind": "reply_mentions", "text": "Hi"}]}
        created = await service.create_evaluation(TestEvaluationCreate(
            name="x", suite_id=uuid4(), techniques=["checks"], technique_configs={"checks": config},
        ))
        assert created.technique_configs == {"checks": config}


class TestCatalogAndArguments:
    def test_the_catalog_lists_remembered_values(self):
        keys = resolve_state_keys({"nodes": NODES}, workflow_path=["Parent"])
        assert [(key["key"], key["source"], key["node_label"]) for key in keys] == [
            ("mode", "chat_input", "Start"),
            ("api_token", "chat_input", "Start"),
            ("mode", "set_state", "Set mode"),
        ]
        assert keys[0]["workflow_path"] == ["Parent"]

    def test_real_tool_arguments_are_kept_only_while_an_evaluation_asks(self, monkeypatch):
        monkeypatch.setattr(settings, "REDIS_FOR_CONVERSATION", False)
        monkeypatch.setattr(ConversationMemory, "_instances", {})
        state = WorkflowState(workflow={"config": {"id": "wf"}, "nodes": [], "edges": []}, thread_id="t")

        state.add_tool_event(agent_id="a", tool_id="t1", tool_name="lookup", arguments={"email": "ana@example.com"},
                             result=None, status="succeeded")
        captured = {}
        token = RAW_TOOL_ARGUMENTS.set(captured)
        try:
            state.add_tool_event(agent_id="a", tool_id="t1", tool_name="lookup",
                                 arguments={"email": "ana@example.com"}, result=None, status="succeeded")
        finally:
            RAW_TOOL_ARGUMENTS.reset(token)

        first, second = state.tool_events
        assert "ana@example.com" not in str(first["arguments"]) + str(second["arguments"])
        assert captured == {second["event_id"]: {"email": "ana@example.com"}}

    def test_one_long_argument_does_not_hide_the_others(self, monkeypatch):
        monkeypatch.setattr(settings, "REDIS_FOR_CONVERSATION", False)
        monkeypatch.setattr(ConversationMemory, "_instances", {})
        state = WorkflowState(workflow={"config": {"id": "wf"}, "nodes": [], "edges": []}, thread_id="t")
        captured = {}
        token = RAW_TOOL_ARGUMENTS.set(captured)
        try:
            state.add_tool_event(agent_id="a", tool_id="t1", tool_name="save_region",
                                 arguments={"region": "uk", "notes": "x" * 9000}, result=None, status="succeeded")
        finally:
            RAW_TOOL_ARGUMENTS.reset(token)

        (arguments,) = captured.values()
        assert arguments["region"] == "uk"
        assert arguments["notes"]["_truncated"] is True

    def test_credentials_stay_hidden_from_checks(self, monkeypatch):
        monkeypatch.setattr(settings, "REDIS_FOR_CONVERSATION", False)
        monkeypatch.setattr(ConversationMemory, "_instances", {})
        state = WorkflowState(workflow={"config": {"id": "wf"}, "nodes": [], "edges": []}, thread_id="t")
        captured = {}
        token = RAW_TOOL_ARGUMENTS.set(captured)
        try:
            state.add_tool_event(agent_id="a", tool_id="t1", tool_name="login", result=None, status="succeeded",
                                 arguments={"email": "ana@example.com", "api_key": "sk-live-1", "user": {"password": "p"}})
        finally:
            RAW_TOOL_ARGUMENTS.reset(token)

        # An email is hidden by its look, so checks may compare it; a key named like a credential never is.
        (arguments,) = captured.values()
        assert arguments == {"email": "ana@example.com", "api_key": "[REDACTED]", "user": {"password": "[REDACTED]"}}
