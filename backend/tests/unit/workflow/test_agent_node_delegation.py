"""Byte-identical output shapes for AgentNode with no sub-agents attached"""

import asyncio
import json
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.workflow.agents.agent_runtime import AgentRunResult
from app.modules.workflow.agents.memory import InMemoryConversationMemory
from app.modules.workflow.agents.sub_agents import orchestrator
from app.modules.workflow.agents.sub_agents import session as sub_session
from app.modules.workflow.agents.sub_agents.models import SubAgentFrame, SubAgentStack
from app.modules.workflow.engine.node_result import is_node_failure
from app.modules.workflow.engine.nodes.agent_node import AgentNode
from app.modules.workflow.engine.workflow_state import WorkflowPausedException, WorkflowState

_RUNTIME = "app.modules.workflow.agents.agent_runtime"
_MERGE = "app.modules.workflow.engine.llm_usage_tracking.merge_llm_usage_from_result"


def _make_node():
    state = SimpleNamespace(
        set_node_input=MagicMock(),
        workflow={"nodes": [], "edges": []},
        initial_values={},
    )
    node = AgentNode("node-1", {"type": "agentNode", "data": {"name": "Agent"}}, state)
    return node


def _patch_runtime(*, result=None, resolve_error=None):
    stack = ExitStack()

    instance = MagicMock()
    instance.invoke = AsyncMock(return_value=result or {})
    instance.cache_split_decision = (False, None)
    stack.enter_context(patch(f"{_RUNTIME}.ToolAgent", MagicMock(return_value=instance)))

    provider = MagicMock()
    if resolve_error is not None:
        provider.get_model_for_node = AsyncMock(side_effect=resolve_error)
    else:
        provider.get_model_for_node = AsyncMock(return_value="resolved-model")
    injector = MagicMock()
    injector.get.return_value = provider
    stack.enter_context(patch("app.dependencies.injector.injector", injector))

    stack.enter_context(patch(_MERGE, AsyncMock()))
    return stack, instance


_CONFIG = {"providerId": "prov-1", "type": "ToolSelector", "memory": False}


@pytest.mark.asyncio
async def test_success_shape():
    node = _make_node()
    stack, _ = _patch_runtime(result={"response": "Paris", "steps": [{"s": 1}], "tools_used": ["calc"]})
    with stack, patch.object(AgentNode, "get_connected_nodes", return_value=[]):
        output = await node.process(dict(_CONFIG))

    assert output == {"message": "Paris", "steps": [{"s": 1}], "tools_used": ["calc"]}


@pytest.mark.asyncio
async def test_agent_internal_error_shape():
    node = _make_node()
    stack, _ = _patch_runtime(result={"status": "error", "error": "boom", "steps": [], "tools_used": []})
    with stack, patch.object(AgentNode, "get_connected_nodes", return_value=[]):
        output = await node.process(dict(_CONFIG))

    failure = is_node_failure(output)
    assert failure is not None
    assert failure["error"] == "boom"
    assert failure["output"] == {
        "message": "The agent could not complete your request: boom",
        "error": "boom",
        "steps": [],
        "tools_used": [],
    }


@pytest.mark.asyncio
async def test_raised_exception_shape():
    node = _make_node()
    stack, _ = _patch_runtime(resolve_error=RuntimeError("kaboom"))
    with stack, patch.object(AgentNode, "get_connected_nodes", return_value=[]):
        output = await node.process(dict(_CONFIG))

    failure = is_node_failure(output)
    assert failure is not None
    assert failure["error"] == "kaboom"
    assert failure["output"] == {
        "message": "The agent could not complete your request: kaboom",
        "error": "kaboom",
    }


@pytest.mark.asyncio
async def test_no_response_shape():
    node = _make_node()
    stack, _ = _patch_runtime(result={"response": None})
    with stack, patch.object(AgentNode, "get_connected_nodes", return_value=[]):
        output = await node.process(dict(_CONFIG))

    assert output == {
        "message": "The agent did not return a response. Please try again or review the agent configuration.",
        "steps": [],
        "tools_used": [],
    }


@pytest.mark.asyncio
async def test_return_direct_result_flows_through_as_success():
    node = _make_node()
    stack, _ = _patch_runtime(
        result={
            "response": "direct answer",
            "return_direct": True,
            "tool": "some_tool",
            "parameters": {},
            "tools_used": ["some_tool"],
            "steps": [],
        }
    )
    with stack, patch.object(AgentNode, "get_connected_nodes", return_value=[]):
        output = await node.process(dict(_CONFIG))

    assert output == {"message": "direct answer", "steps": [], "tools_used": ["some_tool"]}


@pytest.mark.asyncio
async def test_memory_enabled_forwards_chat_history():
    node = _make_node()
    history = [{"role": "user", "content": "earlier"}]
    stack, instance = _patch_runtime(result={"response": "ok", "steps": [], "tools_used": []})
    with (
        stack,
        patch.object(AgentNode, "get_connected_nodes", return_value=[]),
        patch.object(AgentNode, "get_memory", return_value=MagicMock()),
        patch.object(AgentNode, "_get_chat_history_for_agent", AsyncMock(return_value=history)),
    ):
        await node.process({"providerId": "prov-1", "type": "ToolSelector", "memory": True})

    invoked_prompt, invoked_kwargs = instance.invoke.await_args
    assert invoked_kwargs["chat_history"] == history


# Delegation loop

_AGENT_ONCE = "app.modules.workflow.engine.nodes.agent_node.run_agent_once"
_ORCH_RUN = "app.modules.workflow.agents.sub_agents.orchestrator.run_child_turn"
_ORCH_DISCARD = "app.modules.workflow.agents.sub_agents.orchestrator.discard_child_memory"


class _Tool:
    def __init__(self, name):
        self.name = name


def _parent_node(registry_managed=True, thread_id="t-loop", initial_values=None, mode="single_turn"):
    workflow = {
        "config": {"id": "wf1"},
        "nodes": [
            {"id": "parent", "type": "agentNode", "data": {}},
            {"id": "child", "type": "subAgentNode", "data": {"name": "child", "mode": mode}},
        ],
        "edges": [
            {
                "source": "child",
                "target": "parent",
                "sourceHandle": "output_sub_agent",
                "targetHandle": "input_sub_agents",
            }
        ],
    }
    iv = initial_values if initial_values is not None else {"message": "hi", "agent_id": "agentA"}
    state = WorkflowState(workflow=workflow, thread_id=thread_id, initial_values=iv, registry_managed=registry_managed)
    state.memory = InMemoryConversationMemory(thread_id)
    state.node_execution_status["parent"] = {}
    return AgentNode("parent", {"type": "agentNode", "data": {}}, state)


def _rr(response, *, return_direct=False, tool=None, steps=None, tools_used=None, status="success", error=None):
    raw = {"response": response, "status": status}
    if return_direct:
        raw["return_direct"] = True
    if tool:
        raw["tool"] = tool
    return AgentRunResult(
        response=response,
        steps=steps or [],
        tools_used=tools_used or [],
        status=status,
        error=error,
        raw=raw,
        llm_model="m",
    )


def _env(status, message, mode="single_turn", invocation_id="inv", task="do x"):
    return orchestrator.make_envelope(
        status=status,
        message=message,
        child_node_id="child",
        mode=mode,
        invocation_id=invocation_id,
        task=task,
    )


async def _run_loop(node, results, *, delegation_map=None, all_tools=None, config=None):
    delegation_map = delegation_map or {"request_task_child": {"child_node_id": "child", "mode": "single_turn"}}
    all_tools = all_tools or [_Tool("request_task_child")]
    with patch(_AGENT_ONCE, AsyncMock(side_effect=results)) as run_once:
        out = await node._run_agent_with_delegations(
            config=config or {"piiMasking": False},
            provider_id="p",
            fallback_chain_id=None,
            agent_type="ToolSelector",
            system_prompt="s",
            prompt="q",
            all_tools=all_tools,
            delegation_map=delegation_map,
            max_iterations=7,
            chat_history=[],
        )
    return out, run_once


@pytest.mark.asyncio
async def test_single_turn_delegation_then_final_answer():
    node = _parent_node()
    results = [
        _rr(_env("completed", "child answer"), return_direct=True, tool="request_task_child"),
        _rr("final answer"),
    ]
    out, run_once = await _run_loop(node, results)
    assert out["message"] == "final answer"
    assert {"type": "sub_agent", "child_node_id": "child", "mode": "single_turn"} in out["steps"]
    assert run_once.await_count == 2


@pytest.mark.asyncio
async def test_unparsable_envelope_feeds_model_and_strips_tool():
    node = _parent_node()
    results = [
        _rr("The sub-agent could not complete the task.", return_direct=True, tool="request_task_child"),
        _rr("graceful model answer"),
    ]
    out, run_once = await _run_loop(node, results)
    assert out["message"] == "graceful model answer"
    assert run_once.await_count == 2
    second_call = run_once.await_args_list[1].kwargs
    assert "request_task_child" not in {t.name for t in second_call["tools"]}
    assert "unavailable in this context" in second_call["user_prompt"]
    assert "could not complete the task" in second_call["user_prompt"]


@pytest.mark.asyncio
async def test_guard_string_from_chat_child_becomes_model_context():
    node = _parent_node(registry_managed=False, mode="chat")
    dmap = {"request_task_child": {"child_node_id": "child", "mode": "chat"}}
    guard = "This sub-agent needs an interactive chat session and can't be used in this context."
    results = [
        _rr(guard, return_direct=True, tool="request_task_child"),
        _rr("I can help with that myself."),
    ]
    out, _ = await _run_loop(node, results, delegation_map=dmap)
    assert out["message"] == "I can help with that myself."
    assert guard not in out["message"]


@pytest.mark.asyncio
async def test_ordinary_return_direct_tool_still_returns_directly():
    node = _parent_node()
    all_tools = [_Tool("request_task_child"), _Tool("other_tool")]
    results = [_rr("direct tool result", return_direct=True, tool="other_tool")]
    out, run_once = await _run_loop(node, results, all_tools=all_tools)
    assert out["message"] == "direct tool result"
    assert run_once.await_count == 1


@pytest.mark.asyncio
async def test_active_delegation_writes_frame_then_pauses():
    node = _parent_node(mode="task")
    dmap = {"request_task_child": {"child_node_id": "child", "mode": "task"}}
    results = [
        _rr(
            _env("active", "Is a layover okay?", mode="task", invocation_id="inv9"),
            return_direct=True,
            tool="request_task_child",
        )
    ]
    with pytest.raises(WorkflowPausedException) as exc:
        await _run_loop(node, results, delegation_map=dmap)
    assert exc.value.pause_data["status"] == "awaiting_input"
    assert exc.value.pause_data["sub_agent"]["message"] == "Is a layover okay?"

    stack = await sub_session.read_frame_strict(node.get_memory())
    assert stack is not None
    top = stack.top()
    assert top.child_node_id == "child" and top.mode == "task" and top.invocation_id == "inv9"
    assert top.parent_resume is not None


@pytest.mark.asyncio
async def test_pause_frame_is_strictly_json_serializable_with_live_tools():
    node = _parent_node(mode="task")
    node.get_state().set_node_input(
        "parent", {"system_prompt": "s", "prompt": "q", "tools_reference": [_Tool("request_task_child")]}
    )
    dmap = {"request_task_child": {"child_node_id": "child", "mode": "task"}}
    results = [_rr(_env("active", "Need a date?", mode="task"), return_direct=True, tool="request_task_child")]
    with pytest.raises(WorkflowPausedException):
        await _run_loop(node, results, delegation_map=dmap)

    stored = node.get_memory().metadata[sub_session.STACK_KEY]
    json.dumps(stored)
    resume = stored["frames"][-1]["parent_resume"]
    assert "tools_reference" not in resume["node_execution_status"]["parent"]["input"]


@pytest.mark.asyncio
async def test_active_delegation_depth_limit_returns_error_without_frame():
    node = _parent_node(mode="task")
    frames = [
        SubAgentFrame(
            child_node_id="child", parent_node_id="parent", workflow_id="wf1", invocation_id=f"inv{i}", mode="task"
        )
        for i in range(3)
    ]
    await sub_session.write_frame(node.get_memory(), SubAgentStack(agent_id="agentA", frames=frames))
    dmap = {"request_task_child": {"child_node_id": "child", "mode": "task"}}
    results = [_rr(_env("active", "another question", mode="task"), return_direct=True, tool="request_task_child")]
    out, _ = await _run_loop(node, results, delegation_map=dmap)
    assert "depth limit" in out["message"].lower()
    stack = await sub_session.read_frame_strict(node.get_memory())
    assert len(stack.frames) == 3  # unchanged, no dangling frame


@pytest.mark.asyncio
async def test_resume_prepends_saved_user_prompt_context():
    resume = {
        "node_outputs": {},
        "node_execution_status": {},
        "request_context": {},
        "completed_count": 1,
        "accumulated_steps": [],
        "accumulated_tools_used": [],
        "child_node_id": "child",
        "mode": "task",
        "child_task": "task B",
        "child_result": "result B",
        "user_prompt": "PRIOR-CONTEXT-FROM-CHILD-A",
    }
    node = _parent_node(
        mode="task", initial_values={"message": "hi", "agent_id": "agentA", "__sub_agent_resume": resume}
    )
    dmap = {"request_task_child": {"child_node_id": "child", "mode": "task"}}
    _, run_once = await _run_loop(node, [_rr("final")], delegation_map=dmap)
    first_prompt = run_once.await_args_list[0].kwargs["user_prompt"]
    assert "PRIOR-CONTEXT-FROM-CHILD-A" in first_prompt
    assert "result B" in first_prompt


@pytest.mark.asyncio
async def test_resume_rehydrates_outputs_and_continues():
    resume = {
        "node_outputs": {"n1": {"x": 1}},
        "node_execution_status": {},
        "request_context": {},
        "completed_count": 0,
        "accumulated_steps": [],
        "accumulated_tools_used": [],
        "child_node_id": "child",
        "mode": "task",
        "child_task": "do x",
        "child_result": "child final result",
    }
    node = _parent_node(
        mode="task", initial_values={"message": "hi", "agent_id": "agentA", "__sub_agent_resume": resume}
    )
    dmap = {"request_task_child": {"child_node_id": "child", "mode": "task"}}
    out, _ = await _run_loop(node, [_rr("final after resume")], delegation_map=dmap)
    assert out["message"] == "final after resume"
    assert node.get_state().node_outputs.get("n1") == {"x": 1}
    assert any(s.get("type") == "sub_agent" for s in out["steps"])


@pytest.mark.asyncio
async def test_completed_child_tool_removed_after_one_call():
    node = _parent_node()
    all_tools = [_Tool("request_task_child"), _Tool("other_tool")]
    results = [
        _rr(_env("completed", "child answer"), return_direct=True, tool="request_task_child"),
        _rr("final answer"),
    ]
    out, run_once = await _run_loop(node, results, all_tools=all_tools)
    assert out["message"] == "final answer"
    assert run_once.await_count == 2
    second_tools = {t.name for t in run_once.await_args_list[1].kwargs["tools"]}
    assert "request_task_child" not in second_tools
    assert "other_tool" in second_tools


@pytest.mark.asyncio
async def test_repeated_same_child_delegation_capped_at_one():
    """The 5x5 pathology: even if the model re-emits the same delegation, only one child run happens"""
    node = _parent_node()
    results = [_rr(_env("completed", f"answer {i}"), return_direct=True, tool="request_task_child") for i in range(5)]
    out, run_once = await _run_loop(node, results)
    sub_markers = [s for s in out["steps"] if s.get("type") == "sub_agent"]
    assert len(sub_markers) == 1
    assert run_once.await_count == 2


@pytest.mark.asyncio
async def test_delegation_function_refuses_persistent_off_registry():
    node = _parent_node(registry_managed=False, thread_id="t-refuse")
    fn = node._make_delegation_function(child_id="child", mode="task", timeout_seconds=120)
    with patch(_ORCH_RUN, AsyncMock()) as run_child:
        result = await fn({"parameters": {"task": "do x"}})
    assert "interactive chat session" in result
    run_child.assert_not_called()


@pytest.mark.asyncio
async def test_delegation_function_admits_one_persistent_per_turn():
    node = _parent_node(registry_managed=True, thread_id="t-gate")
    node.get_state().sub_agent_persistent_claimed = True  # a persistent delegation already claimed
    fn = node._make_delegation_function(child_id="child", mode="chat", timeout_seconds=120)
    with patch(_ORCH_RUN, AsyncMock()) as run_child:
        result = await fn({"parameters": {"task": "do x"}})
    assert "already in progress" in result
    run_child.assert_not_called()


@pytest.mark.asyncio
async def test_delegation_depth_pre_check_blocks_before_child_runs():
    node = _parent_node(registry_managed=True, thread_id="t-depth")
    frames = [
        SubAgentFrame(
            child_node_id="child", parent_node_id="parent", workflow_id="wf1", invocation_id=f"inv{i}", mode="task"
        )
        for i in range(3)
    ]
    await sub_session.write_frame(node.get_memory(), SubAgentStack(agent_id="agentA", frames=frames))
    fn = node._make_delegation_function(child_id="child", mode="task", timeout_seconds=120)
    with patch(_ORCH_RUN, AsyncMock()) as run_child:
        result = await fn({"parameters": {"task": "do x"}})
    assert "depth limit" in result.lower()
    run_child.assert_not_called()
    assert node.get_state().sub_agent_persistent_claimed is False


@pytest.mark.asyncio
async def test_corrupt_stack_pre_check_fails_delegation_and_releases_claim():
    node = _parent_node(registry_managed=True, thread_id="t-corrupt")
    node.get_memory().metadata[sub_session.STACK_KEY] = {"version": 1, "agent_id": "agentA", "frames": "junk"}
    fn = node._make_delegation_function(child_id="child", mode="chat", timeout_seconds=120)
    with patch(_ORCH_RUN, AsyncMock()) as run_child:
        result = await fn({"parameters": {"task": "do x"}})
    assert "could not be resumed" in result
    run_child.assert_not_called()
    assert node.get_state().sub_agent_persistent_claimed is False


@pytest.mark.asyncio
async def test_claim_flag_reset_after_synchronous_completion():
    node = _parent_node(mode="task")
    node.get_state().sub_agent_persistent_claimed = True  # as the delegation tool would set it
    dmap = {"request_task_child": {"child_node_id": "child", "mode": "task"}}
    results = [
        _rr(_env("completed", "done", mode="task"), return_direct=True, tool="request_task_child"),
        _rr("final"),
    ]
    out, _ = await _run_loop(node, results, delegation_map=dmap)
    assert out["message"] == "final"
    assert node.get_state().sub_agent_persistent_claimed is False


@pytest.mark.asyncio
async def test_timed_out_persistent_delegation_releases_claim():
    node = _parent_node(registry_managed=True, thread_id="t-timeout", mode="task")
    fn = node._make_delegation_function(child_id="child", mode="task", timeout_seconds=1)
    with patch(_ORCH_RUN, AsyncMock(side_effect=asyncio.TimeoutError())):
        result = await fn({"parameters": {"task": "do x"}})
    assert "did not respond in time" in result
    assert node.get_state().sub_agent_persistent_claimed is False


@pytest.mark.asyncio
async def test_failed_persistent_delegation_releases_claim():
    node = _parent_node(registry_managed=True, thread_id="t-fail", mode="chat")
    fn = node._make_delegation_function(child_id="child", mode="chat", timeout_seconds=120)
    with patch(_ORCH_RUN, AsyncMock(side_effect=RuntimeError("db exploded"))):
        result = await fn({"parameters": {"task": "do x"}})
    assert "could not complete the task" in result
    assert node.get_state().sub_agent_persistent_claimed is False


@pytest.mark.asyncio
async def test_completed_delegation_discards_child_memory():
    node = _parent_node(thread_id="t-evict")
    child_state = SimpleNamespace(
        get_node_output=lambda cid: None,
        get_last_node_output=lambda: {"message": "child answer"},
        sub_agent_control=None,
    )
    fn = node._make_delegation_function(child_id="child", mode="single_turn", timeout_seconds=120)
    with (
        patch(_ORCH_RUN, AsyncMock(return_value=child_state)),
        patch(_ORCH_DISCARD) as discard,
    ):
        result = await fn({"parameters": {"task": "do x"}})
    assert orchestrator.parse_envelope(result)["status"] == "completed"
    discard.assert_called_once()
    assert discard.call_args.args[:2] == ("t-evict", "child")


@pytest.mark.asyncio
async def test_failed_delegation_discards_child_memory():
    node = _parent_node(thread_id="t-evict-fail")
    fn = node._make_delegation_function(child_id="child", mode="single_turn", timeout_seconds=1)
    with (
        patch(_ORCH_RUN, AsyncMock(side_effect=asyncio.TimeoutError())),
        patch(_ORCH_DISCARD) as discard,
    ):
        await fn({"parameters": {"task": "do x"}})
    discard.assert_called_once()
    assert discard.call_args.args[:2] == ("t-evict-fail", "child")


@pytest.mark.asyncio
async def test_corrupt_stack_on_pause_fails_delegation_without_overwrite():
    node = _parent_node(mode="task")
    corrupt = {"version": 1, "agent_id": "agentA", "frames": "junk"}
    node.get_memory().metadata[sub_session.STACK_KEY] = dict(corrupt)
    dmap = {"request_task_child": {"child_node_id": "child", "mode": "task"}}
    results = [_rr(_env("active", "a question?", mode="task"), return_direct=True, tool="request_task_child")]
    out, _ = await _run_loop(node, results, delegation_map=dmap)
    assert "could not be resumed" in out["message"]
    assert node.get_memory().metadata[sub_session.STACK_KEY] == corrupt


@pytest.mark.asyncio
async def test_delegation_folds_only_child_output_not_session_or_path():
    node = _parent_node()
    child = WorkflowState(workflow={"nodes": [], "edges": []}, thread_id="t-child", initial_values={})
    child.set_node_output("child", {"message": "child answer", "steps": [{"a": 1}], "tools_used": ["t"]})
    child.llm_usage = [{"input_tokens": 5, "output_tokens": 7}]
    child.update_session_value("child_only_key", "x")
    fn = node._make_delegation_function(child_id="child", mode="single_turn", timeout_seconds=120)
    with patch(_ORCH_RUN, AsyncMock(return_value=child)):
        result = await fn({"parameters": {"task": "do x"}})

    parent = node.get_state()
    assert parent.node_outputs["child"]["message"] == "child answer"
    assert parent.llm_usage == []
    assert parent.execution_path == []
    assert "child_only_key" not in parent.get_session()
    assert orchestrator.parse_envelope(result)["status"] == "completed"


@pytest.mark.asyncio
async def test_in_turn_marker_carries_child_trace():
    node = _parent_node()
    node.get_state().node_outputs["child"] = {
        "message": "done",
        "steps": [{"i": 1}, {"i": 2}],
        "tools_used": ["search"],
    }
    results = [
        _rr(_env("completed", "child answer"), return_direct=True, tool="request_task_child"),
        _rr("final answer"),
    ]
    out, _ = await _run_loop(node, results)
    marker = next(s for s in out["steps"] if s.get("type") == "sub_agent")
    assert marker["child_steps"] == [{"i": 1}, {"i": 2}]
    assert marker["child_tools_used"] == ["search"]


@pytest.mark.asyncio
async def test_in_turn_marker_caps_child_trace():
    node = _parent_node()
    node.get_state().node_outputs["child"] = {
        "steps": [{"i": i} for i in range(35)],
        "tools_used": [f"t{i}" for i in range(35)],
    }
    results = [
        _rr(_env("completed", "child answer"), return_direct=True, tool="request_task_child"),
        _rr("final answer"),
    ]
    out, _ = await _run_loop(node, results)
    marker = next(s for s in out["steps"] if s.get("type") == "sub_agent")
    assert len(marker["child_steps"]) == 30
    assert marker["child_steps"][0] == {"i": 5}
    assert len(marker["child_tools_used"]) == 30


@pytest.mark.asyncio
async def test_resume_does_not_reoffer_completed_child_tool():
    resume = {
        "node_outputs": {},
        "node_execution_status": {},
        "request_context": {},
        "completed_count": 1,
        "accumulated_steps": [],
        "accumulated_tools_used": [],
        "child_node_id": "child",
        "mode": "task",
        "child_task": "do x",
        "child_result": "child result",
    }
    node = _parent_node(
        mode="task", initial_values={"message": "hi", "agent_id": "agentA", "__sub_agent_resume": resume}
    )
    dmap = {"request_task_child": {"child_node_id": "child", "mode": "task"}}
    results = [_rr(_env("completed", "again", mode="task"), return_direct=True, tool="request_task_child")]
    out, run_once = await _run_loop(node, results, delegation_map=dmap)
    first_tools = {t.name for t in run_once.await_args_list[0].kwargs["tools"]}
    assert "request_task_child" not in first_tools
    assert run_once.await_count == 1
    sub_markers = [s for s in out["steps"] if s.get("type") == "sub_agent"]
    assert len(sub_markers) == 1


@pytest.mark.asyncio
async def test_resume_marker_carries_child_trace_from_resume_dict():
    resume = {
        "node_outputs": {},
        "node_execution_status": {},
        "request_context": {},
        "completed_count": 0,
        "accumulated_steps": [],
        "accumulated_tools_used": [],
        "child_node_id": "child",
        "mode": "task",
        "child_task": "do x",
        "child_result": "child final result",
        "child_steps": [{"i": 1}],
        "child_tools_used": ["search"],
    }
    node = _parent_node(
        mode="task", initial_values={"message": "hi", "agent_id": "agentA", "__sub_agent_resume": resume}
    )
    dmap = {"request_task_child": {"child_node_id": "child", "mode": "task"}}
    out, _ = await _run_loop(node, [_rr("final after resume")], delegation_map=dmap)
    marker = next(s for s in out["steps"] if s.get("type") == "sub_agent")
    assert marker["child_steps"] == [{"i": 1}]
    assert marker["child_tools_used"] == ["search"]


def test_pii_wrapped_tool_receives_original_values():
    node = _parent_node(thread_id="t-pii")
    node._pii_prompt_token_items = [
        {"token": "johndoe1@example.com", "original": "alice@example.com", "entity_type": "EMAIL_ADDRESS"}
    ]
    seen = {}

    class _CapturingTool:
        name = "request_task_child"

        def invoke(self, **kwargs):
            seen.update(kwargs)
            return "ok"

    tool = _CapturingTool()
    node._wrap_tools_for_pii_unmask([tool])
    tool.invoke(task="Email johndoe1@example.com the itinerary")
    assert seen["task"] == "Email alice@example.com the itinerary"


def test_capture_resume_context_drops_sub_agent_resume_marker():
    from app.modules.workflow.agents.sub_agents.models import SUB_AGENT_RESUME_KEY

    node = _parent_node(
        initial_values={"message": "hi", "agent_id": "a", SUB_AGENT_RESUME_KEY: {"child_result": "prev"}}
    )
    ctx = node.get_state().capture_resume_context()
    assert SUB_AGENT_RESUME_KEY not in ctx["initial_values"]
    assert ctx["initial_values"]["message"] == "hi"


@pytest.mark.asyncio
async def test_pause_frame_does_not_nest_prior_resume_marker():
    from app.modules.workflow.agents.sub_agents.models import SUB_AGENT_RESUME_KEY

    node = _parent_node(
        mode="task",
        initial_values={"message": "hi", "agent_id": "agentA", SUB_AGENT_RESUME_KEY: {"child_result": "prev"}},
    )
    dmap = {"request_task_child": {"child_node_id": "child", "mode": "task"}}
    results = [
        _rr(_env("active", "another?", mode="task", invocation_id="inv2"), return_direct=True, tool="request_task_child")
    ]
    with pytest.raises(WorkflowPausedException):
        await _run_loop(node, results, delegation_map=dmap)

    stack = await sub_session.read_frame_strict(node.get_memory())
    captured = stack.top().parent_resume.request_context.get("initial_values", {})
    assert SUB_AGENT_RESUME_KEY not in captured


_CHILD_DIAG = {"requested": True, "applied": False}
_DIAG_KEY = "__prompt_caching_diagnostics"


def _child_state_with_diagnostic(node_id="child", diagnostic=None):
    return SimpleNamespace(
        get_node_output=lambda _id: {"message": "child answer"},
        get_last_node_output=lambda: {"message": "child answer"},
        node_execution_status={node_id: {"status": "success"}},
        prompt_caching_diagnostics={node_id: diagnostic or _CHILD_DIAG},
        sub_agent_control={"result": "child answer"},
        get_memory=MagicMock(return_value=MagicMock(add_input_output=AsyncMock())),
    )


async def _delegate_once(node, child_state):
    fn = node._make_delegation_function(child_id="child", mode="single_turn", timeout_seconds=120)
    with patch(_ORCH_RUN, AsyncMock(return_value=child_state)), patch(_ORCH_DISCARD, MagicMock()):
        return await fn({"parameters": {"task": "do x"}})


@pytest.mark.asyncio
async def test_in_turn_delegation_lands_the_child_diagnostic_in_the_parent_collection():
    node = _parent_node(thread_id="t-diag")
    await _delegate_once(node, _child_state_with_diagnostic())

    assert node.get_state().prompt_caching_diagnostics == {"child": _CHILD_DIAG}


@pytest.mark.asyncio
async def test_the_parents_execution_map_never_gains_the_child():
    node = _parent_node(thread_id="t-diag-map")
    await _delegate_once(node, _child_state_with_diagnostic())

    assert set(node.get_state().node_execution_status) == {"parent"}


@pytest.mark.asyncio
async def test_nested_diagnostics_chain_up_through_the_delegation():
    node = _parent_node(thread_id="t-diag-nested")
    child = _child_state_with_diagnostic()
    child.prompt_caching_diagnostics["grandchild"] = {"requested": True, "applied": True}
    await _delegate_once(node, child)

    assert set(node.get_state().prompt_caching_diagnostics) == {"child", "grandchild"}


@pytest.mark.asyncio
async def test_a_child_without_a_diagnostic_leaves_the_collection_empty():
    node = _parent_node(thread_id="t-diag-none")
    child = _child_state_with_diagnostic()
    child.prompt_caching_diagnostics = {}
    await _delegate_once(node, child)

    assert node.get_state().prompt_caching_diagnostics == {}


async def _pause_after_delegating(node, *, seed_diagnostics=None):
    if seed_diagnostics:
        node.get_state().prompt_caching_diagnostics.update(seed_diagnostics)
    dmap = {"request_task_child": {"child_node_id": "child", "mode": "task"}}
    results = [_rr(_env("active", "a question", mode="task", invocation_id="inv9"),
                   return_direct=True, tool="request_task_child")]
    with pytest.raises(WorkflowPausedException):
        await _run_loop(node, results, delegation_map=dmap)
    stack = await sub_session.read_frame_strict(node.get_memory())
    return stack.top().parent_resume.request_context


@pytest.mark.asyncio
async def test_a_pause_carries_an_earlier_childs_diagnostic_in_the_frame():
    context = await _pause_after_delegating(_parent_node(mode="task"), seed_diagnostics={"child-a": _CHILD_DIAG})

    assert context[_DIAG_KEY] == {"child-a": _CHILD_DIAG}


@pytest.mark.asyncio
async def test_a_pause_with_no_diagnostics_writes_a_frame_identical_to_before():
    context = await _pause_after_delegating(_parent_node(mode="task"))

    assert _DIAG_KEY not in context
    assert set(context) == {"initial_values", "session"}


@pytest.mark.asyncio
async def test_the_resume_merges_the_carried_diagnostics_back():
    resume = {
        "node_outputs": {},
        "node_execution_status": {},
        "request_context": {"initial_values": {}, "session": {}, _DIAG_KEY: {"child-a": _CHILD_DIAG}},
        "completed_count": 1,
        "accumulated_steps": [],
        "accumulated_tools_used": [],
        "child_node_id": "child",
        "mode": "task",
        "child_task": "task B",
        "child_result": "result B",
    }
    node = _parent_node(
        mode="task", initial_values={"message": "hi", "agent_id": "agentA", "__sub_agent_resume": resume}
    )
    dmap = {"request_task_child": {"child_node_id": "child", "mode": "task"}}
    await _run_loop(node, [_rr("final")], delegation_map=dmap)

    assert node.get_state().prompt_caching_diagnostics == {"child-a": _CHILD_DIAG}
    assert _DIAG_KEY not in node.get_state().session


@pytest.mark.asyncio
async def test_an_old_frame_without_the_key_resumes_with_an_empty_collection():
    resume = {
        "node_outputs": {},
        "node_execution_status": {},
        "request_context": {"initial_values": {}, "session": {}},
        "completed_count": 1,
        "accumulated_steps": [],
        "accumulated_tools_used": [],
        "child_node_id": "child",
        "mode": "task",
        "child_task": "task B",
        "child_result": "result B",
    }
    node = _parent_node(
        mode="task", initial_values={"message": "hi", "agent_id": "agentA", "__sub_agent_resume": resume}
    )
    dmap = {"request_task_child": {"child_node_id": "child", "mode": "task"}}
    await _run_loop(node, [_rr("final")], delegation_map=dmap)

    assert node.get_state().prompt_caching_diagnostics == {}


@pytest.mark.asyncio
async def test_a_new_frame_still_validates_and_restores_on_an_old_build():
    node = _parent_node(mode="task")
    context = await _pause_after_delegating(node, seed_diagnostics={"child-a": _CHILD_DIAG})

    stored = node.get_memory().metadata[sub_session.STACK_KEY]
    json.dumps(stored)
    assert SubAgentStack.model_validate(stored).top().parent_resume.request_context[_DIAG_KEY]

    fresh = _parent_node(mode="task", thread_id="t-old-pod")
    fresh.get_state().restore_resume_context(context, drop_keys={"message"})

    assert _DIAG_KEY not in fresh.get_state().session
    assert _DIAG_KEY not in fresh.get_state().initial_values
