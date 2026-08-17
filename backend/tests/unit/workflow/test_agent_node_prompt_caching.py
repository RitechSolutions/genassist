"""Agent and sub-agent nodes forward the timestamp suffix only for cache-eligible prompts"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.workflow.agents.agent_runtime import AgentRunResult
from app.modules.workflow.engine.nodes.agent_node import AgentNode
from app.modules.workflow.engine.nodes.sub_agent_node import SubAgentNode

_AGENT_NODE = "app.modules.workflow.engine.nodes.agent_node"
_SUB_NODE = "app.modules.workflow.engine.nodes.sub_agent_node"

_STABLE = "You are a helpful assistant with a long stable prefix."
_VOLATILE_VARS = ["{{session.message}}", "{{message}}", "{{source.text}}", "{{node_outputs.n1}}", "{{timestamp}}"]

_AGENT_CONFIG = {"providerId": "prov-1", "type": "ToolSelector", "memory": False}
_SUB_CONFIG = {"providerId": "prov-1", "mode": "single_turn", "timeoutSeconds": 120}


def _state():
    return SimpleNamespace(set_node_input=MagicMock(), workflow={"nodes": [], "edges": []}, initial_values={})


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


async def _run(node_cls, module, config, *, node_data, resolved=None):
    node = node_cls("node-1", {"type": "agentNode", "data": node_data}, _state())
    merged = dict(config)
    if resolved is not None:
        merged["systemPrompt"] = resolved

    once = AsyncMock(return_value=_run_result())
    with patch(f"{module}.run_agent_once", once), patch.object(node_cls, "get_connected_nodes", return_value=[]):
        await node.process(merged)
    return once.await_args.kwargs


_NODES = [
    pytest.param(AgentNode, _AGENT_NODE, _AGENT_CONFIG, id="agent"),
    pytest.param(SubAgentNode, _SUB_NODE, _SUB_CONFIG, id="sub_agent"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("node_cls,module,config", _NODES)
class TestVolatilityGate:
    async def test_stable_prompt_forwards_the_timestamp_suffix(self, node_cls, module, config):
        kwargs = await _run(node_cls, module, config, node_data={"systemPrompt": _STABLE}, resolved=_STABLE)

        suffix = kwargs["volatile_system_suffix"]
        assert suffix.startswith(" Current time: ")
        assert kwargs["system_prompt"].startswith(_STABLE)
        assert kwargs["system_prompt"].endswith(suffix)

    @pytest.mark.parametrize("var", _VOLATILE_VARS)
    async def test_volatile_prompt_withholds_the_suffix(self, node_cls, module, config, var):
        kwargs = await _run(
            node_cls,
            module,
            config,
            node_data={"systemPrompt": f"Answer about {var}"},
            resolved="Answer about a bug report",
        )

        assert kwargs["volatile_system_suffix"] is None
        assert kwargs["system_prompt"].startswith("Answer about a bug report")
        assert " Current time: " in kwargs["system_prompt"]

    async def test_per_conversation_var_stays_eligible(self, node_cls, module, config):
        kwargs = await _run(
            node_cls,
            module,
            config,
            node_data={"systemPrompt": "Reply in {{session.language}}."},
            resolved="Reply in German.",
        )

        assert kwargs["volatile_system_suffix"] is not None
        assert kwargs["system_prompt"].startswith("Reply in German.")

    async def test_absent_raw_prompt_forwards_the_suffix(self, node_cls, module, config):
        kwargs = await _run(node_cls, module, config, node_data={"name": "Agent"})

        assert kwargs["volatile_system_suffix"] is not None
        assert kwargs["system_prompt"].startswith("You are a helpful assistant.")


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

    async def test_suffix_reaches_run_agent_once(self):
        node = AgentNode("node-1", {"type": "agentNode", "data": {}}, _state())
        once = AsyncMock(return_value=_run_result())

        with patch(f"{_AGENT_NODE}.run_agent_once", once):
            await node._run_agent_with_delegations(**self._delegation_kwargs(volatile_system_suffix=" Current time: X"))

        assert once.await_args.kwargs["volatile_system_suffix"] == " Current time: X"

    async def test_callers_omitting_the_kwarg_send_none(self):
        node = AgentNode("node-1", {"type": "agentNode", "data": {}}, _state())
        once = AsyncMock(return_value=_run_result())

        with patch(f"{_AGENT_NODE}.run_agent_once", once):
            await node._run_agent_with_delegations(**self._delegation_kwargs())

        assert once.await_args.kwargs["volatile_system_suffix"] is None
