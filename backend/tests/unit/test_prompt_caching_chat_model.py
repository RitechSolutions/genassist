"""Unit tests for PromptCachingChatModel"""

import copy

import httpx
import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    HumanMessage,
    SystemMessage,
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
