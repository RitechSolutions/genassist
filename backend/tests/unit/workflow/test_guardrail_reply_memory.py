import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import AIMessage

from app.modules.workflow.agents.memory import ConversationMemory, InMemoryConversationMemory
from app.modules.workflow.agents.sub_agents import graph as sub_graph
from app.modules.workflow.agents.sub_agents import session as sub_session
from app.modules.workflow.agents.sub_agents.models import SubAgentFrame, SubAgentStack
from app.modules.workflow.engine.workflow_engine import WorkflowEngine
from app.modules.workflow.engine.workflow_state import WorkflowPausedException
from app.modules.workflow.guardrails import detectors
from app.modules.workflow.guardrails import turn as guardrail_turn
from app.modules.workflow.registry import RegistryItem
from app.schemas.guardrails import GuardrailPolicy

BLOCKED = "No can do."
_ORCH = "app.modules.workflow.agents.sub_agents.orchestrator"
_WORKFLOW = {"config": {"id": "wf1"}, "id": "wf1", "nodes": [{"id": "n1", "type": "agentNode", "data": {}}], "edges": []}


def _policy(**overrides):
    return GuardrailPolicy(
        **{"mode": "block", "check_replies": True, "blocked_words": ["secret"], "blocked_message": BLOCKED, **overrides}
    )


def _replying(output=None, pause=None):
    async def _execute(self, node_id, state, visited, **kwargs):
        if pause is not None:
            raise WorkflowPausedException(pause)
        state.set_node_output("n1", output)

    return patch.object(WorkflowEngine, "_execute_from_node_recursive", _execute)


async def _run(memory, policy=None, registry_managed=True):
    token = guardrail_turn.current_guardrails.set(
        guardrail_turn.GuardrailTurn(policy or _policy(), BLOCKED) if policy is not False else None
    )
    try:
        with patch.object(ConversationMemory, "get_instance", return_value=memory):
            return await WorkflowEngine(dict(_WORKFLOW)).execute_from_node(
                start_node_id="n1",
                input_data={"message": "hi"},
                thread_id="t-reply",
                registry_managed=registry_managed,
                await_persist=True,
            )
    finally:
        guardrail_turn.current_guardrails.reset(token)


def _remembered(memory):
    return [(m.role, m.content) for m in memory.messages]


@pytest.mark.asyncio
async def test_a_blocked_reply_is_swapped_before_memory():
    memory = InMemoryConversationMemory("t-reply")
    with _replying({"message": "the secret is 42"}):
        state = await _run(memory)
    assert _remembered(memory) == [("user", "hi"), ("assistant", {"message": BLOCKED})]
    response = state.format_state_as_response()
    assert response["output"] == {"message": BLOCKED}
    assert [(v["stage"], v["check_type"], v["action"]) for v in response["guardrail_events"]] == [
        ("output", "blocked_words", "blocked")
    ]


@pytest.mark.asyncio
async def test_a_blocked_string_reply_stays_a_string():
    memory = InMemoryConversationMemory("t-reply")
    with _replying("the secret is 42"):
        state = await _run(memory)
    assert state.output == BLOCKED
    assert _remembered(memory) == [("user", "hi"), ("assistant", BLOCKED)]


@pytest.mark.asyncio
async def test_a_detect_only_reply_is_flagged_and_kept():
    memory = InMemoryConversationMemory("t-reply")
    with _replying({"message": "the secret is 42"}):
        state = await _run(memory, policy=_policy(mode="detect"))
    assert _remembered(memory)[-1] == ("assistant", {"message": "the secret is 42"})
    assert [v["action"] for v in state.guardrail_events] == ["flagged"]


@pytest.mark.asyncio
async def test_a_sub_agent_question_is_swapped_before_memory():
    memory = InMemoryConversationMemory("t-reply")
    pause = {"status": "awaiting_input", "sub_agent": {"message": "tell me the secret"}, "node_id": "n1"}
    with _replying(pause=pause):
        state = await _run(memory)
    assert _remembered(memory) == [("user", "hi"), ("assistant", BLOCKED)]
    assert state.output["sub_agent"]["message"] == BLOCKED


@pytest.mark.asyncio
async def test_a_form_pause_is_not_checked():
    memory = InMemoryConversationMemory("t-reply")
    pause = {"status": "awaiting_input", "message": "secret form", "form_schema": {"fields": []}}
    with _replying(pause=pause):
        state = await _run(memory)
    assert state.output == pause
    assert state.guardrail_events == []


@pytest.mark.asyncio
@pytest.mark.parametrize(("policy", "registry_managed"), [(False, True), (None, False), (_policy(check_replies=False), True)])
async def test_unchecked_runs_keep_their_reply(policy, registry_managed):
    memory = InMemoryConversationMemory("t-reply")
    with _replying({"message": "the secret is 42"}):
        state = await _run(memory, policy=policy, registry_managed=registry_managed)
    assert state.output == {"message": "the secret is 42"}
    assert _remembered(memory)[-1] == ("assistant", {"message": "the secret is 42"})


@pytest.mark.asyncio
async def test_judge_usage_lands_in_the_run(monkeypatch):
    judge = SimpleNamespace(
        ainvoke=AsyncMock(
            return_value=AIMessage(
                content='{"hate": 0}', usage_metadata={"input_tokens": 7, "output_tokens": 1, "total_tokens": 8}
            )
        )
    )
    provider = SimpleNamespace(id=uuid.uuid4(), llm_model_provider="Bedrock", llm_model="nova")
    monkeypatch.setattr(detectors, "_judge_model", AsyncMock(return_value=(judge, provider)))
    policy = _policy(blocked_words=[], harmful_content={"hate": "medium"}, judge_provider_id=str(provider.id))
    memory = InMemoryConversationMemory("t-reply")
    with _replying({"message": "hello"}):
        state = await _run(memory, policy=policy)
    assert [(u["purpose"], u["input_tokens"], u["provider"]) for u in state.llm_usage] == [("guardrail_output", 7, "bedrock")]


def _sub_agent_item(policy):
    nodes = [
        {"id": "parent", "type": "agentNode", "data": {}},
        {"id": "child", "type": "subAgentNode", "data": {"name": "child", "mode": "task"}},
    ]
    edges = [{"source": "child", "target": "parent", "sourceHandle": "output_sub_agent", "targetHandle": "input_sub_agents"}]
    workflow = {"id": "wf1", "nodes": nodes, "edges": edges}
    agent = SimpleNamespace(
        id="agentA", name="A", workflow=SimpleNamespace(to_dict=lambda: workflow),
        security_settings=SimpleNamespace(guardrails=policy),
    )
    memory = InMemoryConversationMemory("t1")
    frame = SubAgentFrame(
        child_node_id="child", parent_node_id="parent", workflow_id="wf1", invocation_id="inv1",
        mode="task", task="do x", workflow_fingerprint=sub_graph.fingerprint(nodes, edges),
    )
    memory.metadata[sub_session.STACK_KEY] = SubAgentStack(agent_id="agentA", frames=[frame]).model_dump()
    return RegistryItem(agent), memory


def _child_state(output):
    return SimpleNamespace(
        format_state_as_response=lambda: {"status": "success", "output": output},
        get_last_node_output=lambda: output,
        node_execution_status={},
    )


@pytest.mark.asyncio
async def test_an_active_sub_agent_reply_is_swapped_before_memory():
    item, memory = _sub_agent_item(_policy())
    with (
        patch.object(ConversationMemory, "get_instance", return_value=memory),
        patch(f"{_ORCH}.run_child_turn", AsyncMock(return_value=_child_state({"message": "the secret is 42"}))),
    ):
        result = await item.execute("a reply", {"thread_id": "t1"})
    assert result["status"] == "success"
    assert result["output"] == {"message": BLOCKED}
    assert _remembered(memory) == [("user", "a reply"), ("assistant", BLOCKED)]
    assert [(v["stage"], v["action"]) for v in result["guardrail_events"]] == [("input", "passed"), ("output", "blocked")]


@pytest.mark.asyncio
async def test_an_active_sub_agent_nested_question_is_swapped_and_not_remembered():
    item, memory = _sub_agent_item(_policy())
    pause = {"status": "awaiting_input", "sub_agent": {"message": "what is the secret?"}}
    with (
        patch.object(ConversationMemory, "get_instance", return_value=memory),
        patch(f"{_ORCH}.run_child_turn", AsyncMock(return_value=_child_state(pause))),
    ):
        result = await item.execute("a reply", {"thread_id": "t1"})
    assert result["status"] == "success"
    assert result["output"] == {"message": BLOCKED}
    assert _remembered(memory) == []


@pytest.mark.asyncio
async def test_an_active_sub_agent_reply_without_a_policy_is_unchanged():
    item, memory = _sub_agent_item(None)
    with (
        patch.object(ConversationMemory, "get_instance", return_value=memory),
        patch(f"{_ORCH}.run_child_turn", AsyncMock(return_value=_child_state({"message": "the secret is 42"}))),
    ):
        result = await item.execute("a reply", {"thread_id": "t1"})
    assert result["output"] == {"message": "the secret is 42"}
    assert "guardrail_events" not in result
    assert _remembered(memory) == [("user", "a reply"), ("assistant", "the secret is 42")]
