"""Unit tests for an LLM node that streams its reply into a chat turn"""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult

from app.core.turn_stream import TurnStream, current_stream
from app.modules.workflow.engine.nodes.llm_model_node import LLMModelNode
from app.modules.workflow.engine.workflow_state import WorkflowState
from app.modules.workflow.llm.provider import LLMProvider
from app.modules.workflow.llm.streaming import _plain_content

_USAGE = {"input_tokens": 25, "output_tokens": 11, "total_tokens": 36}


class _BedrockLikeModel(BaseChatModel):

    @property
    def _llm_type(self) -> str:
        return "bedrock-like"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        reply = AIMessage(content="J'aime la programmation.", usage_metadata=_USAGE)
        return ChatResult(generations=[ChatGeneration(message=reply)])

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        return self._generate(messages, stop, run_manager, **kwargs)

    async def _astream(self, messages, stop=None, run_manager=None, **kwargs):
        yield ChatGenerationChunk(message=AIMessageChunk(content=[{"type": "text", "text": "J'aime", "index": 0}]))
        yield ChatGenerationChunk(message=AIMessageChunk(content=[{"type": "text", "text": " la programmation.", "index": 0}]))
        yield ChatGenerationChunk(message=AIMessageChunk(content=[], usage_metadata=_USAGE))


async def _run(stream=None):
    nodes = [{"id": "llm-1", "type": "llmModelNode", "data": {}}, {"id": "out", "type": "chatOutputNode", "data": {}}]
    state = WorkflowState(
        workflow={"nodes": nodes, "source_edges": {"llm-1": [{"source": "llm-1", "target": "out"}]}},
        thread_id="thread-1",
        registry_managed=True,
    )
    provider = MagicMock(get_model_for_node=AsyncMock(return_value=_BedrockLikeModel()))
    service = MagicMock(get_by_id=AsyncMock(return_value=SimpleNamespace(llm_model_provider="bedrock", llm_model="nova")))
    injector = MagicMock(get=MagicMock(side_effect=lambda cls: provider if cls is LLMProvider else service))
    token = current_stream.set(stream)
    try:
        with patch("app.dependencies.injector.injector", injector):
            content = await LLMModelNode("llm-1", nodes[0], state).process(
                {"providerId": "p1", "systemPrompt": "sys", "userPrompt": "hi"}
            )
    finally:
        current_stream.reset(token)
    return content, state.llm_usage


@pytest.mark.asyncio
async def test_a_streamed_reply_is_saved_and_billed_like_the_unstreamed_one():
    stream = TurnStream("c1")

    streamed_content, streamed_usage = await _run(stream)
    plain_content, plain_usage = await _run()

    frames = [stream.queue.get_nowait() for _ in range(stream.queue.qsize())]
    assert [json.loads(frame.split("data: ", 1)[1])["text"] for frame in frames] == ["J'aime", " la programmation."]
    assert streamed_content == plain_content == "J'aime la programmation."
    assert streamed_usage == plain_usage
    assert streamed_usage[0]["input_tokens"] == 25


@pytest.mark.parametrize(
    "content, expected",
    [
        (
            [{"type": "reasoning_content", "reasoning_content": {"text": "r"}, "index": 0}, {"type": "text", "text": "hi", "index": 1}],
            [{"type": "reasoning_content", "reasoning_content": {"text": "r"}}, {"type": "text", "text": "hi"}],
        ),
        ([{"type": "text", "text": "hi", "citations": [], "index": 0}], [{"type": "text", "text": "hi", "citations": []}]),
    ],
    ids=["reasoning and text", "text with citations"],
)
def test_streamed_blocks_lose_only_their_stream_index(content, expected):
    assert _plain_content(content) == expected
