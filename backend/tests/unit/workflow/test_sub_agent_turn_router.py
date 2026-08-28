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


def _fake_state(response, last_output=None):
    return SimpleNamespace(
        format_state_as_response=lambda: response,
        get_last_node_output=lambda: last_output,
    )


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
    child_state = _fake_state(
        {"status": "success", "output": {"message": "Is a layover okay?"}},
        last_output={"message": "Is a layover okay?"},
    )
    with (
        patch.object(ConversationMemory, "get_instance", return_value=mem),
        patch(f"{_ORCH}.run_child_turn", AsyncMock(return_value=child_state)),
    ):
        result = await router.route_turn("a reply", "t1", {"message": "a reply"}, persist=True)
    assert result["status"] == "success"
    assert result["output"]["message"] == "Is a layover okay?"


@pytest.mark.asyncio
async def test_active_child_output_is_message_only():
    router = _make_router()
    mem = _seed_stack()
    node_status = {"child": {"status": "completed"}}
    child_state = _fake_state(
        {
            "status": "success",
            "output": {"message": "Booked.", "steps": [{"n": 1}], "tools_used": ["search"]},
            "state": {
                "output": {"message": "Booked.", "steps": [{"n": 1}]},
                "nodeExecutionStatus": node_status,
            },
        },
        last_output={"message": "Booked.", "steps": [{"n": 1}], "tools_used": ["search"]},
    )
    with (
        patch.object(ConversationMemory, "get_instance", return_value=mem),
        patch(f"{_ORCH}.run_child_turn", AsyncMock(return_value=child_state)),
    ):
        result = await router.route_turn("a reply", "t1", {"message": "a reply"}, persist=True)
    assert result["status"] == "success"
    assert result["output"] == {"message": "Booked."}
    assert result["state"]["output"] == {"message": "Booked."}
    assert result["state"]["nodeExecutionStatus"] == node_status


@pytest.mark.asyncio
async def test_active_child_nested_pause_passes_through_finalize():
    router = _make_router()
    mem = _seed_stack()
    child_state = _fake_state(
        {
            "status": "awaiting_input",
            "output": {"status": "awaiting_input", "sub_agent": {"message": "Which city?"}},
            "state": {"output": {"status": "awaiting_input", "sub_agent": {"message": "Which city?"}}},
        }
    )
    with (
        patch.object(ConversationMemory, "get_instance", return_value=mem),
        patch(f"{_ORCH}.run_child_turn", AsyncMock(return_value=child_state)),
    ):
        result = await router.route_turn("a reply", "t1", {"message": "a reply"}, persist=True)
    assert result["status"] == "success"
    assert result["output"] == {"message": "Which city?"}


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
        node_outputs={"child": {"message": "child done", "steps": [{"i": 1}], "tools_used": ["search"]}},
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
    resume = kwargs["input_data"]["__sub_agent_resume"]
    assert resume["child_result"] == "child done"
    assert resume["child_steps"] == [{"i": 1}]
    assert resume["child_tools_used"] == ["search"]
    assert mem.metadata[sub_session.STACK_KEY] is None


@pytest.mark.asyncio
async def test_resume_turn_forwards_session_to_child():
    router = _make_router()
    mem = _seed_stack()
    child_state = _fake_state({"status": "success", "output": {"message": "ok"}}, last_output={"message": "ok"})
    run_child = AsyncMock(return_value=child_state)
    with (
        patch.object(ConversationMemory, "get_instance", return_value=mem),
        patch(f"{_ORCH}.run_child_turn", run_child),
    ):
        await router.route_turn(
            "a reply", "t1", {"message": "a reply", "session": {"customer_name": "Ada"}}, persist=True
        )
    assert run_child.await_args.kwargs["session"] == {"customer_name": "Ada"}


@pytest.mark.asyncio
async def test_completed_child_discards_child_memory():
    router = _make_router()
    mem = _seed_stack()
    child_state = SimpleNamespace(
        sub_agent_control={"result": "child done"},
        get_last_node_output=lambda: {"message": "child done"},
        node_outputs={"child": {"message": "child done"}},
    )
    router.workflow_engine.execute_from_node = AsyncMock(
        return_value=_fake_state({"status": "success", "output": {"message": "parent final"}})
    )
    with (
        patch.object(ConversationMemory, "get_instance", return_value=mem),
        patch(f"{_ORCH}.run_child_turn", AsyncMock(return_value=child_state)),
        patch(f"{_ORCH}.discard_child_memory") as discard,
    ):
        await router.route_turn("a reply", "t1", {"message": "a reply"}, persist=True)
    discard.assert_called_once_with("t1", "child", "inv1")


@pytest.mark.asyncio
async def test_resume_passes_one_usage_context_to_child_and_parent():
    router = _make_router()
    mem = _seed_stack()
    context = SimpleNamespace(source="chat")
    child_state = SimpleNamespace(
        sub_agent_control={"result": "child done"},
        get_last_node_output=lambda: {"message": "child done"},
        node_outputs={"child": {"message": "child done"}},
    )
    router.workflow_engine.execute_from_node = AsyncMock(
        return_value=_fake_state({"status": "success", "output": {"message": "parent final"}})
    )
    run_child = AsyncMock(return_value=child_state)
    with (
        patch.object(ConversationMemory, "get_instance", return_value=mem),
        patch(f"{_ORCH}.run_child_turn", run_child),
    ):
        await router.route_turn("a reply", "t1", {"message": "a reply"}, persist=True, usage_context=context)

    run_child.assert_awaited_once()
    assert run_child.await_args.kwargs["usage_context"] is context
    assert "usage_sink" not in run_child.await_args.kwargs
    router.workflow_engine.execute_from_node.assert_awaited_once()
    assert router.workflow_engine.execute_from_node.await_args.kwargs["usage_context"] is context


@pytest.mark.asyncio
async def test_child_still_awaiting_does_not_resume_the_parent():
    router = _make_router()
    mem = _seed_stack()
    child_state = _fake_state(
        {"status": "success", "output": {"message": "need more"}}, last_output={"message": "need more"}
    )
    router.workflow_engine.execute_from_node = AsyncMock()
    run_child = AsyncMock(return_value=child_state)
    with (
        patch.object(ConversationMemory, "get_instance", return_value=mem),
        patch(f"{_ORCH}.run_child_turn", run_child),
    ):
        await router.route_turn("a reply", "t1", {"message": "a reply"}, persist=True, usage_context=SimpleNamespace())

    run_child.assert_awaited_once()
    router.workflow_engine.execute_from_node.assert_not_awaited()


_CHILD_DIAG = {"requested": True, "applied": False}


def _completed_child_state(**extra):
    return SimpleNamespace(
        sub_agent_control={"result": "child done"},
        get_last_node_output=lambda: {"message": "child done"},
        node_outputs={"child": {"message": "child done"}},
        node_execution_status={},
        prompt_caching_diagnostics={},
        **extra,
    )


async def _resume_with(child_state, parent_state):
    router = _make_router()
    router.workflow_engine.execute_from_node = AsyncMock(return_value=parent_state)
    with (
        patch.object(ConversationMemory, "get_instance", return_value=_seed_stack()),
        patch(f"{_ORCH}.run_child_turn", AsyncMock(return_value=child_state)),
    ):
        await router.route_turn("a reply", "t1", {"message": "a reply"}, persist=True)
    return parent_state


def _fresh_parent_state():
    state = _fake_state({"status": "success", "output": {"message": "parent final"}})
    state.node_execution_status = {"parent": {"status": "success"}}
    state.prompt_caching_diagnostics = {}
    return state


@pytest.mark.asyncio
async def test_completion_turn_carries_the_child_diagnostic_to_the_fresh_parent():
    child = _completed_child_state()
    child.node_execution_status = {"child": {"status": "success"}}
    child.prompt_caching_diagnostics = {"child": _CHILD_DIAG}

    parent = await _resume_with(child, _fresh_parent_state())

    assert parent.prompt_caching_diagnostics == {"child": _CHILD_DIAG}
    assert parent.node_execution_status == {"parent": {"status": "success"}}


@pytest.mark.asyncio
async def test_a_completion_turn_without_diagnostics_stays_empty():
    parent = await _resume_with(_completed_child_state(), _fresh_parent_state())

    assert parent.prompt_caching_diagnostics == {}


@pytest.mark.asyncio
async def test_a_mid_conversation_turn_returns_the_childs_own_response():
    router = _make_router()
    router.workflow_engine.execute_from_node = AsyncMock()
    child = SimpleNamespace(
        sub_agent_control=None,
        get_last_node_output=lambda: {"message": "still working"},
        format_state_as_response=lambda: {
            "status": "success",
            "output": {"message": "still working"},
            "state": {"nodeExecutionStatus": {"child": {"prompt_caching": _CHILD_DIAG}}},
        },
    )
    with (
        patch.object(ConversationMemory, "get_instance", return_value=_seed_stack()),
        patch(f"{_ORCH}.run_child_turn", AsyncMock(return_value=child)),
    ):
        result = await router.route_turn("a reply", "t1", {"message": "a reply"}, persist=True)

    router.workflow_engine.execute_from_node.assert_not_awaited()
    assert result["state"]["nodeExecutionStatus"]["child"]["prompt_caching"] == _CHILD_DIAG
