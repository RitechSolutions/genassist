from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.core.turn_stream import TurnStream, current_stream
from app.modules.workflow.agents.memory import ConversationMemory, InMemoryConversationMemory, Message
from app.modules.workflow.guardrails import turn as guardrail_turn
from app.modules.workflow.guardrails.detectors import verdict
from app.modules.workflow.registry import RegistryItem
from app.schemas.guardrails import GuardrailPolicy

_WORKFLOW = {"id": "wf1", "nodes": [{"id": "in", "type": "chatInputNode", "data": {}}], "edges": []}


def _item(policy=None):
    settings = SimpleNamespace(guardrails=policy) if policy is not None else None
    agent = SimpleNamespace(
        id="agentA", name="A", workflow=SimpleNamespace(to_dict=lambda: _WORKFLOW), security_settings=settings
    )
    item = RegistryItem(agent)
    item.workflow_engine.execute_from_node = AsyncMock(
        return_value=SimpleNamespace(
            format_state_as_response=lambda: {
                "status": "success",
                "output": {"message": "agent reply"},
                "guardrail_events": [{"stage": "output", "action": "passed"}],
            }
        )
    )
    return item


def _policy(**overrides):
    return GuardrailPolicy(**{"mode": "block", "blocked_words": ["attack"], "blocked_message": "No can do.", **overrides})


@pytest.fixture
def contexts():
    return []


@pytest.fixture
def checker(monkeypatch, contexts):
    calls = []

    async def fake_check_text(text, checks, stage, mode, usage, **kwargs):
        calls.append((text, stage, mode))
        contexts.append(kwargs.get("context"))
        fired = "attack" in text
        action = ("blocked" if mode == "block" else "flagged") if fired else "passed"
        return [verdict(stage, "blocked_words", mode, action, detector="rules")], action == "blocked"

    monkeypatch.setattr(guardrail_turn, "check_text", fake_check_text)
    return calls


@pytest.mark.asyncio
async def test_a_blocked_message_is_a_normal_reply_and_the_workflow_never_runs(checker):
    item = _item(_policy())
    result = await item.execute("attack now", {"thread_id": "t1"})
    assert result == {
        "status": "success",
        "output": {"message": "No can do."},
        "token_usage": {},
        "cost_usd": 0.0,
        "guardrail_events": [
            {
                "stage": "input", "check_type": "blocked_words", "category": None, "detector": "rules",
                "score": None, "mode": "block", "action": "blocked", "source": None,
            }
        ],
    }
    item.workflow_engine.execute_from_node.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(("source", "output"), [("voice", "No can do."), ("chat", {"message": "No can do."})])
async def test_a_blocked_phone_message_replies_with_plain_text(checker, source, output):
    item = _item(_policy())
    result = await item.execute("attack now", {"thread_id": "t1"}, source=source)
    assert result["status"] == "success"
    assert result["output"] == output


@pytest.mark.asyncio
async def test_a_passed_message_runs_and_its_verdicts_lead_the_reply_verdicts(checker):
    item = _item(_policy())
    result = await item.execute("hello", {"thread_id": "t1"})
    assert result["output"] == {"message": "agent reply"}
    assert [(v["stage"], v["action"]) for v in result["guardrail_events"]] == [("input", "passed"), ("output", "passed")]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("message", "persist"),
    [("attack greeting instruction", False), ("[Voice message]", True)],
)
async def test_the_greeting_and_the_voice_placeholder_are_not_checked(checker, message, persist):
    item = _item(_policy(blocked_words=["attack", "Voice"]))
    result = await item.execute(message, {"thread_id": "t1"}, persist=persist)
    assert checker == []
    assert result["output"] == {"message": "agent reply"}


@pytest.mark.asyncio
async def test_a_form_resume_is_checked_in_detect_mode_and_runs(checker):
    item = _item(_policy())
    metadata = {"thread_id": "t1", "human_in_the_loop_node_id": "hitl1", "human_in_the_loop_from_form": {"note": "attack"}}
    result = await item.execute("attack", metadata)
    assert checker == [("attack", "input", "detect")]
    assert result["output"] == {"message": "agent reply"}
    assert result["guardrail_events"][0]["action"] == "flagged"


@pytest.mark.asyncio
async def test_a_hitl_node_id_without_form_data_is_still_blocked(checker):
    item = _item(_policy())
    result = await item.execute("attack", {"thread_id": "t1", "human_in_the_loop_node_id": "hitl1"})
    assert result["output"] == {"message": "No can do."}
    item.workflow_engine.execute_from_node.assert_not_awaited()


@pytest.mark.asyncio
async def test_live_voice_flags_instead_of_blocking(checker):
    item = _item(_policy())
    result = await item.execute("attack", {"thread_id": "t1"}, live_voice=True)
    assert checker == [("attack", "input", "detect")]
    assert result["output"] == {"message": "agent reply"}


@pytest.mark.asyncio
@pytest.mark.parametrize("policy", [None, _policy(mode="off")])
async def test_no_policy_never_checks(checker, policy):
    item = _item(policy)
    result = await item.execute("attack", {"thread_id": "t1"})
    assert checker == []
    assert result["output"] == {"message": "agent reply"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("policy", "withheld"),
    [
        (_policy(check_replies=True), True),
        (_policy(check_replies=False), False),
        (_policy(mode="detect", check_replies=True), False),
    ],
)
async def test_block_with_reply_checks_withholds_streamed_text(checker, policy, withheld):
    item = _item(policy)
    stream = TurnStream("conv")
    token = current_stream.set(stream)
    try:
        await item.execute("hello", {"thread_id": "t1"})
    finally:
        current_stream.reset(token)
    assert (stream.text_sink("n1") is None) is withheld


@pytest.mark.asyncio
async def test_the_turn_context_is_cleared_after_the_turn(checker):
    item = _item(_policy())
    await item.execute("hello", {"thread_id": "t1"})
    assert guardrail_turn.current_guardrails.get() is None


def test_a_stored_policy_dict_is_read_and_an_invalid_one_is_ignored():
    assert guardrail_turn.active_policy({"mode": "detect", "blocked_words": ["x"]}).blocked_words == ["x"]
    assert guardrail_turn.active_policy({"mode": "sometimes"}) is None
    assert guardrail_turn.active_policy({"mode": "off"}) is None


JUDGE_ID = "0199e3a0-0000-7000-8000-0000000000aa"
QUESTION = "Which size would you like?"


def _context_policy(**overrides):
    return _policy(**{"previous_reply_context": True, "prompt_attack": "medium", "judge_provider_id": JUDGE_ID, **overrides})


async def _memory(*messages):
    memory = InMemoryConversationMemory("t1")
    for role, content in messages:
        await memory.add_message(Message(role, content))
    return memory


@pytest.mark.asyncio
async def test_the_message_check_gets_the_previous_reply_from_thread_memory(checker, contexts):
    item = _item(_context_policy())
    memory = await _memory(("user", "Hello"), ("assistant", {"message": QUESTION}))
    with patch.object(ConversationMemory, "get_instance", return_value=memory) as opened:
        result = await item.execute("Large", {"thread_id": "t1"})
    assert contexts == [QUESTION]
    opened.assert_called_once_with(thread_id="t1")
    assert result["output"] == {"message": "agent reply"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("policy", "metadata"),
    [
        (_context_policy(previous_reply_context=False), {"thread_id": "t1"}),
        (_policy(previous_reply_context=True), {"thread_id": "t1"}),
        (_context_policy(), {}),
    ],
    ids=["switch off", "rules only", "no thread id"],
)
async def test_memory_is_not_read_without_the_switch_a_judge_or_a_thread(checker, contexts, policy, metadata):
    item = _item(policy)
    memory = await _memory(("assistant", {"message": QUESTION}))
    with patch.object(ConversationMemory, "get_instance", return_value=memory) as opened:
        await item.execute("Large", metadata)
    opened.assert_not_called()
    assert contexts == [None]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "messages",
    [
        [("assistant", QUESTION), ("user", "Hello?")],
        [("assistant", {"status": "awaiting_input", "message": "Fill in the form", "fields": []})],
        [],
    ],
    ids=["newest is the customer's", "form", "empty thread"],
)
async def test_no_previous_reply_gives_no_context(checker, contexts, messages):
    memory = await _memory(*messages)
    with patch.object(ConversationMemory, "get_instance", return_value=memory):
        await _item(_context_policy()).execute("Large", {"thread_id": "t1"})
    assert contexts == [None]


@pytest.mark.asyncio
async def test_a_policy_cached_before_the_switch_existed_still_runs_the_turn(checker, contexts):
    stale = _context_policy()
    del stale.__dict__["previous_reply_context"]
    with patch.object(ConversationMemory, "get_instance", return_value=await _memory()):
        result = await _item(stale).execute("hello", {"thread_id": "t1"})
    assert result["output"] == {"message": "agent reply"}
    assert contexts == [None]
