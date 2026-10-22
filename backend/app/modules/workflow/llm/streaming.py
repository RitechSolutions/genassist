"""Streams one model reply into a chat turn and returns it in the shape an unstreamed call gives."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel
    from langchain_core.messages import BaseMessage

    from app.core.turn_stream import TokenSink


def _plain_content(content: Any) -> Any:
    """Give streamed content the shape the same reply has unstreamed. Bedrock and Anthropic stream
    content blocks with `index` keys, and collapse a lone plain text block to a string unstreamed."""
    if not isinstance(content, list):
        return content
    blocks = [
        {k: v for k, v in block.items() if k != "index"} if isinstance(block, dict) else block for block in content
    ]
    if (
        len(blocks) == 1
        and isinstance(blocks[0], dict)
        and blocks[0].keys() == {"type", "text"}
        and blocks[0]["type"] == "text"
    ):
        return blocks[0]["text"]
    return blocks


async def astream_reply(llm: BaseChatModel, messages: list[BaseMessage], on_text: TokenSink) -> BaseMessage:
    call_id = uuid.uuid4().hex
    reply = None
    async for chunk in llm.astream(messages):
        reply = chunk if reply is None else reply + chunk
        if chunk.text:
            on_text(call_id, chunk.text)
    return reply.model_copy(update={"content": _plain_content(reply.content)})
