"""RegistryItem sub-agent routing: HITL precedence, frame route, resume, stale, finalize"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.core.exceptions.exception_classes import AppException
from app.modules.workflow.agents.memory import ConversationMemory, InMemoryConversationMemory
from app.modules.workflow.agents.sub_agents import graph as sub_graph
from app.modules.workflow.agents.sub_agents import session as sub_session
from app.modules.workflow.agents.sub_agents.models import SubAgentFrame, SubAgentStack
from app.modules.workflow.registry import RegistryItem

_ORCH = "app.modules.workflow.agents.sub_agents.orchestrator"

_NODES = [
    {"id": "parent", "type": "agentNode", "data": {}},
    {"id": "child", "type": "subAgentNode", "data": {"name": "child", "mode": "task"}},
]
_EDGES = [
    {"source": "child", "target": "parent", "sourceHandle": "output_sub_agent", "targetHandle": "input_sub_agents"}
]


def _make_item(nodes=_NODES, edges=_EDGES):
    workflow = {"id": "wf1", "nodes": nodes, "edges": edges}
    agent = SimpleNamespace(id="agentA", name="A", workflow=SimpleNamespace(to_dict=lambda: workflow))
    return RegistryItem(agent)


def _fake_state(response, last_output=None):
    return SimpleNamespace(
        format_state_as_response=lambda: response,
        get_last_node_output=lambda: last_output,
    )


def _seed_stack(mode="task", fingerprint=None):
    mem = InMemoryConversationMemory("t1")
    frame = SubAgentFrame(
        child_node_id="child",
        parent_node_id="parent",
        workflow_id="wf1",
        invocation_id="inv1",
        mode=mode,
        task="do x",
        workflow_fingerprint=fingerprint if fingerprint is not None else sub_graph.fingerprint(_NODES, _EDGES),
    )
    mem.metadata[sub_session.STACK_KEY] = SubAgentStack(agent_id="agentA", frames=[frame]).model_dump()
    return mem


@pytest.mark.asyncio
async def test_hitl_metadata_bypasses_frame_routing():
    item = _make_item()
    item.workflow_engine.execute_from_node = AsyncMock(
        return_value=_fake_state({"status": "success", "output": {"message": "ok"}})
    )
    with patch.object(ConversationMemory, "get_instance") as get_inst:
        await item.execute("msg", {"thread_id": "t1", "human_in_the_loop_node_id": "hitl1"})
    get_inst.assert_not_called()
    _, kwargs = item.workflow_engine.execute_from_node.call_args
    assert kwargs["start_node_id"] == "hitl1"
    assert kwargs["registry_managed"] is True


@pytest.mark.asyncio
async def test_no_frame_runs_root_flow():
    item = _make_item()
    item.workflow_engine.execute_from_node = AsyncMock(
        return_value=_fake_state({"status": "success", "output": {"message": "root"}})
    )
    with patch.object(ConversationMemory, "get_instance", return_value=InMemoryConversationMemory("t1")):
        result = await item.execute("msg", {"thread_id": "t1"})
    assert result["output"]["message"] == "root"
    item.workflow_engine.execute_from_node.assert_awaited_once()


@pytest.mark.asyncio
async def test_missing_thread_id_skips_frame_path():
    item = _make_item()
    item.workflow_engine.execute_from_node = AsyncMock(
        return_value=_fake_state({"status": "success", "output": {"message": "root"}})
    )
    with patch.object(ConversationMemory, "get_instance") as get_inst:
        await item.execute("msg", {})
    get_inst.assert_not_called()


@pytest.mark.asyncio
async def test_active_child_turn_returns_success_message():
    item = _make_item()
    mem = _seed_stack()
    child_state = _fake_state(
        {"status": "success", "output": {"message": "Is a layover okay?"}},
        last_output={"message": "Is a layover okay?"},
    )
    with (
        patch.object(ConversationMemory, "get_instance", return_value=mem),
        patch(f"{_ORCH}.run_child_turn", AsyncMock(return_value=child_state)),
    ):
        result = await item.execute("a reply", {"thread_id": "t1"})
    assert result["status"] == "success"
    assert result["output"]["message"] == "Is a layover okay?"


@pytest.mark.asyncio
async def test_resume_child_timeout_returns_controlled_message_and_keeps_frame():
    item = _make_item()
    mem = _seed_stack()
    with (
        patch.object(ConversationMemory, "get_instance", return_value=mem),
        patch(f"{_ORCH}.run_child_turn", AsyncMock(side_effect=asyncio.TimeoutError())),
    ):
        result = await item.execute("a reply", {"thread_id": "t1"})
    assert result["status"] == "success"
    assert "did not respond in time" in result["output"]["message"]
    assert mem.metadata[sub_session.STACK_KEY]["frames"][0]["invocation_id"] == "inv1"


@pytest.mark.asyncio
async def test_resume_child_error_returns_controlled_message_and_keeps_frame():
    item = _make_item()
    mem = _seed_stack()
    with (
        patch.object(ConversationMemory, "get_instance", return_value=mem),
        patch(f"{_ORCH}.run_child_turn", AsyncMock(side_effect=RuntimeError("db exploded"))),
    ):
        result = await item.execute("a reply", {"thread_id": "t1"})
    assert result["status"] == "success"
    assert "could not complete the task" in result["output"]["message"]
    assert "db exploded" not in result["output"]["message"]
    assert mem.metadata[sub_session.STACK_KEY]["frames"][0]["invocation_id"] == "inv1"


@pytest.mark.asyncio
async def test_completed_child_pops_frame_and_reenters_parent():
    item = _make_item()
    mem = _seed_stack()
    child_state = SimpleNamespace(
        sub_agent_control={"result": "child done"},
        get_last_node_output=lambda: {"message": "child done"},
    )
    item.workflow_engine.execute_from_node = AsyncMock(
        return_value=_fake_state({"status": "success", "output": {"message": "parent final"}})
    )
    with (
        patch.object(ConversationMemory, "get_instance", return_value=mem),
        patch(f"{_ORCH}.run_child_turn", AsyncMock(return_value=child_state)),
    ):
        result = await item.execute("a reply", {"thread_id": "t1"})

    assert result["output"]["message"] == "parent final"
    _, kwargs = item.workflow_engine.execute_from_node.call_args
    assert kwargs["start_node_id"] == "parent"
    assert kwargs["input_data"]["__sub_agent_resume"]["child_result"] == "child done"
    assert mem.metadata[sub_session.STACK_KEY] is None


@pytest.mark.asyncio
async def test_stale_fingerprint_raises_409_and_clears():
    item = _make_item()
    mem = _seed_stack(fingerprint="stale-hash")
    with patch.object(ConversationMemory, "get_instance", return_value=mem):
        with pytest.raises(AppException) as exc:
            await item.execute("a reply", {"thread_id": "t1"})
    assert exc.value.status_code == 409
    assert mem.metadata[sub_session.STACK_KEY] is None


@pytest.mark.asyncio
async def test_unowned_frame_left_intact_and_root_runs():
    item = _make_item()
    mem = _seed_stack()
    mem.metadata[sub_session.STACK_KEY]["agent_id"] = "someone-else"
    item.workflow_engine.execute_from_node = AsyncMock(
        return_value=_fake_state({"status": "success", "output": {"message": "root"}})
    )
    with patch.object(ConversationMemory, "get_instance", return_value=mem):
        result = await item.execute("msg", {"thread_id": "t1"})
    assert result["output"]["message"] == "root"
    assert mem.metadata[sub_session.STACK_KEY]["agent_id"] == "someone-else"


def test_finalize_converts_sub_agent_pause_to_success():
    item = _make_item()
    pause = {"status": "awaiting_input", "sub_agent": {"message": "clarify?"}, "node_id": "parent"}
    response = {"status": "awaiting_input", "output": dict(pause), "state": {"output": dict(pause)}}
    finalized = item._router.finalize(response)
    assert finalized["status"] == "success"
    assert finalized["output"] == {"message": "clarify?"}
    assert finalized["state"]["output"] == {"message": "clarify?"}
    assert "sub_agent" not in finalized["state"]["output"]


def test_finalize_leaves_hitl_form_pause_untouched():
    item = _make_item()
    response = {"status": "awaiting_input", "output": {"status": "awaiting_input", "form_schema": {"fields": []}}}
    finalized = item._router.finalize(response)
    assert finalized["status"] == "awaiting_input"
    assert "form_schema" in finalized["output"]
