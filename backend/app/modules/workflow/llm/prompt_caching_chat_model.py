"""Marks a stable system prefix so the provider can cache it.

The marker is provider-specific: Anthropic sets `cache_control: {"type": "ephemeral"}`
on the system block itself, Bedrock Converse adds a `{"cachePoint": {"type": "default"}}`
block after it."""

from __future__ import annotations

from typing import Any, AsyncIterator, Iterator, List, Literal, Optional, Sequence

from langchain_core.callbacks import (
    AsyncCallbackManagerForLLMRun,
    CallbackManagerForLLMRun,
)
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, SystemMessage
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

    @property
    def _llm_type(self) -> str:
        return "prompt_caching_chat_model"

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> "PromptCachingChatModel":
        """Re-wrap the bound child so the type stays stable"""
        return PromptCachingChatModel(
            inner=self.inner.bind_tools(tools, **kwargs),
            cache_style=self.cache_style,
        )

    def _mark_messages(self, messages: List[BaseMessage]) -> List[BaseMessage]:
        """Return `messages` with the first SystemMessage marked, or unchanged"""
        for idx, message in enumerate(messages):
            if not isinstance(message, SystemMessage):
                continue
            marked = self._mark_system(message)
            if marked is message:
                return messages
            new_messages = list(messages)
            new_messages[idx] = marked
            return new_messages
        return messages

    def _mark_system(self, message: SystemMessage) -> SystemMessage:
        """Mark the first content block, or return `message` untouched if ineligible"""
        if not message.additional_kwargs.get(PROMPT_CACHE_OPT_IN_KEY):
            return message

        content = message.content
        if not isinstance(content, list) or not content:
            return message

        # Scans every block, not just the first: a marker the caller placed further down
        # is left as the only breakpoint rather than silently getting a second one.
        marker_key = _MARKER_KEYS[self.cache_style]
        if any(isinstance(block, dict) and marker_key in block for block in content):
            return message

        first = content[0]
        if not isinstance(first, dict) or first.get("type") != "text":
            return message
        text = first.get("text")
        if not isinstance(text, str) or not text.strip():
            return message

        if self.cache_style == "anthropic":
            new_content: List[Any] = [{**first, "cache_control": {"type": "ephemeral"}}, *content[1:]]
        else:
            new_content = [first, {"cachePoint": {"type": "default"}}, *content[1:]]
        return message.model_copy(update={"content": new_content})

    def _invoke_kwargs(self, stop: Optional[List[str]], kwargs: dict) -> dict:
        invoke_kwargs = dict(kwargs)
        if stop is not None:
            invoke_kwargs["stop"] = stop
        return invoke_kwargs

    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        ai = await self.inner.ainvoke(
            self._mark_messages(messages),
            config=child_callback_config(run_manager),
            **self._invoke_kwargs(stop, kwargs),
        )
        return ChatResult(generations=[ChatGeneration(message=ai)])

    async def _astream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatGenerationChunk]:
        marked = self._mark_messages(messages)
        config = child_callback_config(run_manager)
        async for chunk in self.inner.astream(marked, config=config, **self._invoke_kwargs(stop, kwargs)):
            yield ChatGenerationChunk(message=chunk)

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        ai = self.inner.invoke(
            self._mark_messages(messages),
            config=child_callback_config(run_manager),
            **self._invoke_kwargs(stop, kwargs),
        )
        return ChatResult(generations=[ChatGeneration(message=ai)])

    def _stream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        marked = self._mark_messages(messages)
        config = child_callback_config(run_manager)
        for chunk in self.inner.stream(marked, config=config, **self._invoke_kwargs(stop, kwargs)):
            yield ChatGenerationChunk(message=chunk)


def model_has_prompt_caching(model: Any) -> bool:
    if isinstance(model, PromptCachingChatModel):
        return True
    if isinstance(model, FallbackChatModel):
        return bool(model.models) and all(isinstance(child, PromptCachingChatModel) for child in model.models)
    return False
