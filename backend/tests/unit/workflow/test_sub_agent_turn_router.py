"""SubAgentTurnRouter direct tests: detection, ownership, stale, resume, finalize"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.core.exceptions.exception_classes import AppException
from app.modules.workflow.agents.memory import ConversationMemory, InMemoryConversationMemory
from app.modules.workflow.agents.sub_agents import graph as sub_graph
from app.modules.workflow.agents.sub_agents import session as sub_session
from app.modules.workflow.agents.sub_agents.models import SubAgentFrame, SubAgentStack
from app.modules.workflow.agents.sub_agents.turn_router import SubAgentTurnRouter
from app.modules.workflow.engine.workflow_engine import WorkflowEngine

_ORCH = "app.modules.workflow.agents.sub_agents.orchestrator"

_NODES = [
    {"id": "parent", "type": "agentNode", "data": {}},
    {"id": "child", "type": "subAgentNode", "data": {"name": "child", "mode": "task"}},
]
_EDGES = [
    {"source": "child", "target": "parent", "sourceHandle": "output_sub_agent", "targetHandle": "input_sub_agents"}
]


def _make_router(owner_id="agentA", nodes=_NODES, edges=_EDGES):
    engine = WorkflowEngine({"id": "wf1", "nodes": nodes, "edges": edges})
    return SubAgentTurnRouter(engine, owner_id=owner_id)


def _fake_state(response):
    return SimpleNamespace(format_state_as_response=lambda: response)


def _seed_stack(fingerprint=None):
    mem = InMemoryConversationMemory("t1")
    frame = SubAgentFrame(
        child_node_id="child",
        parent_node_id="parent",
        workflow_id="wf1",
        invocation_id="inv1",
        mode="task",
        task="do x",
        workflow_fingerprint=fingerprint if fingerprint is not None else sub_graph.fingerprint(_NODES, _EDGES),
    )
    mem.metadata[sub_session.STACK_KEY] = SubAgentStack(agent_id="agentA", frames=[frame]).model_dump()
    return mem


def test_has_sub_agents_detects_child_nodes():
    assert _make_router().has_sub_agents() is True
    plain = _make_router(nodes=[{"id": "parent", "type": "agentNode", "data": {}}], edges=[])
    assert plain.has_sub_agents() is False


@pytest.mark.asyncio
async def test_no_frame_returns_none():
    router = _make_router()
    with patch.object(ConversationMemory, "get_instance", return_value=InMemoryConversationMemory("t1")):
        assert await router.route_turn("msg", "t1", {"message": "msg"}, persist=True) is None


@pytest.mark.asyncio
async def test_unowned_frame_returns_none_and_left_intact():
    router = _make_router(owner_id="someone-else")
    mem = _seed_stack()
    with patch.object(ConversationMemory, "get_instance", return_value=mem):
        assert await router.route_turn("msg", "t1", {"message": "msg"}, persist=True) is None
    assert mem.metadata[sub_session.STACK_KEY]["agent_id"] == "agentA"


@pytest.mark.asyncio
async def test_stale_fingerprint_raises_409_and_clears():
    router = _make_router()
    mem = _seed_stack(fingerprint="stale-hash")
    with patch.object(ConversationMemory, "get_instance", return_value=mem):
        with pytest.raises(AppException) as exc:
            await router.route_turn("msg", "t1", {"message": "msg"}, persist=True)
    assert exc.value.status_code == 409
    assert mem.metadata[sub_session.STACK_KEY] is None


@pytest.mark.asyncio
async def test_corrupt_stack_returns_controlled_message():
    router = _make_router()
    mem = InMemoryConversationMemory("t1")
    mem.metadata[sub_session.STACK_KEY] = {"version": 1, "agent_id": "agentA", "frames": "junk"}
    with patch.object(ConversationMemory, "get_instance", return_value=mem):
        result = await router.route_turn("msg", "t1", {"message": "msg"}, persist=True)
    assert result["status"] == "success"
    assert "could not be resumed" in result["output"]["message"]


@pytest.mark.asyncio
async def test_active_child_question_returns_success_message():
    router = _make_router()
    mem = _seed_stack()
    child_state = _fake_state({"status": "success", "output": {"message": "Is a layover okay?"}})
    with (
        patch.object(ConversationMemory, "get_instance", return_value=mem),
        patch(f"{_ORCH}.run_child_turn", AsyncMock(return_value=child_state)),
    ):
        result = await router.route_turn("a reply", "t1", {"message": "a reply"}, persist=True)
    assert result["status"] == "success"
    assert result["output"]["message"] == "Is a layover okay?"


@pytest.mark.asyncio
async def test_child_timeout_keeps_frame_intact():
    router = _make_router()
    mem = _seed_stack()
    with (
        patch.object(ConversationMemory, "get_instance", return_value=mem),
        patch(f"{_ORCH}.run_child_turn", AsyncMock(side_effect=asyncio.TimeoutError())),
    ):
        result = await router.route_turn("a reply", "t1", {"message": "a reply"}, persist=True)
    assert "did not respond in time" in result["output"]["message"]
    assert mem.metadata[sub_session.STACK_KEY]["frames"][0]["invocation_id"] == "inv1"


@pytest.mark.asyncio
async def test_completed_child_resumes_parent_registry_managed():
    router = _make_router()
    mem = _seed_stack()
    child_state = SimpleNamespace(
        sub_agent_control={"result": "child done"},
        get_last_node_output=lambda: {"message": "child done"},
    )
    router.workflow_engine.execute_from_node = AsyncMock(
        return_value=_fake_state({"status": "success", "output": {"message": "parent final"}})
    )
    with (
        patch.object(ConversationMemory, "get_instance", return_value=mem),
        patch(f"{_ORCH}.run_child_turn", AsyncMock(return_value=child_state)),
    ):
        result = await router.route_turn("a reply", "t1", {"message": "a reply"}, persist=True)

    assert result["output"]["message"] == "parent final"
    _, kwargs = router.workflow_engine.execute_from_node.call_args
    assert kwargs["start_node_id"] == "parent"
    assert kwargs["registry_managed"] is True
    assert kwargs["input_data"]["__sub_agent_resume"]["child_result"] == "child done"
    assert mem.metadata[sub_session.STACK_KEY] is None
