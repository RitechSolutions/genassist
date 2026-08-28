"""Agent and sub-agent nodes forward the prompt parts only for cache-eligible prompts"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.workflow.agents.agent_runtime import AgentRunResult
from app.modules.workflow.engine.nodes.agent_node import AgentNode
from app.modules.workflow.engine.nodes.sub_agent_node import SubAgentNode

_AGENT_NODE = "app.modules.workflow.engine.nodes.agent_node"
_SUB_NODE = "app.modules.workflow.engine.nodes.sub_agent_node"

_STABLE = "You are a helpful assistant with a long stable prefix."
_VOLATILE_VARS = [
    "{{session.message}}",
    "{{session.language}}",
    "{{message}}",
    "{{source.text}}",
    "{{node_outputs.n1}}",
    "{{timestamp}}",
]

_AGENT_CONFIG = {"providerId": "prov-1", "type": "ToolSelector", "memory": False}
_SUB_CONFIG = {"providerId": "prov-1", "mode": "single_turn", "timeoutSeconds": 120}


def _state():
    return SimpleNamespace(
        set_node_input=MagicMock(),
        workflow={"nodes": [], "edges": []},
        initial_values={},
        get_memory=MagicMock(return_value=None),
    )


def _run_result():
    return AgentRunResult(
        response="answer",
        steps=[],
        tools_used=[],
        status="success",
        error=None,
        raw={"response": "answer"},
        llm_model="m",
    )


async def _run(node_cls, module, config, *, node_data, resolved=None, tools=()):
    node = node_cls("node-1", {"type": "agentNode", "data": node_data}, _state())
    merged = dict(config)
    if resolved is not None:
        merged["systemPrompt"] = resolved

    once = AsyncMock(return_value=_run_result())
    with patch(f"{module}.run_agent_once", once), patch.object(
        node_cls, "get_connected_nodes", return_value=list(tools)
    ):
        await node.process(merged)
    return once.await_args.kwargs


_NODES = [
    pytest.param(AgentNode, _AGENT_NODE, _AGENT_CONFIG, id="agent"),
    pytest.param(SubAgentNode, _SUB_NODE, _SUB_CONFIG, id="sub_agent"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("node_cls,module,config", _NODES)
class TestVolatilityGate:
    async def test_stable_prompt_forwards_the_prompt_parts(self, node_cls, module, config):
        kwargs = await _run(node_cls, module, config, node_data={"systemPrompt": _STABLE}, resolved=_STABLE)

        stable, volatile = kwargs["stable_volatile_parts"]
        assert stable.startswith(_STABLE)
        assert volatile.startswith(" Current time: ")

    @pytest.mark.parametrize("var", _VOLATILE_VARS)
    async def test_volatile_prompt_withholds_the_parts(self, node_cls, module, config, var):
        kwargs = await _run(
            node_cls,
            module,
            config,
            node_data={"systemPrompt": f"Answer about {var}"},
            resolved="Answer about a bug report",
        )

        assert kwargs["stable_volatile_parts"] is None
        assert kwargs["system_prompt"].startswith("Answer about a bug report")
        assert " Current time: " in kwargs["system_prompt"]

    async def test_absent_raw_prompt_forwards_the_parts(self, node_cls, module, config):
        kwargs = await _run(node_cls, module, config, node_data={"name": "Agent"})

        assert kwargs["stable_volatile_parts"] is not None
        assert kwargs["system_prompt"].startswith("You are a helpful assistant.")


class TestTimestampedSystemPromptHelper:

    @staticmethod
    def _node(raw):
        return AgentNode("node-1", {"type": "agentNode", "data": {"systemPrompt": raw}}, _state())

    def test_stable_template_returns_parts_that_rebuild_the_prompt(self):
        full, parts = self._node(_STABLE)._timestamped_system_prompt(_STABLE)

        assert parts == (_STABLE, full[len(_STABLE) :])
        assert "".join(parts) == full
        assert parts[1].startswith(" Current time: ")

    @pytest.mark.parametrize("var", _VOLATILE_VARS)
    def test_volatile_template_withholds_the_parts(self, var):
        full, parts = self._node(f"Answer about {var}")._timestamped_system_prompt("Answer about a bug report")

        assert parts is None
        assert full.startswith("Answer about a bug report")
        assert " Current time: " in full

    def test_the_sub_agent_node_inherits_it(self):
        assert SubAgentNode._timestamped_system_prompt is AgentNode._timestamped_system_prompt


@pytest.mark.asyncio
class TestDelegationPathThreading:
    @staticmethod
    def _delegation_kwargs(**over):
        kwargs = dict(
            config={},
            provider_id="prov-1",
            fallback_chain_id=None,
            agent_type="ToolSelector",
            system_prompt="sys Current time: X",
            prompt="hi",
            all_tools=[],
            delegation_map={},
            max_iterations=7,
            chat_history=[],
        )
        kwargs.update(over)
        return kwargs

    async def test_parts_reach_run_agent_once(self):
        node = AgentNode("node-1", {"type": "agentNode", "data": {}}, _state())
        once = AsyncMock(return_value=_run_result())
        parts = ("sys", " Current time: X")

        with patch(f"{_AGENT_NODE}.run_agent_once", once):
            await node._run_agent_with_delegations(**self._delegation_kwargs(stable_volatile_parts=parts))

        assert once.await_args.kwargs["stable_volatile_parts"] == parts

    async def test_callers_omitting_the_kwarg_send_none(self):
        node = AgentNode("node-1", {"type": "agentNode", "data": {}}, _state())
        once = AsyncMock(return_value=_run_result())

        with patch(f"{_AGENT_NODE}.run_agent_once", once):
            await node._run_agent_with_delegations(**self._delegation_kwargs())

        assert once.await_args.kwargs["stable_volatile_parts"] is None

    async def test_stable_tool_names_are_the_prefix_before_the_first_delegation(self):
        node = AgentNode("node-1", {"type": "agentNode", "data": {}}, _state())
        once = AsyncMock(return_value=_run_result())
        tools = [SimpleNamespace(name="weather"), SimpleNamespace(name="delegate_to_a"),
                 SimpleNamespace(name="finish_task")]
        delegation_map = {"delegate_to_a": {"child_node_id": "child-a", "mode": "single_turn"}}

        with patch(f"{_AGENT_NODE}.run_agent_once", once):
            await node._run_agent_with_delegations(
                **self._delegation_kwargs(all_tools=tools, delegation_map=delegation_map)
            )

        assert once.await_args.kwargs["stable_tool_names"] == frozenset({"weather"})

    async def test_a_run_without_delegations_sends_no_stable_tool_names(self):
        node = AgentNode("node-1", {"type": "agentNode", "data": {}}, _state())
        once = AsyncMock(return_value=_run_result())

        with patch(f"{_AGENT_NODE}.run_agent_once", once):
            await node._run_agent_with_delegations(
                **self._delegation_kwargs(all_tools=[SimpleNamespace(name="weather")])
            )

        assert once.await_args.kwargs["stable_tool_names"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize("node_cls,module,config", _NODES)
class TestPartsInvariant:

    @staticmethod
    def _assert_parts_rebuild_the_prompt(kwargs):
        parts = kwargs["stable_volatile_parts"]
        assert parts, "a stable prompt must still forward them"
        assert "".join(parts) == kwargs["system_prompt"]

    async def test_holds_for_a_plain_run(self, node_cls, module, config):
        kwargs = await _run(node_cls, module, config, node_data={"systemPrompt": _STABLE}, resolved=_STABLE)

        self._assert_parts_rebuild_the_prompt(kwargs)

    async def test_holds_with_memory_enabled(self, node_cls, module, config):
        with patch.object(node_cls, "_get_chat_history_for_agent", AsyncMock(return_value=[])):
            kwargs = await _run(
                node_cls,
                module,
                {**config, "memory": True},
                node_data={"systemPrompt": _STABLE},
                resolved=_STABLE,
            )

        self._assert_parts_rebuild_the_prompt(kwargs)

    async def test_holds_with_pii_masking_and_tools(self, node_cls, module, config):
        kwargs = await _run(
            node_cls,
            module,
            {**config, "piiMasking": True},
            node_data={"systemPrompt": _STABLE},
            resolved=_STABLE,
            tools=[MagicMock(name="tool")],
        )

        self._assert_parts_rebuild_the_prompt(kwargs)

    async def test_holds_on_the_delegation_branch(self, node_cls, module, config):
        node = node_cls("node-1", {"type": "agentNode", "data": {"systemPrompt": _STABLE}}, _state())
        delegating = AsyncMock(return_value={"message": "answer"})

        with patch.object(node_cls, "get_connected_nodes", return_value=[]), patch.object(
            node_cls, "_build_delegation_tools", return_value=([MagicMock(name="delegation")], {"child-1": {}})
        ), patch.object(node_cls, "_run_agent_with_delegations", delegating):
            await node.process({**config, "systemPrompt": _STABLE})

        self._assert_parts_rebuild_the_prompt(delegating.await_args.kwargs)


async def _run_delegating(node_cls, module, config, *, node_data):
    node = node_cls("node-1", {"type": "agentNode", "data": node_data}, _state())
    delegated = AsyncMock(return_value={"message": "ok"})
    with patch.object(node_cls, "_build_delegation_tools", return_value=([], {"ask_child": {}})), patch.object(
        node_cls, "_run_agent_with_delegations", delegated
    ), patch.object(node_cls, "get_connected_nodes", return_value=[]):
        await node.process(dict(config))
    return delegated.await_args.kwargs


@pytest.mark.asyncio
@pytest.mark.parametrize("node_cls,module,config", _NODES)
class TestPromptCachingOptInForwarding:

    async def test_the_toggle_travels_to_the_runtime(self, node_cls, module, config):
        kwargs = await _run(
            node_cls, module, {**config, "promptCaching": True}, node_data={"systemPrompt": _STABLE}
        )

        assert kwargs["prompt_caching_enabled"] is True

    @pytest.mark.parametrize("raw", [None, False, "true", "True", 1, "1"], ids=repr)
    async def test_only_a_real_true_requests_caching(self, node_cls, module, config, raw):
        extra = {} if raw is None else {"promptCaching": raw}
        kwargs = await _run(node_cls, module, {**config, **extra}, node_data={"systemPrompt": _STABLE})

        assert kwargs["prompt_caching_enabled"] is False

    async def test_the_delegation_branch_forwards_it_too(self, node_cls, module, config):
        kwargs = await _run_delegating(
            node_cls, module, {**config, "promptCaching": True}, node_data={"systemPrompt": _STABLE}
        )

        assert kwargs["prompt_caching_enabled"] is True

    async def test_the_delegation_branch_defaults_off(self, node_cls, module, config):
        kwargs = await _run_delegating(node_cls, module, config, node_data={"systemPrompt": _STABLE})

        assert kwargs["prompt_caching_enabled"] is False
