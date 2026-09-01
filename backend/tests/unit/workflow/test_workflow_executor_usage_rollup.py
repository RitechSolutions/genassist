"""Child-workflow LLM usage rolls up under the Workflow Executor node that ran it"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.workflow.engine.node_result import is_node_failure
from app.modules.workflow.engine.nodes.workflow_executor_node import WorkflowExecutorNode
from app.modules.workflow.engine.workflow_engine import WorkflowEngine
from app.modules.workflow.engine.workflow_state import WorkflowState

PARENT_WF = {"config": {"id": "parent-wf"}, "nodes": [], "edges": []}
CHILD_WF = {"config": {"id": "child-wf"}, "nodes": [], "edges": []}
THREAD = "11111111-1111-1111-1111-111111111111"
CHILD_WORKFLOW_ID = "22222222-2222-2222-2222-222222222222"
CONFIG = {"workflowId": CHILD_WORKFLOW_ID, "inputParameters": {"threadId": THREAD}}


def _entry(node_id="child-n1", **overrides):
    entry = {
        "input_tokens": 40,
        "output_tokens": 12,
        "total_tokens": 52,
        "provider": "openai",
        "model": "gpt-4o",
        "node_id": node_id,
        "purpose": "llm_model",
        "token_details": {"cache_read": 8},
        "llm_provider_id": "pid-1",
    }
    entry.update(overrides)
    return entry


def _state(workflow=PARENT_WF) -> WorkflowState:
    return WorkflowState(workflow=workflow, thread_id=THREAD, initial_values={})


def _node(state, node_id="exec-1") -> WorkflowExecutorNode:
    return WorkflowExecutorNode(node_id, {"type": "workflowExecutorNode", "data": {}}, state)


def _patch_workflow_service():
    workflow = MagicMock()
    workflow.id = CHILD_WORKFLOW_ID
    workflow.name = "Child flow"
    workflow.nodes = []
    workflow.edges = []
    service = MagicMock()
    service.get_by_id = AsyncMock(return_value=workflow)
    inj = MagicMock()
    inj.get = MagicMock(return_value=service)
    return patch("app.dependencies.injector.injector", inj)


def _patch_engine(entries, error=None, child_diagnostics=None):

    async def _execute(self, *, usage_sink=None, **kwargs):
        if usage_sink is not None:
            usage_sink.extend(entries)
        if error is not None:
            raise error
        child = _state(CHILD_WF)
        if child_diagnostics:
            child.prompt_caching_diagnostics = child_diagnostics
        return child

    return patch.object(WorkflowEngine, "execute_from_node", _execute)


@pytest.mark.asyncio
async def test_success_remaps_child_node_ids_to_the_executor():
    state = _state()
    entries = [_entry("child-n1"), _entry("child-n2", purpose="smart_route")]

    with _patch_workflow_service(), _patch_engine(entries):
        result = await _node(state).process(CONFIG)

    assert result["status"] == "success"
    assert [u["node_id"] for u in state.llm_usage] == ["exec-1", "exec-1"]


@pytest.mark.asyncio
async def test_only_the_node_id_changes():
    state = _state()
    entries = [_entry("child-n1")]

    with _patch_workflow_service(), _patch_engine(entries):
        await _node(state).process(CONFIG)

    rolled_up = state.llm_usage[0]
    assert rolled_up.keys() == entries[0].keys()
    assert {k: v for k, v in rolled_up.items() if k != "node_id"} == {
        k: v for k, v in entries[0].items() if k != "node_id"
    }


@pytest.mark.asyncio
async def test_totals_survive_the_remap():
    state = _state()
    entries = [_entry("child-n1"), _entry("child-n2", input_tokens=5, output_tokens=1, total_tokens=6)]

    with _patch_workflow_service(), _patch_engine(entries):
        await _node(state).process(CONFIG)

    for field in ("input_tokens", "output_tokens", "total_tokens"):
        assert sum(u[field] for u in state.llm_usage) == sum(e[field] for e in entries)


@pytest.mark.asyncio
async def test_child_raise_still_rolls_usage_up():
    state = _state()
    entries = [_entry("child-n1")]

    with _patch_workflow_service(), _patch_engine(entries, error=RuntimeError("child exploded")):
        result = await _node(state).process(CONFIG)

    assert is_node_failure(result)
    assert [u["node_id"] for u in state.llm_usage] == ["exec-1"]


@pytest.mark.asyncio
async def test_child_cancellation_still_rolls_usage_up():
    state = _state()
    entries = [_entry("child-n1")]

    with _patch_workflow_service(), _patch_engine(entries, error=asyncio.CancelledError()):
        with pytest.raises(asyncio.CancelledError):
            await _node(state).process(CONFIG)

    assert [u["node_id"] for u in state.llm_usage] == ["exec-1"]


@pytest.mark.asyncio
async def test_child_entries_are_copied_not_aliased():
    state = _state()
    entries = [_entry("child-n1")]

    with _patch_workflow_service(), _patch_engine(entries):
        await _node(state).process(CONFIG)

    assert state.llm_usage[0] is not entries[0]
    assert entries[0]["node_id"] == "child-n1"


@pytest.mark.asyncio
async def test_child_caching_diagnostics_collapse_onto_the_executor():
    state = _state()
    diagnostics = {
        "child-n1": {"requested": True, "applied": True},
        "child-n2": {"requested": True, "applied": False},
    }

    with _patch_workflow_service(), _patch_engine([_entry("child-n1")], child_diagnostics=diagnostics):
        await _node(state).process(CONFIG)

    assert state.prompt_caching_diagnostics == {"exec-1": {"requested": True, "applied": True}}


@pytest.mark.asyncio
async def test_an_all_withheld_child_still_surfaces_a_withheld_entry():
    state = _state()
    diagnostics = {"child-n1": {"requested": True, "applied": False}}

    with _patch_workflow_service(), _patch_engine([_entry("child-n1")], child_diagnostics=diagnostics):
        await _node(state).process(CONFIG)

    assert state.prompt_caching_diagnostics == {"exec-1": {"requested": True, "applied": False}}


@pytest.mark.asyncio
async def test_a_child_without_diagnostics_leaves_none_on_the_executor():
    state = _state()

    with _patch_workflow_service(), _patch_engine([_entry("child-n1")]):
        await _node(state).process(CONFIG)

    assert state.prompt_caching_diagnostics == {}


@pytest.mark.asyncio
async def test_nested_executors_roll_up_to_the_outermost_node():
    child_state = _state(CHILD_WF)
    with _patch_workflow_service(), _patch_engine([_entry("grandchild-n1")]):
        await _node(child_state, "inner-1").process(CONFIG)
    assert [u["node_id"] for u in child_state.llm_usage] == ["inner-1"]

    parent_state = _state()
    with _patch_workflow_service(), _patch_engine(child_state.llm_usage):
        await _node(parent_state, "outer-1").process(CONFIG)

    assert [u["node_id"] for u in parent_state.llm_usage] == ["outer-1"]
    assert [u["node_id"] for u in child_state.llm_usage] == ["inner-1"]
