"""Unit tests for the coarse activity a node reports to a streamed chat turn"""

import pytest

from app.core import turn_stream
from app.core.turn_stream import TurnStream, current_stream
from app.modules.workflow.engine.base_node import BaseNode
from app.modules.workflow.engine.workflow_engine import WorkflowEngine
from app.modules.workflow.engine.workflow_state import WorkflowState


class _Node(BaseNode):
    def __init__(self, node_type, data=None, fails=False):
        node_config = {"id": "n1", "type": node_type, "data": {"name": "Secret builder name", **(data or {})}}
        super().__init__("n1", node_config, WorkflowState(workflow={"nodes": [node_config]}, thread_id="thread-1"))
        self._fails = fails

    async def process(self, config):
        if self._fails:
            raise RuntimeError("boom")
        return "ok"


@pytest.fixture
def stream():
    stream = TurnStream("c1")
    token = current_stream.set(stream)
    yield stream
    current_stream.reset(token)


def _frames(stream):
    frames = []
    while not stream.queue.empty():
        frames.append(stream.queue.get_nowait())
    return frames


@pytest.mark.asyncio
async def test_knowledge_node_reports_only_its_kind(stream):
    await _Node("knowledgeBaseNode").execute()

    assert _frames(stream) == [
        'event: activity\ndata: {"kind": "knowledge", "phase": "start"}\n\n',
        'event: activity\ndata: {"kind": "knowledge", "phase": "end"}\n\n',
    ]


@pytest.mark.asyncio
async def test_failing_tool_node_still_ends_its_activity(stream):
    await _Node("apiToolNode", fails=True).execute()

    assert _frames(stream) == [
        'event: activity\ndata: {"kind": "tool", "phase": "start"}\n\n',
        'event: activity\ndata: {"kind": "tool", "phase": "end"}\n\n',
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("node_type", ["agentNode", "routerNode", "llmModelNode"])
async def test_nodes_outside_the_allowlist_send_nothing(stream, node_type):
    await _Node(node_type).execute()

    assert _frames(stream) == []


def test_deactivated_node_pass_through_sends_nothing(stream):
    node = _Node("knowledgeBaseNode", data={"deactivated": True})
    node.start_execution()
    node.complete_execution()

    assert _frames(stream) == []


def test_every_labelled_node_type_is_a_registered_node_type():
    WorkflowEngine._initialize_node_registry()

    assert set(turn_stream._NODE_ACTIVITY_KINDS) - set(WorkflowEngine._node_registry) == set()
