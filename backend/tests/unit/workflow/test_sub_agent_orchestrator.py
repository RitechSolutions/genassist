"""Child-engine orchestration: derived thread, persist=False, durable history, timeout"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi_injector import RequestScopeFactory
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.workflow.agents.sub_agents import orchestrator

_ORCH = "app.modules.workflow.agents.sub_agents.orchestrator"


class _FakeScope:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False


def _fake_child_state(message="child says hi"):
    state = MagicMock()
    state.get_last_node_output.return_value = {"message": message, "steps": [], "tools_used": []}
    state.get_memory.return_value = MagicMock(add_input_output=AsyncMock())
    return state


def _patch_env(child_state, *, wait_for=None):
    from contextlib import ExitStack

    stack = ExitStack()

    engine = MagicMock()
    engine.execute_from_node = AsyncMock(return_value=child_state)
    engine_cls = MagicMock(return_value=engine)
    stack.enter_context(patch("app.modules.workflow.engine.workflow_engine.WorkflowEngine", engine_cls))

    session = MagicMock(close=AsyncMock())
    factory = MagicMock(create_scope=MagicMock(return_value=_FakeScope()))

    def _get(dep):
        if dep is RequestScopeFactory:
            return factory
        if dep is AsyncSession:
            return session
        return MagicMock()

    injector = MagicMock()
    injector.get.side_effect = _get
    stack.enter_context(patch(f"{_ORCH}.injector", injector))
    stack.enter_context(patch(f"{_ORCH}.get_tenant_context", MagicMock(return_value="tenant-1")))
    set_tenant = MagicMock()
    stack.enter_context(patch(f"{_ORCH}.set_tenant_context", set_tenant))
    if wait_for is not None:
        stack.enter_context(patch(f"{_ORCH}.asyncio.wait_for", wait_for))
    return stack, engine, session, set_tenant, engine_cls


_WORKFLOW = {"config": {"id": "wf1"}, "nodes": [{"id": "child", "type": "subAgentNode"}], "edges": []}


def test_child_thread_id_is_invocation_scoped():
    assert orchestrator.child_thread_id("root", "child", "inv") == "root:sub:child:inv"


@pytest.mark.asyncio
async def test_run_child_turn_uses_derived_thread_and_persists_history():
    child_state = _fake_child_state("done")
    stack, engine, session, set_tenant, _ = _patch_env(child_state)
    with stack:
        result = await orchestrator.run_child_turn(
            workflow=_WORKFLOW,
            root_thread_id="root",
            child_node_id="child",
            invocation_id="inv",
            message="do it",
            timeout_seconds=120,
        )

    assert result is child_state
    _, kwargs = engine.execute_from_node.call_args
    assert kwargs["start_node_id"] == "child"
    assert kwargs["thread_id"] == "root:sub:child:inv"
    assert kwargs["persist"] is False
    assert kwargs["input_data"]["message"] == "do it"
    child_state.get_memory().add_input_output.assert_awaited_once_with("do it", "done")
    session.close.assert_awaited_once()
    set_tenant.assert_called_once_with("tenant-1")


@pytest.mark.asyncio
async def test_run_child_turn_timeout_surfaced_and_session_closed():
    child_state = _fake_child_state()

    async def _raise(coro, timeout):
        coro.close()
        raise asyncio.TimeoutError()

    stack, engine, session, _, _ = _patch_env(child_state, wait_for=_raise)
    with stack, pytest.raises(asyncio.TimeoutError):
        await orchestrator.run_child_turn(
            workflow=_WORKFLOW,
            root_thread_id="root",
            child_node_id="child",
            invocation_id="inv",
            message="do it",
            timeout_seconds=1,
        )

    session.close.assert_awaited_once()
    child_state.get_memory().add_input_output.assert_not_called()


@pytest.mark.asyncio
async def test_run_child_turn_forces_child_pii_when_inherited():
    child_state = _fake_child_state()
    stack, _, _, _, engine_cls = _patch_env(child_state)
    with stack:
        await orchestrator.run_child_turn(
            workflow=_WORKFLOW,
            root_thread_id="root",
            child_node_id="child",
            invocation_id="inv",
            message="do it",
            timeout_seconds=120,
            inherit_pii=True,
        )
    built_config = engine_cls.call_args.args[0]
    child_node = next(n for n in built_config["nodes"] if n["id"] == "child")
    assert child_node["data"]["piiMasking"] is True


def test_envelope_round_trip_and_gating():
    env = orchestrator.make_envelope(
        status="completed",
        message="answer",
        child_node_id="c",
        mode="task",
        invocation_id="inv",
        task="t",
    )
    parsed = orchestrator.parse_envelope(env)
    assert parsed["status"] == "completed"
    assert parsed["child_node_id"] == "c"
    assert orchestrator.parse_envelope("not json") is None
    assert orchestrator.parse_envelope('{"status": "completed"}') is None


def test_child_completion_and_message_helpers():
    state = MagicMock()
    state.get_last_node_output.return_value = {"message": "hello"}
    assert orchestrator.child_message(state) == "hello"
    delattr_state = MagicMock(spec=[])
    delattr_state.get_last_node_output = MagicMock(return_value={"message": "x"})
    assert orchestrator.child_completion(delattr_state) is None
    setattr(state, orchestrator.SUB_AGENT_CONTROL_ATTR, {"result": "final"})
    assert orchestrator.child_completion(state) == {"result": "final"}
