from uuid import UUID

import pytest

from app.services import guardrails as guardrail_service
from app.services.guardrails import GuardrailService, record_events_without_conversation

AGENT_ID = UUID("0199e3a0-0000-7000-8000-0000000000a1")
CONVERSATION_ID = UUID("0199e3a0-0000-7000-8000-0000000000c1")
INPUT_MESSAGE_ID = UUID("0199e3a0-0000-7000-8000-0000000000d1")
REPLY_MESSAGE_ID = UUID("0199e3a0-0000-7000-8000-0000000000d2")


def _verdict(stage, action, check_type="blocked_words", source=None):
    return {
        "stage": stage,
        "check_type": check_type,
        "category": "competitorx",
        "detector": "rules",
        "score": None,
        "mode": "block",
        "action": action,
        "source": source,
    }


class FakeRepository:
    def __init__(self):
        self.batches = []

    async def add_many(self, rows):
        self.batches.append(rows)


async def _record(registry_response, conversation_id=CONVERSATION_ID, input_id=INPUT_MESSAGE_ID, reply_id=REPLY_MESSAGE_ID):
    repo = FakeRepository()
    await GuardrailService(repo).record_turn_events(AGENT_ID, conversation_id, input_id, reply_id, registry_response)
    return repo.batches


@pytest.mark.asyncio
async def test_fired_verdicts_are_written_against_the_message_they_judged():
    batches = await _record(
        {
            "execution_id": "exec-1",
            "guardrail_events": [
                _verdict("input", "blocked"),
                _verdict("input", "passed", "prompt_attack"),
                _verdict("output", "flagged", "harmful_content"),
                _verdict("tool", "error", "detector_error", source="search"),
            ],
        }
    )

    assert len(batches) == 1
    assert [(r.stage, r.check_type, r.action, r.transcript_message_id, r.source) for r in batches[0]] == [
        ("input", "blocked_words", "blocked", INPUT_MESSAGE_ID, None),
        ("output", "harmful_content", "flagged", REPLY_MESSAGE_ID, None),
        ("tool", "detector_error", "error", REPLY_MESSAGE_ID, "search"),
    ]
    assert {(r.agent_id, r.conversation_id, r.workflow_execution_id) for r in batches[0]} == {
        (AGENT_ID, CONVERSATION_ID, "exec-1")
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "registry_response",
    [{}, {"guardrail_events": [_verdict("input", "passed"), _verdict("tool", "skipped", "too_long")]}],
    ids=["no checks ran", "only passed and skipped checks"],
)
async def test_nothing_is_written_when_no_check_fired(registry_response):
    assert await _record(registry_response) == []


@pytest.mark.asyncio
async def test_a_turn_without_a_conversation_writes_rows_with_no_conversation_or_message():
    batches = await _record(
        {"guardrail_events": [_verdict("input", "blocked"), _verdict("output", "flagged", "denied_topic")]},
        conversation_id=None,
        input_id=None,
        reply_id=None,
    )

    assert [(r.stage, r.conversation_id, r.transcript_message_id) for r in batches[0]] == [
        ("input", None, None),
        ("output", None, None),
    ]


@pytest.mark.asyncio
async def test_a_long_tool_name_is_cut_to_the_column_width():
    batches = await _record({"guardrail_events": [_verdict("tool", "flagged", "untrusted_content", source="t" * 300)]})

    assert batches[0][0].source == "t" * 128


def test_no_task_is_scheduled_when_no_check_fired(monkeypatch):
    scheduled = []
    monkeypatch.setattr(guardrail_service, "spawn", lambda coro, name: scheduled.append(name))

    record_events_without_conversation(AGENT_ID, {"guardrail_events": [_verdict("input", "passed")]})
    record_events_without_conversation(AGENT_ID, {})

    assert scheduled == []
