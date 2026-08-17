"""Proves cache markers survive the real provider formatters"""

import pytest
from langchain_anthropic.chat_models import _format_messages
from langchain_aws.chat_models.bedrock_converse import _messages_to_bedrock
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from app.modules.workflow.llm.prompt_caching_chat_model import PromptCachingChatModel

_STABLE = "You are a helpful assistant with a long stable prefix."
_VOLATILE = "Current time: 2026-08-17T10:00:00Z"


class _CapturingModel(BaseChatModel):
    seen: list = []

    @property
    def _llm_type(self) -> str:
        return "capturing"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        self.seen.append(list(messages))
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content="ok"))])

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        return self._generate(messages, stop, run_manager, **kwargs)


async def _sent(style: str, system_content) -> list:
    inner = _CapturingModel()
    wrapper = PromptCachingChatModel(inner=inner, cache_style=style)
    await wrapper.ainvoke([SystemMessage(content=system_content), HumanMessage(content="hello")])
    return inner.seen[-1]


def _contains_key(obj, key: str) -> bool:
    if isinstance(obj, dict):
        return key in obj or any(_contains_key(v, key) for v in obj.values())
    if isinstance(obj, list):
        return any(_contains_key(v, key) for v in obj)
    return False


@pytest.mark.asyncio
class TestAnthropicSerialization:
    async def test_cache_control_reaches_the_system_payload(self):
        system, messages = _format_messages(await _sent("anthropic", [{"type": "text", "text": _STABLE}]))
        assert system == [{"type": "text", "text": _STABLE, "cache_control": {"type": "ephemeral"}}]
        assert messages[0]["role"] == "user"

    async def test_only_the_stable_block_carries_the_marker(self):
        system, _ = _format_messages(
            await _sent(
                "anthropic",
                [{"type": "text", "text": _STABLE}, {"type": "text", "text": _VOLATILE}],
            )
        )
        assert system == [
            {"type": "text", "text": _STABLE, "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": _VOLATILE},
        ]

    async def test_plain_string_system_serializes_without_any_marker(self):
        system, messages = _format_messages(await _sent("anthropic", _STABLE))
        assert system == _STABLE
        assert not _contains_key(system, "cache_control")
        assert not _contains_key(messages, "cache_control")


@pytest.mark.asyncio
class TestBedrockConverseSerialization:
    async def test_cache_point_reaches_the_system_payload(self):
        messages, system = _messages_to_bedrock(await _sent("bedrock_converse", [{"type": "text", "text": _STABLE}]))
        assert system == [{"text": _STABLE}, {"cachePoint": {"type": "default"}}]
        assert messages[0]["role"] == "user"

    async def test_cache_point_sits_between_stable_and_volatile_blocks(self):
        _, system = _messages_to_bedrock(
            await _sent(
                "bedrock_converse",
                [{"type": "text", "text": _STABLE}, {"type": "text", "text": _VOLATILE}],
            )
        )
        assert system == [
            {"text": _STABLE},
            {"cachePoint": {"type": "default"}},
            {"text": _VOLATILE},
        ]

    async def test_plain_string_system_serializes_without_any_marker(self):
        messages, system = _messages_to_bedrock(await _sent("bedrock_converse", _STABLE))
        assert system == [{"text": _STABLE}]
        assert not _contains_key(system, "cachePoint")
        assert not _contains_key(messages, "cachePoint")


_AGENT_SUFFIX = " Current time: 2026-08-17 12:00:00"
_HISTORY = "User: hi\nAssistant: hello"

_SPLITS = [
    pytest.param(
        [{"type": "text", "text": _STABLE}, {"type": "text", "text": _AGENT_SUFFIX}],
        _STABLE + _AGENT_SUFFIX,
        id="agent_split",
    ),
    pytest.param(
        [{"type": "text", "text": _STABLE + "\n\n"}, {"type": "text", "text": _HISTORY}],
        _STABLE + "\n\n" + _HISTORY,
        id="llm_node_split",
    ),
]


@pytest.mark.parametrize("blocks,rendered", _SPLITS)
class TestUncachedChildrenInAMixedChain:
    def test_openai_passes_the_blocks_through_as_content_parts(self, blocks, rendered):
        from langchain_openai.chat_models.base import _convert_message_to_dict

        assert _convert_message_to_dict(SystemMessage(content=blocks)) == {"role": "system", "content": blocks}

    def test_google_keeps_one_part_per_block(self, blocks, rendered):
        from langchain_google_genai.chat_models import _parse_chat_history

        system, _ = _parse_chat_history(
            [SystemMessage(content=blocks), HumanMessage(content="hi")], convert_system_message_to_human=False
        )
        assert [part.text for part in system.parts] == [block["text"] for block in blocks]

    def test_ollama_injects_a_newline_per_block(self, blocks, rendered):
        """Known deviation: langchain_ollama joins blocks with \\n, so a mixed chain
        sends this child two extra newlines. Delete this test if that formatter changes."""
        from langchain_ollama import ChatOllama

        content = ChatOllama(model="llama3")._convert_messages_to_ollama_messages(
            [SystemMessage(content=blocks), HumanMessage(content="hi")]
        )[0]["content"]

        assert content == "".join("\n" + block["text"] for block in blocks)
        assert content != rendered
