"""Marks a stable system prefix so the provider can cache it.

The marker is provider-specific: Anthropic sets `cache_control: {"type": "ephemeral"}`
on the system block itself, Bedrock Converse adds a `{"cachePoint": {"type": "default"}}`
block after it.

A tool-bound wrapper additionally marks the end of the conversation on every call, so
each turn of a tool loop re-reads the previous turn's prefix. Anthropic takes this as
a `cache_control` request kwarg — the provider package places it on the last eligible
block itself — while Bedrock takes a cachePoint block appended to the last human or
tool message."""

from __future__ import annotations

from typing import Any, AsyncIterator, Iterator, List, Literal, Optional, Sequence

from langchain_core.callbacks import (
    AsyncCallbackManagerForLLMRun,
    CallbackManagerForLLMRun,
)
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult

from app.modules.workflow.llm.fallback_chat_model import FallbackChatModel, child_callback_config

__all__ = [
    "PROMPT_CACHE_OPT_IN_KEY",
    "PromptCachingChatModel",
    "build_cacheable_system_message",
    "model_has_prompt_caching",
]

CacheStyle = Literal["anthropic", "bedrock_converse"]

_MARKER_KEYS: dict[str, str] = {"anthropic": "cache_control", "bedrock_converse": "cachePoint"}

# Optional marker the builder stamps and the wrapper requires
PROMPT_CACHE_OPT_IN_KEY = "genassist_prompt_cache"


def build_cacheable_system_message(stable: str, volatile: Optional[str] = None) -> SystemMessage:
    """The only sanctioned constructor for a cache-eligible system message"""
    content: List[Any] = [{"type": "text", "text": stable}]
    if volatile:
        content.append({"type": "text", "text": volatile})
    return SystemMessage(content=content, additional_kwargs={PROMPT_CACHE_OPT_IN_KEY: True})


class PromptCachingChatModel(BaseChatModel):
    """Adds a provider cache marker to an opted-in system prefix, then delegates"""

    inner: Any
    cache_style: CacheStyle
    # Set by bind_tools: a tool loop re-sends a growing prefix, so the conversation
    # tail earns its own breakpoint. Stays off for single-shot callers, whose tail
    # changes every request and would pay the cache write without a read-back.
    cache_conversation: bool = False

    @property
    def _llm_type(self) -> str:
        return "prompt_caching_chat_model"

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> "PromptCachingChatModel":
        """Re-wrap the bound child so the type stays stable"""
        return PromptCachingChatModel(
            inner=self.inner.bind_tools(tools, **kwargs),
            cache_style=self.cache_style,
            cache_conversation=True,
        )

    def _mark_messages(self, messages: List[BaseMessage]) -> tuple[List[BaseMessage], bool]:
        """`messages` with the first SystemMessage marked, plus whether caching is active"""
        for idx, message in enumerate(messages):
            if not isinstance(message, SystemMessage):
                continue
            marked, active = self._mark_system(message)
            if marked is message:
                return messages, active
            new_messages = list(messages)
            new_messages[idx] = marked
            return new_messages, active
        return messages, False

    def _mark_system(self, message: SystemMessage) -> tuple[SystemMessage, bool]:
        """Mark the first content block, or return `message` untouched if ineligible"""
        if not message.additional_kwargs.get(PROMPT_CACHE_OPT_IN_KEY):
            return message, False

        content = message.content
        if not isinstance(content, list) or not content:
            return message, False

        # Scans every block, not just the first: a marker the caller placed further down
        # is left as the only breakpoint rather than silently getting a second one.
        marker_key = _MARKER_KEYS[self.cache_style]
        if any(isinstance(block, dict) and marker_key in block for block in content):
            return message, True

        first = content[0]
        if not isinstance(first, dict) or first.get("type") != "text":
            return message, False
        text = first.get("text")
        if not isinstance(text, str) or not text.strip():
            return message, False

        if self.cache_style == "anthropic":
            new_content: List[Any] = [{**first, "cache_control": {"type": "ephemeral"}}, *content[1:]]
        else:
            new_content = [first, {"cachePoint": {"type": "default"}}, *content[1:]]
        return message.model_copy(update={"content": new_content}), True

    def _mark_conversation_tail(self, messages: List[BaseMessage]) -> List[BaseMessage]:
        """Append a Bedrock cachePoint to the last human or tool message.

        Anthropic never comes through here — its tail breakpoint travels as a request
        kwarg so the provider package can pick the last eligible block itself."""
        last = messages[-1] if messages else None
        if not isinstance(last, (HumanMessage, ToolMessage)):
            return messages

        content = last.content
        if isinstance(content, str):
            if not content.strip():
                return messages
            new_content: List[Any] = [{"type": "text", "text": content}, {"cachePoint": {"type": "default"}}]
        elif isinstance(content, list) and content:
            if any(isinstance(block, dict) and "cachePoint" in block for block in content):
                return messages
            new_content = [*content, {"cachePoint": {"type": "default"}}]
        else:
            return messages

        new_messages = list(messages)
        new_messages[-1] = last.model_copy(update={"content": new_content})
        return new_messages

    def _prepare(
        self, messages: List[BaseMessage], stop: Optional[List[str]], kwargs: dict
    ) -> tuple[List[BaseMessage], dict]:
        """Marked messages plus the kwargs the delegated call should carry"""
        marked, active = self._mark_messages(messages)
        invoke_kwargs = dict(kwargs)
        if stop is not None:
            invoke_kwargs["stop"] = stop
        if active and self.cache_conversation:
            if self.cache_style == "anthropic":
                invoke_kwargs.setdefault("cache_control", {"type": "ephemeral"})
            else:
                marked = self._mark_conversation_tail(marked)
        return marked, invoke_kwargs

    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        marked, invoke_kwargs = self._prepare(messages, stop, kwargs)
        ai = await self.inner.ainvoke(marked, config=child_callback_config(run_manager), **invoke_kwargs)
        return ChatResult(generations=[ChatGeneration(message=ai)])

    async def _astream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatGenerationChunk]:
        marked, invoke_kwargs = self._prepare(messages, stop, kwargs)
        config = child_callback_config(run_manager)
        async for chunk in self.inner.astream(marked, config=config, **invoke_kwargs):
            yield ChatGenerationChunk(message=chunk)

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        marked, invoke_kwargs = self._prepare(messages, stop, kwargs)
        ai = self.inner.invoke(marked, config=child_callback_config(run_manager), **invoke_kwargs)
        return ChatResult(generations=[ChatGeneration(message=ai)])

    def _stream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        marked, invoke_kwargs = self._prepare(messages, stop, kwargs)
        config = child_callback_config(run_manager)
        for chunk in self.inner.stream(marked, config=config, **invoke_kwargs):
            yield ChatGenerationChunk(message=chunk)


def model_has_prompt_caching(model: Any) -> bool:
    if isinstance(model, PromptCachingChatModel):
        return True
    if isinstance(model, FallbackChatModel):
        return bool(model.models) and all(isinstance(child, PromptCachingChatModel) for child in model.models)
    return False
