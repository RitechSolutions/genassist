"""Unit tests for what a node sends to a streamed chat turn: coarse activity and reply text"""

import asyncio
from unittest.mock import AsyncMock

import pytest

from app.core.turn_stream import TurnStream, current_stream
from app.modules.workflow.engine import base_node
from app.modules.workflow.engine.base_node import BaseNode
from app.modules.workflow.engine.pii_anonymizer_mixin import PIIAnonymizerMixin
from app.modules.workflow.engine.workflow_engine import WorkflowEngine
from app.modules.workflow.engine.workflow_state import WorkflowState


class _Node(BaseNode):
    def __init__(self, node_type, data=None, fails=False, node_id="n1"):
        node_config = {"id": node_id, "type": node_type, "data": {"name": "Secret builder name", **(data or {})}}
        super().__init__(node_id, node_config, WorkflowState(workflow={"nodes": [node_config]}, thread_id="thread-1"))
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

    assert set(base_node._NODE_ACTIVITY_KINDS) - set(WorkflowEngine._node_registry) == set()


class _ReplyNode(PIIAnonymizerMixin, _Node):
    pass


def _feeding(target_type="chatOutputNode", registry_managed=True, node_data=None):
    nodes = [{"id": "n1", "type": "agentNode", "data": {}}, {"id": "out", "type": target_type, "data": {}}]
    node = _ReplyNode("agentNode", data=node_data)
    node.state = WorkflowState(
        workflow={"nodes": nodes, "source_edges": {"n1": [{"source": "n1", "target": "out"}]}},
        thread_id="thread-1",
        registry_managed=registry_managed,
    )
    return node


def test_node_feeding_chat_output_streams_its_text(stream):
    _feeding().chat_token_sink()("call-1", "Hi")

    assert _frames(stream) == ['event: delta\ndata: {"call_id": "call-1", "text": "Hi"}\n\n']


@pytest.mark.parametrize(
    "overrides",
    [{"registry_managed": False}, {"target_type": "routerNode"}, {"node_data": {"piiMasking": True}}],
    ids=["nested run", "not feeding chat output", "pii masked"],
)
def test_token_sink_is_withheld(stream, overrides):
    assert _feeding(**overrides).chat_token_sink() is None


def test_token_sink_is_withheld_when_the_turn_withholds_text(stream):
    stream.withhold_text()

    assert _feeding().chat_token_sink() is None


def test_token_sink_is_withheld_outside_a_streamed_turn():
    assert _feeding().chat_token_sink() is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "reply, later_frames",
    [
        ("Hi", ['event: activity\ndata: {"kind": "tool", "phase": "end"}\n\n']),
        (
            '{"message": "Hi"}',
            [
                'event: activity\ndata: {"kind": "tool", "phase": "start"}\n\n',
                'event: activity\ndata: {"kind": "tool", "phase": "end"}\n\n',
            ],
        ),
    ],
    ids=["shown reply", "muted envelope"],
)
async def test_a_tool_after_the_streamed_reply_cannot_clear_it(stream, reply, later_frames):
    agent = _feeding()
    agent.process = AsyncMock(side_effect=lambda config: agent.chat_token_sink()("call-1", reply))

    await agent.execute()
    _frames(stream)
    await _Node("zendeskTicketNode").execute()

    assert _frames(stream) == later_frames


@pytest.mark.asyncio
async def test_only_the_replying_agents_own_tools_clear_its_live_reply(stream):
    agent = _feeding()
    reply_live, sibling_done = asyncio.Event(), asyncio.Event()

    async def process(config):
        sink = agent.chat_token_sink()
        sink("call-1", "Let me check")
        await _Node("apiToolNode", node_id="own-tool").execute()
        sink("call-2", "Your order")
        reply_live.set()
        await sibling_done.wait()
        sink("call-2", " shipped")

    async def sibling():
        await reply_live.wait()
        await _Node("slackMessageNode", node_id="side-branch").execute()
        sibling_done.set()

    agent.process = process
    await asyncio.gather(agent.execute(), sibling())

    assert _frames(stream) == [
        'event: delta\ndata: {"call_id": "call-1", "text": "Let me check"}\n\n',
        'event: activity\ndata: {"kind": "tool", "phase": "start"}\n\n',
        'event: activity\ndata: {"kind": "tool", "phase": "end"}\n\n',
        'event: delta\ndata: {"call_id": "call-2", "text": "Your order"}\n\n',
        'event: activity\ndata: {"kind": "tool", "phase": "end"}\n\n',
        'event: delta\ndata: {"call_id": "call-2", "text": " shipped"}\n\n',
    ]
