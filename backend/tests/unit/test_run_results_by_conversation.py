"""A run's results by conversation, as the results page reads them."""
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.exceptions.exception_classes import AppException
from app.services.test_suite import TestSuiteService as EvalService

T0 = datetime(2026, 10, 1)


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


def _case(case_id, conversation, turn_index, message, *, expected=None, deleted=0):
    return SimpleNamespace(
        id=case_id,
        source_conversation_id=conversation,
        turn_index=turn_index,
        created_at=T0 + timedelta(minutes=turn_index),
        input_data={"message": message},
        expected_output=expected,
        is_deleted=deleted,
    )


def _result(case_id, status="scored", *, metrics=None, reply=None, trace_input=None, error=None):
    return SimpleNamespace(
        case_id=case_id,
        status=status,
        error=error,
        metrics=metrics,
        actual_output={"value": reply} if reply is not None else None,
        trace_input=trace_input,
        has_trace=trace_input is not None,
    )


def _rule(run_id, status, *, case_id=None, conversation=None, scope="turn", expected="", observed=""):
    return SimpleNamespace(
        id=uuid4(),
        run_id=run_id,
        technique="checks",
        rule_id="a",
        scope=scope,
        case_id=case_id,
        source_conversation_id=conversation,
        status=status,
        score=1.0 if status == "passed" else 0.0 if status == "failed" else None,
        details={"expected": expected, "observed": observed},
        created_at=T0,
    )


class TestRunConversations:
    @pytest.mark.asyncio
    async def test_a_run_reads_by_conversation(self):
        run_id, suite_id, conversation = uuid4(), uuid4(), uuid4()
        first, second, removed = sorted([uuid4(), uuid4(), uuid4()], key=str)
        service = _service()
        service.run_repo.get_by_id = AsyncMock(
            return_value=SimpleNamespace(id=run_id, suite_id=suite_id, status="completed", techniques=["contains", "checks"])
        )
        service.result_repo.get_outcomes_for_run = AsyncMock(return_value=[
            _result(first, metrics={"contains": {"score": 0.0, "passed": False, "comment": "Not in the reply"}},
                    reply="Your order ships tomorrow.", trace_input={"message": "Where is my order?", "region": "uk"}),
            _result(second, "skipped", error="Skipped: an earlier turn was not persisted to memory"),
            _result(removed, metrics={"contains": {"score": 1.0, "passed": True}}, reply="Hello", trace_input="Hi"),
        ])
        on_turn = _rule(run_id, "failed", case_id=first, expected='The tool "save_region" should not be called',
                        observed="Called once")
        whole = _rule(run_id, "passed", conversation=conversation, scope="conversation")
        lost = _rule(run_id, "not_evaluated", scope="conversation")
        service.tool_rule_result_repo.get_all_for_run = AsyncMock(return_value=[on_turn, whole, lost])
        service.case_repo.get_cases_by_ids = AsyncMock(return_value=[
            _case(first, conversation, 0, "Where is it?", expected={"value": "It's on its way."}),
            _case(second, conversation, 1, "Thanks"),
            _case(removed, None, 0, "Hi", deleted=1),
        ])

        result = await service.get_run_conversations(run_id)

        # Turns removed from the dataset since the run are still read.
        assert service.case_repo.get_cases_by_ids.await_args.kwargs == {"include_deleted": True}
        assert result.counts.model_dump() == {"total": 2, "passed": 1, "failed": 1, "not_evaluated": 0}
        thread, single = result.conversations
        assert thread.key == str(conversation) and thread.verdict == "failed"
        one, two = thread.turns
        # What the run sent, not what the dataset says now.
        assert (one.number, one.message, one.expected, one.reply) == (
            1, "Where is my order?", "It's on its way.", "Your order ships tomorrow.")
        assert one.verdict == "failed" and one.reason is None and one.has_trace
        assert [rule.id for rule in one.rules] == [on_turn.id]
        assert one.metrics["contains"].comment == "Not in the reply"
        assert two.verdict == "not_evaluated" and not two.has_trace
        assert two.reason == "This turn did not run because an earlier turn failed."
        assert [rule.id for rule in thread.rules] == [whole.id]
        assert single.verdict == "passed" and not single.turns[0].in_dataset
        assert [rule.id for rule in result.other_rules] == [lost.id]

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "status, techniques, pending",
        [
            ("running", ["checks"], True),
            ("failed", ["contains", "tool_used"], True),
            ("completed", ["checks"], False),
            ("running", ["contains"], False),
        ],
    )
    async def test_rules_are_pending_until_the_run_completes(self, status, techniques, pending):
        service = _service()
        service.run_repo.get_by_id = AsyncMock(
            return_value=SimpleNamespace(id=uuid4(), suite_id=uuid4(), status=status, techniques=techniques)
        )
        service.result_repo.get_outcomes_for_run = AsyncMock(return_value=[])
        service.tool_rule_result_repo.get_all_for_run = AsyncMock(return_value=[])
        service.case_repo.get_cases_by_ids = AsyncMock(return_value=[])

        result = await service.get_run_conversations(uuid4())

        assert result.rules_pending is pending

    @pytest.mark.asyncio
    async def test_a_skipped_turn_has_no_steps(self):
        case_id = uuid4()
        service = _service()
        service.run_repo.get_by_id = AsyncMock(
            return_value=SimpleNamespace(id=uuid4(), suite_id=uuid4(), status="completed", techniques=["contains"])
        )
        skipped = _result(case_id, "skipped", error="Skipped: an earlier turn was not persisted to memory")
        skipped.has_trace = True  # a stored JSON null is not a trace
        service.result_repo.get_outcomes_for_run = AsyncMock(return_value=[skipped])
        service.tool_rule_result_repo.get_all_for_run = AsyncMock(return_value=[])
        service.case_repo.get_cases_by_ids = AsyncMock(return_value=[_case(case_id, None, 0, "Hi")])

        result = await service.get_run_conversations(uuid4())

        assert result.conversations[0].turns[0].has_trace is False

    @pytest.mark.asyncio
    async def test_an_unknown_run_is_not_found(self):
        service = _service()
        service.run_repo.get_by_id = AsyncMock(return_value=None)
        with pytest.raises(AppException) as excinfo:
            await service.get_run_conversations(uuid4())
        assert excinfo.value.status_code == 404

    @pytest.mark.asyncio
    async def test_the_trace_of_an_unknown_run_is_not_found(self):
        service = _service()
        service.run_repo.get_by_id = AsyncMock(return_value=None)
        with pytest.raises(AppException) as excinfo:
            await service.get_run_turn_trace(uuid4(), uuid4())
        assert excinfo.value.status_code == 404

    @pytest.mark.asyncio
    async def test_a_turn_trace_is_read_on_its_own(self):
        service = _service()
        service.run_repo.get_by_id = AsyncMock(return_value=SimpleNamespace(id=uuid4()))
        service.result_repo.get_trace = AsyncMock(return_value={"state": {"nodeExecutionStatus": {}}})
        trace = await service.get_run_turn_trace(uuid4(), uuid4())
        assert trace.execution_trace == {"state": {"nodeExecutionStatus": {}}}

        service.result_repo.get_trace = AsyncMock(return_value=None)
        assert (await service.get_run_turn_trace(uuid4(), uuid4())).execution_trace is None
