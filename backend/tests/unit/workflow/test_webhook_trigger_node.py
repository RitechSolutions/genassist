"""Behaviour of WebhookTriggerNode.process() and the engine's entry-node rules.

- With a delivery on the state the node re-applies the mapping and returns it.
- Without one (builder Test button / schedule) it falls back to the sample payload.
- A run started at the trigger neither waits on nor reads from the Chat Input
  node that shares its downstream node; `_find_starting_nodes` picks a lone
  trigger when there is no Chat Input.
"""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.modules.workflow.engine.node_result import is_node_failure
from app.modules.workflow.engine.nodes.webhook_trigger_node import WebhookTriggerNode
from app.modules.workflow.engine.workflow_engine import WorkflowEngine
from app.modules.workflow.webhook_trigger_mapping import build_envelope


class _State(SimpleNamespace):
    def get_value(self, key, default=None):
        return getattr(self, key, default)

    def set_node_input(self, node_id, value):
        self.inputs = {node_id: value}


def _node(node_data, state):
    config = {"id": "wt", "type": "webhookTriggerNode", "data": node_data}
    return WebhookTriggerNode("wt", config, state)


@pytest.mark.asyncio
async def test_maps_live_delivery_from_state():
    env = build_envelope(method="POST", headers={}, query={}, body={"order": {"id": 9}, "text": "hi"})
    state = _State(webhook=env)
    node = _node(
        {"fieldMappings": [{"key": "order_id", "path": "body.order.id"}], "messagePath": "body.text"},
        state,
    )
    result = await node.process({})
    assert result["order_id"] == 9
    assert result["message"] == "hi"
    assert result["webhook"] is env
    assert result["webhook"]["is_test"] is False
    assert state.inputs["wt"] is result


@pytest.mark.asyncio
async def test_falls_back_to_sample_payload_when_no_delivery():
    state = _State()
    node = _node(
        {"samplePayload": '{"order": {"id": 1}}', "fieldMappings": [{"key": "order_id", "path": "body.order.id"}]},
        state,
    )
    result = await node.process({})
    assert result["order_id"] == 1
    assert result["webhook"]["is_test"] is True
    assert result["webhook"]["body"] == {"order": {"id": 1}}


@pytest.mark.asyncio
async def test_mapping_errors_become_a_node_failure():
    state = _State(webhook=build_envelope(method="POST", headers={}, query={}, body={}))
    node = _node({"fieldMappings": [{"key": "x", "path": "body.x", "required": True}]}, state)
    result = await node.process({})
    failure = is_node_failure(result)
    assert failure is not None
    assert "x" in failure["error"]


def test_mapping_config_is_never_template_resolved():
    node = _node({}, _State())
    assert {"fieldMappings", "messagePath", "samplePayload"} <= node._unresolved_config_fields()


# --------------------------------------------------------------------------- #
# Engine integration: two entry nodes feeding one output node
# --------------------------------------------------------------------------- #

_WORKFLOW = {
    "id": "wf",
    "nodes": [
        {"id": "start", "type": "chatInputNode", "data": {"inputSchema": {"message": {"type": "string", "required": True}}}},
        {"id": "wt", "type": "webhookTriggerNode", "data": {"messagePath": "body.text"}},
        {"id": "out", "type": "chatOutputNode", "data": {}},
    ],
    "edges": [
        {"source": "start", "target": "out", "sourceHandle": "output", "targetHandle": "input"},
        {"source": "wt", "target": "out", "sourceHandle": "output", "targetHandle": "input"},
    ],
}


class _NoMemory:
    async def add_input_output(self, *_args, **_kwargs):
        return None


@pytest.mark.asyncio
async def test_run_from_trigger_ignores_the_unused_chat_input():
    engine = WorkflowEngine(dict(_WORKFLOW))
    env = build_envelope(method="POST", headers={}, query={}, body={"text": "from webhook"})
    with patch("app.modules.workflow.engine.workflow_state.ConversationMemory.get_instance", return_value=_NoMemory()):
        state = await engine.execute_from_node(
            start_node_id="wt", input_data={"webhook": env, "message": "from webhook"},
            thread_id="t1", persist=False,
        )
    assert state.entry_node_id == "wt"
    assert "start" not in state.node_outputs
    # The output node ran (it was not blocked waiting on Chat Input) and saw only the trigger's output.
    out = state.node_outputs["out"]
    assert out["message"] == "from webhook"
    assert out["webhook"]["body"] == {"text": "from webhook"}


def test_lone_trigger_is_the_starting_node_when_there_is_no_chat_input():
    wf = {
        "id": "wf",
        "nodes": [
            {"id": "wt", "type": "webhookTriggerNode", "data": {}},
            {"id": "tool", "type": "toolBuilderNode", "data": {}},  # also has no incoming edge
            {"id": "agent", "type": "agentNode", "data": {}},
        ],
        "edges": [
            {"source": "wt", "target": "agent", "sourceHandle": "output", "targetHandle": "input"},
            {"source": "tool", "target": "agent", "sourceHandle": "output", "targetHandle": "input_tools"},
        ],
    }
    assert WorkflowEngine(wf)._find_starting_nodes() == ["wt"]


def test_chat_input_still_wins_when_both_entry_nodes_exist():
    assert WorkflowEngine(dict(_WORKFLOW))._find_starting_nodes() == ["start"]
