"""Model-layer prompt caching: PromptCachingChatModel marking semantics, what the real
provider formatters serialize, and the build_chat_model opt-in that applies the wrapper"""

import copy
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from langchain_anthropic.chat_models import _format_messages
from langchain_aws.chat_models.bedrock_converse import _messages_to_bedrock
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    HumanMessage,
    SystemMessage,
    ToolMessage,
    message_to_dict,
    messages_from_dict,
)
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult

from app.modules.workflow.llm.fallback_chat_model import FallbackChatModel
from app.modules.workflow.llm.prompt_caching_chat_model import (
    PROMPT_CACHE_OPT_IN_KEY,
    PromptCachingChatModel,
    build_cacheable_system_message,
    model_has_prompt_caching,
)
from app.modules.workflow.llm.provider import LLMProvider, build_chat_model

_STYLES = ["anthropic", "bedrock_converse"]


class _CapturingModel(BaseChatModel):
    seen: list = []
    seen_kwargs: list = []
    text: str = "ok-response"
    tools_bound: list = []
    fail: bool = False

    @property
    def _llm_type(self) -> str:
        return "capturing"

    def _record(self, messages, stop, kwargs) -> None:
        self.seen.append(list(messages))
        self.seen_kwargs.append({"stop": stop, **kwargs})
        if self.fail:
            raise httpx.ConnectError("no route")

    @property
    def last(self) -> list:
        return self.seen[-1]

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        self._record(messages, stop, kwargs)
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=self.text))])

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        self._record(messages, stop, kwargs)
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=self.text))])

    def _stream(self, messages, stop=None, run_manager=None, **kwargs):
        self._record(messages, stop, kwargs)
        yield ChatGenerationChunk(message=AIMessageChunk(content=self.text))

    async def _astream(self, messages, stop=None, run_manager=None, **kwargs):
        self._record(messages, stop, kwargs)
        yield ChatGenerationChunk(message=AIMessageChunk(content=self.text))

    def bind_tools(self, tools, **kwargs):
        return _CapturingModel(text=self.text, tools_bound=list(tools))


def _wrap(style: str) -> tuple[PromptCachingChatModel, _CapturingModel]:
    inner = _CapturingModel()
    return PromptCachingChatModel(inner=inner, cache_style=style), inner


def _system_blocks(sent: list) -> list:
    return [m for m in sent if isinstance(m, SystemMessage)][0].content


def _tagged(content) -> SystemMessage:
    return SystemMessage(content=content, additional_kwargs={PROMPT_CACHE_OPT_IN_KEY: True})


@pytest.mark.asyncio
class TestInversionRule:
    async def test_anthropic_marks_first_block(self):
        wrapper, inner = _wrap("anthropic")
        await wrapper.ainvoke([build_cacheable_system_message("stable"), HumanMessage(content="hi")])
        assert _system_blocks(inner.last) == [
            {"type": "text", "text": "stable", "cache_control": {"type": "ephemeral"}}
        ]

    async def test_bedrock_inserts_cache_point_after_first_block(self):
        wrapper, inner = _wrap("bedrock_converse")
        await wrapper.ainvoke([build_cacheable_system_message("stable"), HumanMessage(content="hi")])
        assert _system_blocks(inner.last) == [
            {"type": "text", "text": "stable"},
            {"cachePoint": {"type": "default"}},
        ]

    @pytest.mark.parametrize("style", _STYLES)
    async def test_plain_string_system_is_never_marked(self, style):
        wrapper, inner = _wrap(style)
        original = _tagged("a plain string prompt")
        await wrapper.ainvoke([original, HumanMessage(content="hi")])
        sent_system = [m for m in inner.last if isinstance(m, SystemMessage)][0]
        assert sent_system.content == "a plain string prompt"
        assert isinstance(sent_system.content, str)

    @pytest.mark.parametrize("style", _STYLES)
    async def test_no_system_message_passes_through(self, style):
        wrapper, inner = _wrap(style)
        messages = [HumanMessage(content="hi")]
        await wrapper.ainvoke(messages)
        assert [m.content for m in inner.last] == ["hi"]


class TestCacheableSystemMessageBuilder:
    def test_two_blocks_when_a_volatile_part_is_given(self):
        assert build_cacheable_system_message("stable", "volatile").content == [
            {"type": "text", "text": "stable"},
            {"type": "text", "text": "volatile"},
        ]

    @pytest.mark.parametrize("volatile", [None, ""], ids=["omitted", "empty"])
    def test_a_missing_volatile_part_emits_one_block(self, volatile):
        assert build_cacheable_system_message("stable", volatile).content == [{"type": "text", "text": "stable"}]

    def test_the_tag_is_stamped(self):
        assert build_cacheable_system_message("stable").additional_kwargs == {PROMPT_CACHE_OPT_IN_KEY: True}

    def test_the_class_stays_a_plain_system_message(self):
        assert type(build_cacheable_system_message("stable")) is SystemMessage


@pytest.mark.asyncio
@pytest.mark.parametrize("style", _STYLES)
class TestOptInTag:

    async def test_untagged_blocks_pass_through_unmarked(self, style):
        wrapper, inner = _wrap(style)
        content = [{"type": "text", "text": "stable"}, {"type": "text", "text": "volatile"}]

        await wrapper.ainvoke([SystemMessage(content=list(content)), HumanMessage(content="hi")])

        assert _system_blocks(inner.last) == content

    @pytest.mark.parametrize("tag", [False, None, 0, ""], ids=["false", "none", "zero", "empty"])
    async def test_a_falsy_tag_never_authorizes_marking(self, style, tag):
        wrapper, inner = _wrap(style)
        message = SystemMessage(
            content=[{"type": "text", "text": "stable"}], additional_kwargs={PROMPT_CACHE_OPT_IN_KEY: tag}
        )

        await wrapper.ainvoke([message, HumanMessage(content="hi")])

        assert _system_blocks(inner.last) == [{"type": "text", "text": "stable"}]

    async def test_a_tagged_message_that_round_tripped_through_a_dict_still_marks(self, style):
        wrapper, inner = _wrap(style)
        restored = messages_from_dict([message_to_dict(build_cacheable_system_message("stable"))])[0]

        await wrapper.ainvoke([restored, HumanMessage(content="hi")])

        assert len(_system_blocks(inner.last)) == (1 if style == "anthropic" else 2)


@pytest.mark.asyncio
class TestBlockSelection:
    @pytest.mark.parametrize(
        "style,expected",
        [
            (
                "anthropic",
                [
                    {"type": "text", "text": "stable base", "cache_control": {"type": "ephemeral"}},
                    {"type": "text", "text": "volatile suffix"},
                ],
            ),
            (
                "bedrock_converse",
                [
                    {"type": "text", "text": "stable base"},
                    {"cachePoint": {"type": "default"}},
                    {"type": "text", "text": "volatile suffix"},
                ],
            ),
        ],
    )
    async def test_only_first_block_is_selected(self, style, expected):
        wrapper, inner = _wrap(style)
        await wrapper.ainvoke(
            [
                build_cacheable_system_message("stable base", "volatile suffix"),
                HumanMessage(content="hi"),
            ]
        )
        assert _system_blocks(inner.last) == expected

    @pytest.mark.parametrize("style", _STYLES)
    @pytest.mark.parametrize(
        "first_block",
        [
            {"type": "text", "text": ""},
            {"type": "text", "text": "   "},
            {"type": "text"},
            {"type": "image", "source": {"data": "x"}},
            "a bare string block",
        ],
        ids=["empty", "whitespace", "no-text-key", "non-text-type", "not-a-dict"],
    )
    async def test_blank_or_non_text_first_block_is_untouched(self, style, first_block):
        wrapper, inner = _wrap(style)
        content = [first_block, {"type": "text", "text": "later"}]
        await wrapper.ainvoke([_tagged(list(content)), HumanMessage(content="hi")])
        assert _system_blocks(inner.last) == content

    @pytest.mark.parametrize("style", _STYLES)
    async def test_empty_block_list_is_untouched(self, style):
        wrapper, inner = _wrap(style)
        await wrapper.ainvoke([_tagged([]), HumanMessage(content="hi")])
        assert _system_blocks(inner.last) == []

    @pytest.mark.parametrize(
        "style,already_marked",
        [
            ("anthropic", [{"type": "text", "text": "a", "cache_control": {"type": "ephemeral"}}]),
            ("bedrock_converse", [{"type": "text", "text": "a"}, {"cachePoint": {"type": "default"}}]),
        ],
    )
    async def test_idempotent_when_already_marked(self, style, already_marked):
        wrapper, inner = _wrap(style)
        await wrapper.ainvoke([_tagged(list(already_marked)), HumanMessage(content="hi")])
        assert _system_blocks(inner.last) == already_marked

    @pytest.mark.parametrize("style", _STYLES)
    async def test_marker_placed_elsewhere_is_left_alone(self, style):
        wrapper, inner = _wrap(style)
        if style == "anthropic":
            content = [
                {"type": "text", "text": "a"},
                {"type": "text", "text": "b", "cache_control": {"type": "ephemeral"}},
            ]
        else:
            content = [
                {"type": "text", "text": "a"},
                {"type": "text", "text": "b"},
                {"cachePoint": {"type": "default"}},
            ]
        await wrapper.ainvoke([_tagged(list(content)), HumanMessage(content="hi")])
        assert _system_blocks(inner.last) == content

    @pytest.mark.parametrize("style", _STYLES)
    async def test_only_the_first_system_message_is_considered(self, style):
        wrapper, inner = _wrap(style)
        await wrapper.ainvoke(
            [
                build_cacheable_system_message("first"),
                HumanMessage(content="hi"),
                build_cacheable_system_message("second"),
            ]
        )
        systems = [m for m in inner.last if isinstance(m, SystemMessage)]
        assert systems[1].content == [{"type": "text", "text": "second"}]
        assert len(systems[0].content) == (1 if style == "anthropic" else 2)

    @pytest.mark.parametrize("style", _STYLES)
    async def test_first_system_ineligible_does_not_fall_through_to_a_later_one(self, style):
        wrapper, inner = _wrap(style)
        await wrapper.ainvoke(
            [
                _tagged("plain"),
                HumanMessage(content="hi"),
                build_cacheable_system_message("second"),
            ]
        )
        systems = [m for m in inner.last if isinstance(m, SystemMessage)]
        assert systems[0].content == "plain"
        assert systems[1].content == [{"type": "text", "text": "second"}]


@pytest.mark.asyncio
class TestCopyOnWrite:
    @pytest.mark.parametrize("style", _STYLES)
    async def test_caller_objects_are_never_mutated(self, style):
        wrapper, inner = _wrap(style)
        system = build_cacheable_system_message("stable", "suffix")
        messages = [system, HumanMessage(content="hi")]
        original_content = system.content
        original_first = original_content[0]
        before = copy.deepcopy(messages)

        await wrapper.ainvoke(messages)

        assert [m.content for m in messages] == [m.content for m in before]
        assert system.content is original_content
        assert original_content[0] is original_first
        assert original_first == {"type": "text", "text": "stable"}
        assert inner.last is not messages
        assert inner.last[0] is not system

    @pytest.mark.parametrize("style", _STYLES)
    async def test_repeated_invocations_do_not_accumulate_markers(self, style):
        wrapper, inner = _wrap(style)
        messages = [build_cacheable_system_message("stable"), HumanMessage(content="hi")]
        await wrapper.ainvoke(messages)
        await wrapper.ainvoke(messages)
        assert _system_blocks(inner.seen[0]) == _system_blocks(inner.seen[1])


class TestMethodContracts:
    @pytest.mark.asyncio
    async def test_agenerate_returns_chat_result(self):
        wrapper, _ = _wrap("anthropic")
        result = await wrapper._agenerate([HumanMessage(content="hi")])
        assert isinstance(result, ChatResult)
        assert result.generations[0].message.content == "ok-response"

    def test_generate_returns_chat_result(self):
        wrapper, _ = _wrap("anthropic")
        result = wrapper._generate([HumanMessage(content="hi")])
        assert isinstance(result, ChatResult)
        assert result.generations[0].message.content == "ok-response"

    @pytest.mark.asyncio
    async def test_astream_marks_and_yields_chunks(self):
        wrapper, inner = _wrap("anthropic")
        out = "".join(
            [
                chunk.content
                async for chunk in wrapper.astream(
                    [build_cacheable_system_message("stable"), HumanMessage(content="hi")]
                )
            ]
        )
        assert out == "ok-response"
        assert _system_blocks(inner.last)[0]["cache_control"] == {"type": "ephemeral"}

    def test_stream_marks_and_yields_chunks(self):
        wrapper, inner = _wrap("bedrock_converse")
        out = "".join(
            chunk.content
            for chunk in wrapper.stream([build_cacheable_system_message("stable"), HumanMessage(content="hi")])
        )
        assert out == "ok-response"
        assert _system_blocks(inner.last)[1] == {"cachePoint": {"type": "default"}}

    @pytest.mark.asyncio
    async def test_stop_and_kwargs_are_forwarded(self):
        wrapper, inner = _wrap("anthropic")
        await wrapper.ainvoke([HumanMessage(content="hi")], stop=["</end>"], temperature=0.3)
        assert inner.seen_kwargs[-1]["stop"] == ["</end>"]
        assert inner.seen_kwargs[-1]["temperature"] == 0.3

    @pytest.mark.asyncio
    async def test_stop_absent_when_not_supplied(self):
        wrapper, inner = _wrap("anthropic")
        await wrapper.ainvoke([HumanMessage(content="hi")])
        assert inner.seen_kwargs[-1]["stop"] is None

    @pytest.mark.asyncio
    async def test_astream_forwards_stop_and_kwargs(self):
        wrapper, inner = _wrap("anthropic")
        async for _ in wrapper.astream([HumanMessage(content="hi")], stop=["</end>"], temperature=0.3):
            pass
        assert inner.seen_kwargs[-1]["stop"] == ["</end>"]
        assert inner.seen_kwargs[-1]["temperature"] == 0.3

    def test_stream_forwards_stop_and_kwargs(self):
        wrapper, inner = _wrap("anthropic")
        list(wrapper.stream([HumanMessage(content="hi")], stop=["</end>"], temperature=0.3))
        assert inner.seen_kwargs[-1]["stop"] == ["</end>"]
        assert inner.seen_kwargs[-1]["temperature"] == 0.3

    def test_llm_type(self):
        wrapper, _ = _wrap("anthropic")
        assert wrapper._llm_type == "prompt_caching_chat_model"


@pytest.mark.asyncio
class TestBindTools:
    async def test_bind_tools_rewraps_and_keeps_marking(self):
        wrapper, _ = _wrap("bedrock_converse")
        bound = wrapper.bind_tools([{"name": "search"}])
        assert isinstance(bound, PromptCachingChatModel)
        assert bound.cache_style == "bedrock_converse"
        assert bound.inner.tools_bound == [{"name": "search"}]

        await bound.ainvoke([build_cacheable_system_message("stable"), HumanMessage(content="hi")])
        assert _system_blocks(bound.inner.last)[1] == {"cachePoint": {"type": "default"}}


@pytest.mark.asyncio
class TestRunnableBinding:
    async def test_bind_keeps_marking_and_forwards_its_kwargs(self):
        """`.bind()` wraps outside — the shape router_node and nlp_node already use."""
        wrapper, inner = _wrap("bedrock_converse")
        bound = wrapper.bind(temperature=0)

        await bound.ainvoke([build_cacheable_system_message("stable"), HumanMessage(content="hi")])

        assert _system_blocks(inner.last)[1] == {"cachePoint": {"type": "default"}}
        assert inner.seen_kwargs[-1]["temperature"] == 0


def _loop_turn(tail) -> list:
    return [
        build_cacheable_system_message("stable"),
        HumanMessage(content="hi"),
        AIMessage(content="calling", tool_calls=[{"name": "t", "args": {}, "id": "tc1"}]),
        tail,
    ]


class TestSystemPrefixOnly:

    @pytest.mark.asyncio
    async def test_a_tool_loop_turn_carries_no_cache_point_in_messages(self):
        llm, _ = await _build("bedrock", {}, "eu.amazon.nova-2-lite-v1:0")
        bound = llm.bind_tools([{"name": "search"}])
        bound.inner = _CapturingModel()

        await bound.ainvoke(_loop_turn(ToolMessage(content="result", tool_call_id="tc1")))

        messages, system = _messages_to_bedrock(bound.inner.last)
        assert "cachePoint" not in str(messages), "a cachePoint in messages fails the call"
        assert {"cachePoint": {"type": "default"}} in system, "the system prefix still caches"


class TestLangChainIntrospection:
    def test_provider_strategy_probe_reads_no_model_name(self):
        """LangChain reads `.model` as a model-name string; a child model there crashes it.

        Pinned against langchain's private helper on purpose — an upgrade that moves it
        should re-open the question rather than pass silently.
        """
        from langchain.agents.factory import _supports_provider_strategy

        plain = _CapturingModel()
        wrapper = PromptCachingChatModel(inner=plain, cache_style="anthropic")

        assert _supports_provider_strategy(wrapper) is False
        assert _supports_provider_strategy(plain) is False
        assert _supports_provider_strategy(FallbackChatModel(models=[plain, wrapper])) is False


class TestModelHasPromptCaching:
    def test_truth_table(self):
        plain = _CapturingModel()
        wrapper = PromptCachingChatModel(inner=_CapturingModel(), cache_style="anthropic")

        assert model_has_prompt_caching(wrapper) is True
        assert model_has_prompt_caching(plain) is False
        assert model_has_prompt_caching(None) is False
        assert model_has_prompt_caching(FallbackChatModel(models=[wrapper])) is True
        assert model_has_prompt_caching(FallbackChatModel(models=[wrapper, wrapper])) is True
        assert model_has_prompt_caching(FallbackChatModel(models=[plain, wrapper])) is False
        assert model_has_prompt_caching(FallbackChatModel(models=[wrapper, plain])) is False
        assert model_has_prompt_caching(FallbackChatModel(models=[plain, plain])) is False
        assert model_has_prompt_caching(FallbackChatModel(models=[])) is False

    def test_survives_chain_wide_bind_tools(self):
        chain = FallbackChatModel(
            models=[
                PromptCachingChatModel(inner=_CapturingModel(), cache_style="anthropic"),
                PromptCachingChatModel(inner=_CapturingModel(), cache_style="anthropic"),
            ],
            provider_ids=["p1", "p2"],
        )
        assert model_has_prompt_caching(chain.bind_tools([{"name": "search"}])) is True


class TestMixedFallbackChain:

    @pytest.mark.parametrize("position", [0, 1], ids=["primary", "fallback"])
    def test_a_single_unwrapped_child_disables_the_chain(self, position):
        models = [PromptCachingChatModel(inner=_CapturingModel(), cache_style="anthropic") for _ in range(2)]
        models[position] = _CapturingModel()

        assert model_has_prompt_caching(FallbackChatModel(models=models, provider_ids=["p1", "p2"])) is False


@pytest.mark.asyncio
class TestHomogeneousFallbackChain:
    async def test_failover_to_a_wrapped_child_still_marks(self):
        primary_inner = _CapturingModel(fail=True)
        fallback_inner = _CapturingModel(text="from-fallback-child")
        chain = FallbackChatModel(
            models=[
                PromptCachingChatModel(inner=primary_inner, cache_style="anthropic"),
                PromptCachingChatModel(inner=fallback_inner, cache_style="anthropic"),
            ],
            provider_ids=["p1", "p2"],
        )
        system = build_cacheable_system_message("stable")
        messages = [system, HumanMessage(content="hi")]
        original_content = system.content

        assert model_has_prompt_caching(chain) is True
        resp = await chain.ainvoke(messages)
        assert resp.content == "from-fallback-child"
        for inner in (primary_inner, fallback_inner):
            assert _system_blocks(inner.last) == [
                {"type": "text", "text": "stable", "cache_control": {"type": "ephemeral"}}
            ]
        assert messages[0] is system
        assert system.content is original_content
        assert original_content == [{"type": "text", "text": "stable"}]


_STABLE = "You are a helpful assistant with a long stable prefix."
_VOLATILE = "Current time: 2026-08-17T10:00:00Z"


async def _sent(style: str, system_content) -> list:
    wrapper, inner = _wrap(style)
    await wrapper.ainvoke([_tagged(system_content), HumanMessage(content="hello")])
    return inner.last


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

_LEGACY_RENDERINGS = [
    pytest.param(_STABLE + _AGENT_SUFFIX, id="agent_split"),
    pytest.param(_STABLE + "\n\n" + _HISTORY, id="llm_node_split"),
]


class TestOptInTagStaysInProcess:

    def test_it_survives_a_dict_round_trip(self):
        message = build_cacheable_system_message(_STABLE, _VOLATILE)

        restored = messages_from_dict([message_to_dict(message)])[0]

        assert type(restored) is SystemMessage
        assert restored.additional_kwargs[PROMPT_CACHE_OPT_IN_KEY] is True
        assert restored.content == message.content

    def test_anthropic_never_sees_it(self):
        system, messages = _format_messages(
            [build_cacheable_system_message(_STABLE, _VOLATILE), HumanMessage(content="hello")]
        )

        assert not _contains_key(system, PROMPT_CACHE_OPT_IN_KEY)
        assert not _contains_key(messages, PROMPT_CACHE_OPT_IN_KEY)

    def test_bedrock_never_sees_it(self):
        messages, system = _messages_to_bedrock(
            [build_cacheable_system_message(_STABLE, _VOLATILE), HumanMessage(content="hello")]
        )

        assert not _contains_key(system, PROMPT_CACHE_OPT_IN_KEY)
        assert not _contains_key(messages, PROMPT_CACHE_OPT_IN_KEY)

    def test_openai_never_sees_it(self):
        from langchain_openai.chat_models.base import _convert_message_to_dict

        assert not _contains_key(
            _convert_message_to_dict(build_cacheable_system_message(_STABLE, _VOLATILE)), PROMPT_CACHE_OPT_IN_KEY
        )


@pytest.mark.parametrize("rendered", _LEGACY_RENDERINGS)
class TestMixedChainKeepsTheLegacyString:

    def test_openai_receives_the_flattened_string(self, rendered):
        from langchain_openai.chat_models.base import _convert_message_to_dict

        assert _convert_message_to_dict(SystemMessage(content=rendered)) == {"role": "system", "content": rendered}

    def test_google_receives_one_part(self, rendered):
        from langchain_google_genai.chat_models import _parse_chat_history

        system, _ = _parse_chat_history(
            [SystemMessage(content=rendered), HumanMessage(content="hi")], convert_system_message_to_human=False
        )
        assert [part.text for part in system.parts] == [rendered]

    def test_ollama_receives_the_flattened_string(self, rendered):
        from langchain_ollama import ChatOllama

        content = ChatOllama(model="llama3")._convert_messages_to_ollama_messages(
            [SystemMessage(content=rendered), HumanMessage(content="hi")]
        )[0]["content"]

        assert content == rendered


_INIT = "langchain.chat_models.init_chat_model"
_OPIK = "app.modules.workflow.llm.opik_tracing.get_opik_callbacks"


async def _build(provider, connection_data, model_name="a-model", requested=True):
    """One build with the node opt-in on, unless a case is about the default-off path"""
    with patch(_INIT) as init:
        init.return_value = MagicMock(name="inner-model")
        llm = await build_chat_model(provider, connection_data, model_name, requested)
    return llm, init


@pytest.mark.asyncio
class TestWrappedProviders:
    async def test_anthropic_flag_wraps_with_anthropic_style(self):
        llm, init = await _build("anthropic", {"api_key": "k"})
        assert isinstance(llm, PromptCachingChatModel)
        assert llm.cache_style == "anthropic"
        assert llm.inner is init.return_value
        assert "prompt_caching_enabled" not in init.call_args.kwargs

    async def test_bedrock_flag_wraps_with_bedrock_converse_style(self):
        llm, init = await _build(
            "bedrock",
            {"region_name": "eu-central-1"},
            "eu.anthropic.claude-sonnet-4-5-v1:0",
        )
        assert isinstance(llm, PromptCachingChatModel)
        assert llm.cache_style == "bedrock_converse"
        assert init.call_args.kwargs["model_provider"] == "bedrock_converse"
        assert "prompt_caching_enabled" not in init.call_args.kwargs


@pytest.mark.asyncio
class TestBedrockFamilyGuard:

    @pytest.mark.parametrize(
        "model_name",
        [
            "eu.amazon.nova-2-lite-v1:0",
            "us.amazon.nova-pro-v1:0",
            "us.amazon.nova-premier-v1:0",
            "eu.anthropic.claude-3-5-sonnet-20241022-v2:0",
            "us.anthropic.claude-sonnet-4-5-v1:0",
            "global.anthropic.claude-sonnet-5",
            "global.anthropic.claude-opus-5",
            "us.anthropic.claude-fable-5",
        ],
    )
    async def test_cacheable_families_wrap(self, model_name):
        llm, _ = await _build("bedrock", {}, model_name)
        assert isinstance(llm, PromptCachingChatModel)

    @pytest.mark.parametrize(
        "model_name",
        [
            "meta.llama3-3-70b-instruct-v1:0",
            "mistral.mistral-large-2407-v1:0",
            "amazon.titan-text-premier-v1:0",
            "deepseek.r1-v1:0",
        ],
    )
    async def test_families_without_cache_support_run_uncached(self, model_name):
        llm, init = await _build("bedrock", {}, model_name)
        assert llm is init.return_value, "wrapping these fails every call with a ValidationException"

    @pytest.mark.parametrize("model_name", ["amazon.nova-sonic-v1:0", "amazon.nova-2-sonic-v1:0"])
    async def test_speech_novas_run_uncached(self, model_name):
        llm, init = await _build("bedrock", {}, model_name)
        assert llm is init.return_value

    @pytest.mark.parametrize(
        "model_name",
        [
            "anthropic.claude-3-haiku-20240307-v1:0",
            "anthropic.claude-3-sonnet-20240229-v1:0",
            "anthropic.claude-3-opus-20240229-v1:0",
            "us.anthropic.claude-3-5-sonnet-20240620-v1:0",
        ],
    )
    async def test_non_cacheable_claude_versions_run_uncached(self, model_name):
        llm, init = await _build("bedrock", {}, model_name)
        assert llm is init.return_value, "wrapping these fails every call with a ValidationException"

    @pytest.mark.parametrize(
        "model_name",
        [
            "arn:aws:bedrock:eu-central-1::foundation-model/amazon.nova-2-lite-v1:0",
            "arn:aws:bedrock:us-east-1::inference-profile/us.anthropic.claude-sonnet-4-5-v1:0",
            "arn:aws:bedrock:us-east-1::inference-profile/global.anthropic.claude-fable-5",
        ],
    )
    async def test_arn_wraps_on_a_model_it_names_itself(self, model_name):
        llm, _ = await _build("bedrock", {"model_provider": "amazon"}, model_name)
        assert isinstance(llm, PromptCachingChatModel)

    @pytest.mark.parametrize("model_provider", ["anthropic", "amazon"])
    async def test_opaque_arns_stay_uncached(self, model_provider):
        llm, init = await _build(
            "bedrock",
            {"model_provider": model_provider},
            "arn:aws:bedrock:eu-central-1:123456789012:provisioned-model/abc123",
        )
        assert llm is init.return_value

    @pytest.mark.parametrize(
        "model_name",
        [
            "arn:aws:bedrock:us-east-1:123456789012:custom-model/my-nova-finetune",
            "arn:aws:bedrock:us-east-1:123456789012:provisioned-model/nova-throughput",
            "arn:aws:bedrock:us-east-1:123456789012:custom-model/claude-sonnet-5-finetune",
            "arn:aws:bedrock:eu-central-1:123456789012:provisioned-model/claude-fable-5-throughput",
        ],
    )
    async def test_a_deployment_arn_never_inherits_its_base_family(self, model_name):
        llm, init = await _build("bedrock", {"model_provider": "amazon"}, model_name)
        assert llm is init.return_value

    async def test_missing_model_name_stays_uncached(self):
        llm, init = await _build("bedrock", {}, None)
        assert llm is init.return_value

    async def test_anthropic_direct_is_unaffected_by_the_model_name(self):
        llm, _ = await _build("anthropic", {"api_key": "k"}, "some-model")
        assert isinstance(llm, PromptCachingChatModel)


@pytest.mark.asyncio
class TestUnwrappedCases:
    async def test_the_default_is_off(self):
        llm, init = await _build("anthropic", {"api_key": "k"}, requested=False)
        assert llm is init.return_value

    async def test_an_unset_parameter_is_off(self):
        with patch(_INIT) as init:
            init.return_value = MagicMock(name="inner-model")
            llm = await build_chat_model("anthropic", {"api_key": "k"}, "a-model")
        assert llm is init.return_value

    async def test_an_opted_in_openai_provider_stays_plain(self):
        llm, init = await _build("openai", {"api_key": "k"})
        assert llm is init.return_value
        assert "prompt_caching_enabled" not in init.call_args.kwargs

    @pytest.mark.parametrize("raw", [True, "true", "false", 1, 0, None, ""], ids=repr)
    async def test_a_stale_stored_key_never_decides_anything(self, raw):
        llm, init = await _build("anthropic", {"api_key": "k", "prompt_caching_enabled": raw}, requested=False)
        assert llm is init.return_value
        assert "prompt_caching_enabled" not in init.call_args.kwargs

    async def test_a_stale_stored_key_is_popped_from_an_opted_in_build_too(self):
        llm, init = await _build("anthropic", {"api_key": "k", "prompt_caching_enabled": True})
        assert isinstance(llm, PromptCachingChatModel)
        assert "prompt_caching_enabled" not in init.call_args.kwargs

    async def test_the_stored_connection_data_is_never_rewritten(self):
        connection_data = {"api_key": "k", "prompt_caching_enabled": True}
        await _build("anthropic", connection_data)
        assert connection_data == {"api_key": "k", "prompt_caching_enabled": True}


@pytest.mark.asyncio
class TestOpikCallbacks:
    async def test_callbacks_stay_on_the_inner_model(self):
        callback = MagicMock(name="opik-tracer")
        with patch(_OPIK, return_value=[callback]):
            llm, init = await _build("anthropic", {"api_key": "k"})
        assert init.call_args.kwargs["callbacks"] == [callback]
        assert llm.callbacks is None


def _patch_provider_lookups(chain=None):
    from app.services.fallback_chains import FallbackChainService

    provider_service = MagicMock()
    provider_service.get_by_id = AsyncMock(return_value=SimpleNamespace(id="p1"))
    chain_service = MagicMock()
    chain_service.get_by_id = AsyncMock(return_value=chain)

    inj = MagicMock()
    inj.get = MagicMock(
        side_effect=lambda cls: chain_service if cls is FallbackChainService else provider_service
    )
    return patch("app.dependencies.injector.injector", inj)


def _fallback_chain(provider_ids):
    return SimpleNamespace(provider_ids=provider_ids, retry_policy=None)


@pytest.mark.asyncio
@pytest.mark.parametrize("requested", [True, False], ids=["opted-in", "default-off"])
class TestOptInThreading:

    @staticmethod
    def _spy():
        build = AsyncMock(return_value=MagicMock(name="built-model"))
        return build, patch.object(LLMProvider, "_build_from_provider", build)

    @staticmethod
    def _flags(build):
        return [
            call.kwargs.get("prompt_caching_enabled", call.args[1] if len(call.args) > 1 else False)
            for call in build.await_args_list
        ]

    async def _run(self, requested, coro_factory, chain=None):
        build, spy = self._spy()
        with _patch_provider_lookups(chain), spy:
            await coro_factory(LLMProvider())
        return self._flags(build)

    async def test_get_model(self, requested):
        flags = await self._run(requested, lambda p: p.get_model("p1", requested))
        assert flags == [requested]

    async def test_get_model_for_node_without_a_chain(self, requested):
        flags = await self._run(requested, lambda p: p.get_model_for_node("p1", None, requested))
        assert flags == [requested]

    async def test_single_provider_fast_path(self, requested):
        flags = await self._run(requested, lambda p: p.get_model_with_fallback(["p1"], None, requested))
        assert flags == [requested]

    async def test_every_child_of_a_multi_provider_chain(self, requested):
        flags = await self._run(
            requested, lambda p: p.get_model_with_fallback(["p1", "p2", "p3"], {"retry_count": 1}, requested)
        )
        assert flags == [requested] * 3

    async def test_get_model_for_node_with_a_chain_id(self, requested):
        flags = await self._run(
            requested,
            lambda p: p.get_model_for_node("p1", "chain-1", requested),
            chain=_fallback_chain(["p2"]),
        )
        assert flags == [requested] * 2
