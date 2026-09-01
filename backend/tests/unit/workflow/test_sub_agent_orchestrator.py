"""Child-engine orchestration: derived thread, persist=False, durable history, timeout"""

import asyncio
import json
from types import SimpleNamespace
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


def test_canonical_session_strips_flatten_artifacts():
    polluted = {
        "message": "m",
        "thread_id": "t",
        "agent_id": "a",
        "conversation_history": "h",
        "session.message": "m",
        "session.session.message": "m",
        "session": {"message": "m"},
    }
    canon = orchestrator._canonical_session(polluted)
    assert canon == {"message": "m", "thread_id": "t", "agent_id": "a", "conversation_history": "h"}


def test_canonical_session_strips_sub_agent_resume_marker():
    from app.modules.workflow.agents.sub_agents.models import SUB_AGENT_RESUME_KEY

    canon = orchestrator._canonical_session({"customer_name": "Ada", SUB_AGENT_RESUME_KEY: {"child_result": "x"}})
    assert canon == {"customer_name": "Ada"}


@pytest.mark.asyncio
async def test_run_child_turn_passes_canonical_nested_session():
    child_state = _fake_child_state()
    stack, engine, _, _, _ = _patch_env(child_state)
    polluted = {
        "message": "orig",
        "thread_id": "t",
        "agent_id": "a",
        "session.message": "orig",
        "session.session.message": "orig",
        "session": {"message": "orig"},
    }
    with stack:
        await orchestrator.run_child_turn(
            workflow=_WORKFLOW,
            root_thread_id="root",
            child_node_id="child",
            invocation_id="inv",
            message="task",
            session=polluted,
            timeout_seconds=120,
        )
    input_data = engine.execute_from_node.call_args.kwargs["input_data"]
    assert input_data["message"] == "task"
    assert not any(isinstance(k, str) and k.startswith("session.") for k in input_data)
    assert input_data["session"] == {"message": "orig", "thread_id": "t", "agent_id": "a"}


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


def test_parse_envelope_rejects_malformed_payloads():
    missing_key = json.dumps({"__sub_agent__": 1, "status": "completed", "message": "x"})
    assert orchestrator.parse_envelope(missing_key) is None

    wrong_type = json.dumps(
        {
            "__sub_agent__": 1,
            "status": "completed",
            "message": "x",
            "child_node_id": 123,
            "mode": "task",
            "invocation_id": "inv",
            "task": "t",
        }
    )
    assert orchestrator.parse_envelope(wrong_type) is None

    # Unknown status -> None
    bad_status = json.dumps(
        {
            "__sub_agent__": 1,
            "status": "bogus",
            "message": "x",
            "child_node_id": "c",
            "mode": "task",
            "invocation_id": "inv",
            "task": "t",
        }
    )
    assert orchestrator.parse_envelope(bad_status) is None


def test_child_completion_and_message_helpers():
    state = MagicMock()
    state.get_last_node_output.return_value = {"message": "hello"}
    assert orchestrator.child_message(state) == "hello"
    delattr_state = MagicMock(spec=[])
    delattr_state.get_last_node_output = MagicMock(return_value={"message": "x"})
    assert orchestrator.child_completion(delattr_state) is None
    setattr(state, orchestrator.SUB_AGENT_CONTROL_ATTR, {"result": "final"})
    assert orchestrator.child_completion(state) == {"result": "final"}


@pytest.mark.asyncio
async def test_run_child_turn_forwards_the_parent_usage_sink():
    child_state = _fake_child_state()
    sink = []
    stack, engine, _, _, _ = _patch_env(child_state)
    with stack:
        await orchestrator.run_child_turn(
            workflow=_WORKFLOW,
            root_thread_id="root",
            child_node_id="child",
            invocation_id="inv",
            message="do it",
            timeout_seconds=120,
            usage_sink=sink,
        )

    _, kwargs = engine.execute_from_node.call_args
    assert kwargs["usage_sink"] is sink
    assert kwargs["usage_context"] is None


@pytest.mark.asyncio
async def test_run_child_turn_forwards_the_resume_usage_context():
    child_state = _fake_child_state()
    context = MagicMock()
    stack, engine, _, _, _ = _patch_env(child_state)
    with stack:
        await orchestrator.run_child_turn(
            workflow=_WORKFLOW,
            root_thread_id="root",
            child_node_id="child",
            invocation_id="inv",
            message="do it",
            timeout_seconds=120,
            usage_context=context,
        )

    _, kwargs = engine.execute_from_node.call_args
    assert kwargs["usage_context"] is context
    assert kwargs["usage_sink"] is None


@pytest.mark.asyncio
async def test_run_child_turn_without_usage_threading_stays_uncaptured():
    child_state = _fake_child_state()
    stack, engine, _, _, _ = _patch_env(child_state)
    with stack:
        await orchestrator.run_child_turn(
            workflow=_WORKFLOW,
            root_thread_id="root",
            child_node_id="child",
            invocation_id="inv",
            message="do it",
            timeout_seconds=120,
        )

    _, kwargs = engine.execute_from_node.call_args
    assert kwargs["usage_sink"] is None and kwargs["usage_context"] is None


def _diag(applied=False):
    return {"requested": True, "applied": applied}


def _state_with(entries=None, collected=None):
    return SimpleNamespace(
        node_execution_status=entries if entries is not None else {},
        prompt_caching_diagnostics=collected if collected is not None else {},
    )


class TestPropagatePromptCacheDiagnostics:

    def test_the_childs_collection_reaches_the_parent(self):
        child = _state_with(collected={"child": _diag()})
        parent = _state_with()

        orchestrator.propagate_prompt_cache_diagnostics(child, parent)

        assert parent.prompt_caching_diagnostics == {"child": _diag()}

    def test_the_parents_execution_map_is_left_alone(self):
        child = _state_with({"child": {"status": "failed"}}, {"child": _diag()})
        parent = _state_with({"parent": {"status": "success"}})

        orchestrator.propagate_prompt_cache_diagnostics(child, parent)

        assert parent.node_execution_status == {"parent": {"status": "success"}}

    def test_descendant_diagnostics_chain_upward(self):
        child = _state_with(collected={"child": _diag(), "grandchild": _diag()})
        parent = _state_with()

        orchestrator.propagate_prompt_cache_diagnostics(child, parent)

        assert set(parent.prompt_caching_diagnostics) == {"child", "grandchild"}

    def test_the_childs_entry_wins_over_a_stale_parent_copy(self):
        child = _state_with(collected={"child": _diag(applied=True)})
        parent = _state_with(collected={"child": _diag()})

        orchestrator.propagate_prompt_cache_diagnostics(child, parent)

        assert parent.prompt_caching_diagnostics["child"]["applied"] is True

    def test_existing_parent_entries_survive(self):
        child = _state_with(collected={"child": _diag()})
        parent = _state_with(collected={"earlier": _diag()})

        orchestrator.propagate_prompt_cache_diagnostics(child, parent)

        assert set(parent.prompt_caching_diagnostics) == {"earlier", "child"}

    def test_a_child_without_diagnostics_writes_nothing(self):
        parent = _state_with()

        orchestrator.propagate_prompt_cache_diagnostics(_state_with({"child": {"status": "success"}}), parent)

        assert parent.prompt_caching_diagnostics == {}

    def test_a_malformed_child_collection_is_ignored(self):
        parent = _state_with()

        orchestrator.propagate_prompt_cache_diagnostics(_state_with(collected="junk"), parent)

        assert parent.prompt_caching_diagnostics == {}

    def test_a_state_without_the_collection_never_raises(self):
        child = _state_with(collected={"child": _diag()})

        orchestrator.propagate_prompt_cache_diagnostics(child, SimpleNamespace())
        orchestrator.propagate_prompt_cache_diagnostics(SimpleNamespace(), _state_with())
