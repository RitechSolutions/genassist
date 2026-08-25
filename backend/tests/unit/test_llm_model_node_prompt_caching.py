"""Unit tests for the LLM node's prompt-caching opt-in"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from app.modules.workflow.engine.nodes.llm_model_node import LLMModelNode
from app.modules.workflow.llm.fallback_chat_model import FallbackChatModel
from app.modules.workflow.llm.prompt_caching_chat_model import (
    PROMPT_CACHE_OPT_IN_KEY,
    PromptCachingChatModel,
)
from app.modules.workflow.llm.provider import LLMProvider

_BASE = "You are a helpful assistant with a long stable prefix."
_HISTORY = "User: hi\nAssistant: hello"
_STYLES = ["anthropic", "bedrock_converse"]


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


class _RaisingModel(_CapturingModel):

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        raise RuntimeError("provider unavailable")


class _FakeMemory:
    def __init__(self, history: str):
        self._history = history

    async def get_chat_history(self, as_string: bool = False, max_messages: int = 10) -> str:
        return self._history


class _FakeState:
    def __init__(self, memory=None):
        self._memory = memory
        self.llm_usage: list = []
        self.prompt_caching_diagnostics: dict = {}

    def get_memory(self):
        return self._memory

    def get_value(self, key, default=None):
        return default

    def add_llm_usage(self, **kwargs):
        self.llm_usage.append(kwargs)


def _patch_injector(llm):
    provider = MagicMock()
    provider.get_model_for_node = AsyncMock(return_value=llm)
    service = MagicMock()
    service.get_by_id = AsyncMock(
        return_value=SimpleNamespace(llm_model_provider="anthropic", llm_model="claude-sonnet-4-5")
    )
    inj = MagicMock()
    inj.get = MagicMock(side_effect=lambda cls: provider if cls is LLMProvider else service)
    return patch("app.dependencies.injector.injector", inj), provider


def _caching_llm(style: str = "anthropic"):
    inner = _CapturingModel()
    return PromptCachingChatModel(inner=inner, cache_style=style), inner


def _plain_llm():
    inner = _CapturingModel()
    return inner, inner


async def _run(llm, *, raw=_BASE, resolved=None, history=None, node_data=None):
    memory = _FakeMemory(history) if history is not None else None
    data = node_data if node_data is not None else {"systemPrompt": raw}
    node = LLMModelNode("llm-1", {"type": "llmModelNode", "data": data}, _FakeState(memory=memory))

    config = {
        "providerId": "p1",
        "systemPrompt": _BASE if resolved is None else resolved,
        "userPrompt": "hello",
        "memory": memory is not None,
    }
    ctx, _ = _patch_injector(llm)
    with ctx:
        return await node.process(config)


def _sent(inner: _CapturingModel) -> list:
    return inner.seen[-1]


def _system_content(inner: _CapturingModel):
    return _sent(inner)[0].content


def _rendered(content) -> str:
    # Assumes the provider joins system blocks with no separator; only an E2E call proves it.
    if isinstance(content, str):
        return content
    return "".join(block.get("text", "") for block in content)


def _text_blocks(content) -> list:
    return [block for block in content if "text" in block]


@pytest.mark.asyncio
@pytest.mark.parametrize("style", _STYLES)
class TestRenderingIsByteIdentical:

    async def test_memory_on_with_history(self, style):
        cached, cached_inner = _caching_llm(style)
        plain, plain_inner = _plain_llm()

        await _run(cached, history=_HISTORY)
        await _run(plain, history=_HISTORY)

        assert _rendered(_system_content(cached_inner)) == _BASE + "\n\n" + _HISTORY
        assert _rendered(_system_content(cached_inner)) == _system_content(plain_inner)

    async def test_memory_on_with_empty_first_turn_history(self, style):
        cached, cached_inner = _caching_llm(style)
        plain, plain_inner = _plain_llm()

        await _run(cached, history="")
        await _run(plain, history="")

        assert _rendered(_system_content(cached_inner)) == _BASE + "\n\n"
        assert _rendered(_system_content(cached_inner)) == _system_content(plain_inner)

    async def test_memory_off(self, style):
        cached, cached_inner = _caching_llm(style)
        plain, plain_inner = _plain_llm()

        await _run(cached)
        await _run(plain)

        assert _rendered(_system_content(cached_inner)) == _BASE
        assert _rendered(_system_content(cached_inner)) == _system_content(plain_inner)


@pytest.mark.asyncio
class TestBlockShapes:
    async def test_anthropic_marks_only_the_stable_block(self):
        llm, inner = _caching_llm("anthropic")

        await _run(llm, history=_HISTORY)

        assert _system_content(inner) == [
            {"type": "text", "text": _BASE + "\n\n", "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": _HISTORY},
        ]

    async def test_bedrock_cache_point_sits_between_prefix_and_history(self):
        llm, inner = _caching_llm("bedrock_converse")

        await _run(llm, history=_HISTORY)

        assert _system_content(inner) == [
            {"type": "text", "text": _BASE + "\n\n"},
            {"cachePoint": {"type": "default"}},
            {"type": "text", "text": _HISTORY},
        ]

    async def test_memory_off_sends_a_single_block(self):
        llm, inner = _caching_llm("anthropic")

        await _run(llm)

        assert _system_content(inner) == [{"type": "text", "text": _BASE, "cache_control": {"type": "ephemeral"}}]

    @pytest.mark.parametrize("style", _STYLES)
    async def test_empty_history_emits_no_blank_block(self, style):
        llm, inner = _caching_llm(style)

        await _run(llm, history="")

        blocks = _text_blocks(_system_content(inner))
        assert len(blocks) == 1
        assert blocks[0]["text"].strip()

    async def test_the_system_turn_carries_the_opt_in_tag(self):
        llm, inner = _caching_llm("anthropic")

        await _run(llm, history=_HISTORY)

        assert _sent(inner)[0].additional_kwargs == {PROMPT_CACHE_OPT_IN_KEY: True}

    async def test_the_uncached_system_turn_carries_no_tag(self):
        llm, inner = _plain_llm()

        await _run(llm, history=_HISTORY)

        assert _sent(inner)[0].additional_kwargs == {}

    async def test_user_turn_is_untouched_by_the_split(self):
        llm, inner = _caching_llm("anthropic")

        await _run(llm, history=_HISTORY)

        assert _sent(inner)[1].content == [{"type": "text", "text": "hello"}]

    async def test_node_still_returns_the_model_content(self):
        llm, _ = _caching_llm("anthropic")

        assert await _run(llm, history=_HISTORY) == "ok"


@pytest.mark.asyncio
class TestStringPathIsPreserved:
    async def test_model_without_caching_keeps_the_single_string(self):
        llm, inner = _plain_llm()

        await _run(llm, history=_HISTORY)

        assert _system_content(inner) == _BASE + "\n\n" + _HISTORY

    @pytest.mark.parametrize("prompt", ["", "   \n "], ids=["empty", "whitespace"])
    async def test_blank_prompt_keeps_the_single_string(self, prompt):
        llm, inner = _caching_llm("anthropic")

        await _run(llm, raw=prompt, resolved=prompt, history=_HISTORY)

        assert _system_content(inner) == prompt + "\n\n" + _HISTORY

    async def test_blank_prompt_without_memory_keeps_the_single_string(self):
        llm, inner = _caching_llm("anthropic")

        await _run(llm, raw="", resolved="")

        assert _system_content(inner) == ""

    @pytest.mark.parametrize(
        "var",
        [
            "{{source}}",
            "{{source.text}}",
            "{{sourceLanguage}}",
            "{{direct_input}}",
            "{{direct_input.query}}",
            "{{node_outputs.node-1.result}}",
            "{{timestamp}}",
            "{{execution_id}}",
            "{{session.message}}",
            "{{session}}",
            "{{session.language}}",
            "{{thread_id}}",
            "{{customer_name}}",
            "{{message}}",
            "{{output}}",
            "{{current_step}}",
        ],
    )
    async def test_volatile_template_var_keeps_the_single_string(self, var):
        llm, inner = _caching_llm("anthropic")

        await _run(llm, raw=f"Summarize this: {var}", resolved="Summarize this: a bug report", history=_HISTORY)

        assert _system_content(inner) == "Summarize this: a bug report" + "\n\n" + _HISTORY

    async def test_raw_prompt_absent_from_node_data_still_opts_in(self):
        llm, inner = _caching_llm("anthropic")

        await _run(llm, node_data={}, history=_HISTORY)

        assert _system_content(inner)[0]["cache_control"] == {"type": "ephemeral"}


@pytest.mark.asyncio
class TestFallbackChain:
    async def test_chain_with_every_child_cached_opts_in_chain_wide(self):
        primary, primary_inner = _caching_llm("anthropic")
        chain = FallbackChatModel(models=[primary, _caching_llm("anthropic")[0]])

        await _run(chain, history=_HISTORY)

        assert _system_content(primary_inner) == [
            {"type": "text", "text": _BASE + "\n\n", "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": _HISTORY},
        ]

    async def test_mixed_chain_keeps_the_single_string(self):
        primary = _CapturingModel()
        chain = FallbackChatModel(models=[primary, _caching_llm("anthropic")[0]])

        await _run(chain, history=_HISTORY)

        assert _system_content(primary) == _BASE + "\n\n" + _HISTORY

    async def test_chain_without_a_cached_child_keeps_the_single_string(self):
        primary = _CapturingModel()
        chain = FallbackChatModel(models=[primary, _CapturingModel()])

        await _run(chain, history=_HISTORY)

        assert _system_content(primary) == _BASE + "\n\n" + _HISTORY


async def _forward(llm, **config_overrides):
    state = _FakeState()
    node = LLMModelNode("llm-1", {"type": "llmModelNode", "data": {"systemPrompt": _BASE}}, state)
    config = {"providerId": "p1", "systemPrompt": _BASE, "userPrompt": "hello", **config_overrides}

    ctx, provider = _patch_injector(llm)
    with ctx:
        await node.process(config)
    return provider, state


@pytest.mark.asyncio
class TestNodeOptInForwarding:

    async def test_the_toggle_reaches_the_model_build(self):
        provider, _ = await _forward(_caching_llm()[0], promptCaching=True)

        assert provider.get_model_for_node.await_args.args == ("p1", None, True)

    @pytest.mark.parametrize("raw", [None, False, "true", "True", 1, "1"], ids=repr)
    async def test_only_a_real_true_requests_caching(self, raw):
        config = {} if raw is None else {"promptCaching": raw}
        provider, _ = await _forward(_plain_llm()[0], **config)

        assert provider.get_model_for_node.await_args.args == ("p1", None, False)

    async def test_the_chain_id_still_travels_with_the_toggle(self):
        provider, _ = await _forward(_plain_llm()[0], fallbackChainId="chain-1", promptCaching=True)

        assert provider.get_model_for_node.await_args.args == ("p1", "chain-1", True)

    async def test_usage_entries_carry_the_request(self):
        _, state = await _forward(_caching_llm()[0], promptCaching=True)

        assert state.llm_usage[0]["prompt_caching_enabled"] is True

    async def test_usage_entries_stay_unmarked_when_the_toggle_is_off(self):
        _, state = await _forward(_plain_llm()[0])

        assert state.llm_usage[0]["prompt_caching_enabled"] is False

    async def test_chain_of_thought_forwards_the_request_too(self):
        with patch("app.modules.workflow.engine.nodes.llm_model_node.ChainOfThoughtAgent") as agent_cls:
            agent_cls.return_value.invoke = AsyncMock(return_value={"response": "ok"})
            provider, _ = await _forward(_plain_llm()[0], type="Chain-of-Thought", promptCaching=True)

        assert provider.get_model_for_node.await_args.args == ("p1", None, True)


async def _diagnose(llm, *, raw=_BASE, resolved=None, history=None, node_data=None, **config_overrides):
    memory = _FakeMemory(history) if history is not None else None
    data = node_data if node_data is not None else {"systemPrompt": raw}
    state = _FakeState(memory=memory)
    node = LLMModelNode("llm-1", {"type": "llmModelNode", "data": data}, state)
    config = {
        "providerId": "p1",
        "systemPrompt": _BASE if resolved is None else resolved,
        "userPrompt": "hello",
        "memory": memory is not None,
        **config_overrides,
    }

    ctx, _ = _patch_injector(llm)
    with ctx:
        await node.process(config)
    return state.prompt_caching_diagnostics.get("llm-1")


@pytest.mark.asyncio
class TestNodeDiagnostic:

    async def test_a_split_prompt_reports_applied(self):
        diagnostic = await _diagnose(_caching_llm()[0], history=_HISTORY, promptCaching=True)

        assert diagnostic == {"requested": True, "applied": True}

    async def test_a_volatile_prompt_is_withheld(self):
        diagnostic = await _diagnose(
            _caching_llm()[0], raw="Summarize: {{message}}", resolved="Summarize: a bug", promptCaching=True
        )

        assert diagnostic == {"requested": True, "applied": False}

    async def test_an_unwrapped_model_is_withheld(self):
        diagnostic = await _diagnose(_plain_llm()[0], promptCaching=True)

        assert diagnostic == {"requested": True, "applied": False}

    async def test_a_mixed_chain_is_withheld(self):
        chain = FallbackChatModel(models=[_CapturingModel(), _caching_llm()[0]])
        diagnostic = await _diagnose(chain, promptCaching=True)

        assert diagnostic == {"requested": True, "applied": False}

    async def test_a_chain_with_no_cacheable_child_is_withheld(self):
        chain = FallbackChatModel(models=[_CapturingModel(), _CapturingModel()])
        diagnostic = await _diagnose(chain, promptCaching=True)

        assert diagnostic == {"requested": True, "applied": False}

    async def test_a_blank_prompt_is_withheld(self):
        diagnostic = await _diagnose(_caching_llm()[0], raw="", resolved="   ", promptCaching=True)

        assert diagnostic == {"requested": True, "applied": False}

    async def test_chain_of_thought_is_withheld(self):
        with patch("app.modules.workflow.engine.nodes.llm_model_node.ChainOfThoughtAgent") as agent_cls:
            agent_cls.return_value.invoke = AsyncMock(return_value={"response": "ok"})
            diagnostic = await _diagnose(_caching_llm()[0], type="Chain-of-Thought", promptCaching=True)

        assert diagnostic == {"requested": True, "applied": False}

    @pytest.mark.parametrize("raw", [None, False, "true", 1], ids=repr)
    async def test_an_unrequested_node_writes_no_annotation(self, raw):
        config = {} if raw is None else {"promptCaching": raw}
        diagnostic = await _diagnose(_caching_llm()[0], history=_HISTORY, **config)

        assert diagnostic is None

    async def test_a_failed_memory_lookup_leaves_no_applied_marker(self):
        class _RaisingMemory:
            async def get_chat_history(self, as_string: bool = False, max_messages: int = 10) -> str:
                raise RuntimeError("memory backend down")

        state = _FakeState(memory=_RaisingMemory())
        node = LLMModelNode("llm-1", {"type": "llmModelNode", "data": {"systemPrompt": _BASE}}, state)
        config = {"providerId": "p1", "systemPrompt": _BASE, "userPrompt": "hi", "memory": True, "promptCaching": True}

        ctx, _ = _patch_injector(_caching_llm()[0])
        with ctx:
            await node.process(config)

        assert state.prompt_caching_diagnostics == {}

    async def test_an_unreadable_attachment_leaves_no_applied_marker(self):
        class _StateWithAttachments(_FakeState):
            def get_value(self, key, default=None):
                if key == "attachments":
                    return [{"type": "image/png", "file_mime_type": "image/png", "file_local_path": "/nonexistent.png"}]
                return default

        state = _StateWithAttachments()
        node = LLMModelNode("llm-1", {"type": "llmModelNode", "data": {"systemPrompt": _BASE}}, state)
        config = {"providerId": "p1", "systemPrompt": _BASE, "userPrompt": "hi", "promptCaching": True}

        ctx, _ = _patch_injector(_caching_llm()[0])
        with ctx:
            await node.process(config)

        assert state.prompt_caching_diagnostics == {}

    async def test_a_raising_model_call_leaves_no_applied_marker(self):
        llm = PromptCachingChatModel(inner=_RaisingModel(), cache_style="anthropic")
        diagnostic = await _diagnose(llm, promptCaching=True)

        assert diagnostic is None

    async def test_a_withheld_verdict_survives_a_raising_model_call(self):
        diagnostic = await _diagnose(_RaisingModel(), promptCaching=True)

        assert diagnostic == {"requested": True, "applied": False}

    async def test_a_state_without_the_store_never_breaks_the_node(self):
        state = _FakeState()
        del state.prompt_caching_diagnostics  # a state built before the diagnostic existed
        node = LLMModelNode("llm-1", {"type": "llmModelNode", "data": {"systemPrompt": _BASE}}, state)
        config = {"providerId": "p1", "systemPrompt": _BASE, "userPrompt": "hi", "promptCaching": True}

        ctx, _ = _patch_injector(_caching_llm()[0])
        with ctx:
            assert await node.process(config) == "ok"
