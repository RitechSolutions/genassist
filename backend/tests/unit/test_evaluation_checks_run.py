"""Checks in a run: graded on what each turn did, stored one row each, masked, summarized by conversation."""
import asyncio
import time
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
import app.services.test_suite as test_suite_module
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


async def _execute(service, cases, checks, *, nodes=NODES, edges=EDGES, engine=None, create=None):
    service.case_repo.get_all_for_suite.return_value = cases
    service.result_repo.create = create or AsyncMock()
    # The run counts its conversations from the rows it stored.
    service.tool_rule_result_repo.get_all_for_run = AsyncMock(side_effect=lambda _run_id: _rows(service))
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
    async def test_a_hidden_value_in_another_tools_values_is_masked(self, in_memory):
        cases = [_case(uuid4(), 0, {"message": "Hello", "region": "uk", "api_token": SECRET})]
        checks = [{"id": "tools", "kind": "tool_called", "tool_name": "lookup",
                   "tools": [{"tool_name": "search", "args": {"key": SECRET}, "result_contains": SECRET}]}]
        service = _service()

        await _execute(service, cases, checks)

        (row,) = _rows(service)
        assert SECRET not in str(row.details)
        assert row.details["rule"]["tools"][0]["args"] == {"key": "[API_TOKEN]"}

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
        assert run.summary_metrics["_conversations"] == {"total": 1, "passed": 0, "failed": 1, "not_evaluated": 0}

    @pytest.mark.asyncio
    async def test_the_expected_reply_and_step_errors_come_from_the_run(self, in_memory):
        conversation = uuid4()
        first = _case(conversation, 0, {"message": "Refund please", "region": "uk"})
        first.expected_output = {"text": "Mode is refund"}
        cases = [first, _case(conversation, 1, {"message": "Thanks"})]
        checks = [
            {"id": "exact", "kind": "reply_matches", "match": "exact"},
            {"id": "inside", "kind": "reply_matches", "match": "contains", "level": "turn", "case_id": str(first.id)},
            {"id": "errors", "kind": "step_fails", "expect": "should_not"},
            {"id": "grounded", "kind": "reply_grounded"},
        ]
        service = _service()

        await _execute(service, cases, checks)

        rows = {row.rule_id: row for row in _rows(service)}
        assert rows["exact"].status == "passed"
        # The second turn has no expected reply, so only the first is checked.
        assert rows["exact"].details["observed"] == "Held on the one turn checked; the other turn could not be checked."
        assert rows["inside"].status == "passed"
        assert rows["errors"].status == "passed"
        assert rows["grounded"].status == "not_evaluated"
        assert rows["grounded"].details["comment"] == (
            "No turn of this conversation found knowledge-base passages to check against."
        )

    def test_more_to_grade_by_ai_gets_more_time(self):
        budget = test_suite_module._checks_judge_budget
        rubric = {"checks": [{"id": "r", "kind": "reply_meets", "rubric": "Greet", "when": "every_turn"}]}
        plain = {"checks": [{"id": "m", "kind": "reply_mentions", "text": "x"}]}
        assert budget({"checks": plain}, 1000, 100) == test_suite_module.CHECKS_JUDGE_BUDGET_SECONDS
        assert budget({"checks": rubric}, 600, 60) == 600 * test_suite_module.CHECK_JUDGE_SECONDS_EACH
        assert budget({"checks": rubric}, 100000, 10) == test_suite_module.CHECKS_JUDGE_BUDGET_CAP_SECONDS
        assert budget({"checks": {"checks": [{"id": "bad"}]}}, 600, 60) == test_suite_module.CHECKS_JUDGE_BUDGET_SECONDS
        # A check on one turn is graded once, however long the run.
        both = {"checks": [*rubric["checks"], {"id": "t", "kind": "reply_meets", "rubric": "Greet", "level": "turn",
                                               "case_id": "case-1"}]}
        assert budget({"checks": both}, 600, 60) == 601 * test_suite_module.CHECK_JUDGE_SECONDS_EACH

    def test_grading_ends_before_the_run_time_limit(self):
        budget = test_suite_module._checks_judge_budget
        rubric = {"checks": [{"id": "r", "kind": "reply_meets", "rubric": "Greet", "when": "every_turn"}]}
        # 70 minutes in, the grader gets what is left after the margin and storing.
        left = test_suite_module.RUN_TIME_LIMIT_SECONDS - 70 * 60
        assert budget({"checks": rubric}, 100000, 10, left) == left - 3 * 60 - test_suite_module.RUN_FINISH_SECONDS
        # Late in a run that is less than usual, and with no time left nothing, rather than past the limit.
        assert budget({"checks": rubric}, 10, 1, 10 * 60) == 2 * 60
        assert budget({"checks": {"checks": [{"id": "bad"}]}}, 10, 1, 10 * 60) == 2 * 60
        assert budget({"checks": rubric}, 100000, 10, 60) == 0

    @pytest.mark.asyncio
    async def test_the_checks_stop_in_time_for_the_run_to_store_its_results(self):
        service = _service()
        never_done = asyncio.Event()

        async def grade_forever(**_kwargs):
            await never_done.wait()

        service._evaluate_checks = grade_forever
        # A run whose turns took all but two minutes of its limit.
        started = time.monotonic() - test_suite_module.RUN_TIME_LIMIT_SECONDS + 2 * 60
        summaries = await asyncio.wait_for(
            service._evaluate_rule_techniques(
                run=SimpleNamespace(id=uuid4()), cases=[], conversations=[], technique_configs={}, workflow=None,
                requested=["checks"], case_events={}, case_executed_agents={}, case_routes={}, case_actions={},
                started=started,
            ),
            timeout=5,
        )
        assert summaries["checks"]["error"] == "Checks evaluation failed or timed out."

    @pytest.mark.asyncio
    async def test_the_checks_budget_leaves_out_the_time_earlier_techniques_took(self, monkeypatch):
        service = _service()
        clock = {"now": 10_000.0}
        monkeypatch.setattr(test_suite_module, "time", SimpleNamespace(monotonic=lambda: clock["now"]))
        budgets = []

        async def slow_tool_rules(**_kwargs):
            clock["now"] += 30 * 60

        async def checks(**kwargs):
            budgets.append(kwargs["judge_budget"])

        service._evaluate_tool_usage = slow_tool_rules
        service._evaluate_checks = checks
        rubric = {"checks": {"checks": [{"id": "r", "kind": "reply_meets", "rubric": "Greet", "when": "every_turn"}]}}
        # 40 minutes are left when grading starts, and the older tool rules take 30 of them.
        started = clock["now"] - test_suite_module.RUN_TIME_LIMIT_SECONDS + 40 * 60
        await service._evaluate_rule_techniques(
            run=SimpleNamespace(id=uuid4()), cases=[None] * 2000, conversations=[], technique_configs=rubric,
            workflow=None, requested=["tool_used", "checks"], case_events={}, case_executed_agents={},
            case_routes={}, case_actions={}, started=started,
        )
        # The checks get the 10 minutes still left: 2 for AI grading, after their margin and storing.
        assert budgets == [2 * 60]

    def test_step_errors_read_plainly(self):
        nodes = {"n1": {"label": "Search"}}
        assert test_suite_module._step_errors_text([{"node": "n1", "error": "timed out"}], nodes) == (
            'The step "Search" failed: timed out.'
        )
        many = [{"node": "n1", "error": f"e{index}"} for index in range(5)]
        assert test_suite_module._step_errors_text(many, nodes) == (
            'The step "Search" failed: e0. The step "Search" failed: e1. The step "Search" failed: e2. And 2 more.'
        )

    def test_a_failed_step_is_named_once_without_its_id(self):
        step = "a2305382-1f19-4606-9118-ecca4652e18c"
        nodes = {step: {"label": "Start"}}
        reason = f"Error executing node {step}: value missing for required key: order_number"
        errors = [
            {"type": "node_execution", "message": f"Node {step}: {reason}", "timestamp": "2026-10-14T16:00:18"},
            {"node": step, "error": reason},
        ]
        assert test_suite_module._step_errors_text(errors, nodes) == (
            'The step "Start" failed: value missing for required key: order_number.'
        )

    def test_an_error_of_no_step_is_the_workflow_s(self):
        errors = [{"type": "execution_failure", "message": "Workflow timed out.", "timestamp": "2026-10-14T16:00:18"}]
        assert test_suite_module._step_errors_text(errors, {}) == "The workflow failed: Workflow timed out."

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
        assert set(run.summary_metrics) == {"checks", "_totals", "_conversations"}
        # The run's own count agrees with the checks'.
        assert run.summary_metrics["_conversations"] == run.summary_metrics["checks"]["conversations"]


async def _read_back(service, run, cases):
    """The run's stored rows, read back the way the results page reads them."""
    stored = [call.args[0] for call in service.result_repo.create.await_args_list]
    rules = _rows(service)
    for rule in rules:
        rule.id, rule.created_at = uuid4(), datetime(2026, 1, 1)
    service.run_repo.get_by_id = AsyncMock(
        return_value=SimpleNamespace(id=run.id, suite_id=uuid4(), status="completed", techniques=run.techniques)
    )
    service.result_repo.get_outcomes_for_run = AsyncMock(return_value=[
        SimpleNamespace(
            case_id=row.case_id, status=row.status, error=row.error, metrics=row.metrics,
            actual_output=row.actual_output, trace_input=(row.execution_trace or {}).get("input"),
            has_trace=row.execution_trace is not None,
        )
        for row in stored
    ])
    service.tool_rule_result_repo.get_all_for_run = AsyncMock(return_value=rules)
    service.case_repo.get_cases_by_ids = AsyncMock(return_value=[SimpleNamespace(**vars(case), is_deleted=0) for case in cases])
    return await service.get_run_conversations(run.id)


class TestCountsAgree:
    """The counts a run stores, its checks' counts and its results page always agree."""

    @staticmethod
    def _cases():
        conversation = uuid4()
        return [
            _case(conversation, 0, {"message": "Hi", "region": "uk"}),
            _case(conversation, 1, {"message": "Again", "region": "uk"}),
            _case(None, 0, {"message": "Alone", "region": "uk"}),
        ]

    async def _assert_agree(self, service, run, cases):
        page = await _read_back(service, run, cases)
        stored = run.summary_metrics["_conversations"]
        assert stored == run.summary_metrics["checks"]["conversations"]
        assert page.counts.model_dump() == stored
        return stored

    @pytest.mark.asyncio
    async def test_on_an_ordinary_run(self, in_memory):
        service = _service()
        cases = self._cases()
        run = await _execute(service, cases, [
            {"id": "a", "kind": "reply_mentions", "text": "mode"},
            {"id": "b", "kind": "state_equals", "key": "mode", "value": "standard", "level": "turn", "case_id": str(cases[1].id)},
        ])
        stored = await self._assert_agree(service, run, cases)
        assert stored["total"] == 2

    @pytest.mark.asyncio
    async def test_when_a_turn_could_not_be_read_for_the_checks(self, in_memory, monkeypatch):
        real = test_suite_module.tool_calls_from_events
        calls = {"count": 0}

        def unreadable_once(*args, **kwargs):
            calls["count"] += 1
            if calls["count"] == 1:
                raise RuntimeError("unreadable events")
            return real(*args, **kwargs)

        monkeypatch.setattr(test_suite_module, "tool_calls_from_events", unreadable_once)
        service = _service()
        cases = self._cases()
        run = await _execute(service, cases, [{"id": "a", "kind": "reply_mentions", "text": "mode"}])
        await self._assert_agree(service, run, cases)

    @pytest.mark.asyncio
    async def test_when_a_turn_ran_but_could_not_be_stored_as_scored(self, in_memory):
        failed_once = []

        async def create(row):
            if row.status == "scored" and not failed_once:
                failed_once.append(row)
                raise RuntimeError("flush failed")
            return row

        service = _service()
        cases = self._cases()
        run = await _execute(
            service, cases, [{"id": "a", "kind": "reply_mentions", "text": "mode"}], create=AsyncMock(side_effect=create)
        )
        statuses = [call.args[0].status for call in service.result_repo.create.await_args_list]
        assert "scoring_failed" in statuses
        await self._assert_agree(service, run, cases)


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
    async def test_a_check_with_its_own_grader_is_graded_by_it(self):
        used = []

        def model_for(name):
            async def ainvoke(_messages):
                used.append(name)
                return AIMessage(content='{"score": 1.0, "reason": "Fine."}')

            return SimpleNamespace(ainvoke=ainvoke)

        provider = SimpleNamespace(get_model=AsyncMock(side_effect=lambda grader: model_for(grader or "default")))
        service = _service()
        service._flush_judge_usage = AsyncMock()
        turn = TurnRecord(case_id="a1", conversation_key="a", turn_index=0, position=0, message="Hi", reply="Hello")
        own = Check(id="o", kind="reply_meets", rubric="Greet", when="every_turn", llm_provider_id="other")
        shared = Check(id="s", kind="reply_meets", rubric="Be brief", when="every_turn")
        with patch("app.services.test_suite.injector", SimpleNamespace(get=lambda _cls: provider)):
            verdicts = await service._judge_checks(
                [JudgeRequest(own, [turn]), JudgeRequest(shared, [turn])],
                "main",
                run=SimpleNamespace(id=uuid4()),
                workflow=SimpleNamespace(id=uuid4(), agent_id=None),
                provider_name_cache={},
                metering_state={"timed_out": False},
            )
        assert verdicts[("o", ("a1",))].met and verdicts[("s", ("a1",))].met
        assert sorted(used) == ["main", "other"]

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


class TestGradedAsTheOlderMethodsDid:
    @staticmethod
    def _request(**fields):
        item = Check(id="g", kind="reply_grounded", context="expected_reply", **fields)
        record = TurnRecord(case_id="a1", conversation_key="a", turn_index=0, position=0, message="m",
                            reply="It ships Monday.", expected="It ships on Monday.")
        return JudgeRequest(item, [record])

    @pytest.mark.asyncio
    async def test_should_not_holds_when_the_reply_does_not_stick_to_its_source(self):
        evaluators = SimpleNamespace(similarity_result=AsyncMock(return_value={"score": 0.2, "passed": False, "comment": "low"}))
        service = SimpleNamespace(evaluators=evaluators)
        verdict = await test_suite_module.TestSuiteService._grade_locally(
            service, self._request(grader="similarity", expect="should_not", pass_score=0.6)
        )
        assert (verdict.passed, verdict.score, verdict.reason) == (True, 0.2, "low")
        evaluators.similarity_result.assert_awaited_once_with(
            "It ships Monday.", "It ships on Monday.", {"min_score": 0.6}
        )

    @pytest.mark.asyncio
    async def test_the_nli_model_gets_its_settings_and_a_failure_is_an_error(self):
        evaluators = SimpleNamespace(nli_result=AsyncMock(side_effect=RuntimeError("NLI model unavailable")))
        service = SimpleNamespace(evaluators=evaluators)
        verdict = await test_suite_module.TestSuiteService._grade_locally(
            service, self._request(grader="nli", nli_model="m", fail_on_contradiction=True)
        )
        assert verdict.error and verdict.reason == "The NLI model could not grade this reply."
        evaluators.nli_result.assert_awaited_once_with(
            "It ships Monday.", "It ships on Monday.",
            {"min_entail_score": 0.5, "fail_on_contradiction": True, "nli_model_name": "m"},
        )
