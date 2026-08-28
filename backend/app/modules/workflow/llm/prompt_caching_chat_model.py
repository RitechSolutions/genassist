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

import hashlib
import json
import logging
from typing import Any, AsyncIterator, Iterator, List, Literal, Optional, Sequence

from langchain_core.callbacks import (
    AsyncCallbackManagerForLLMRun,
    CallbackManagerForLLMRun,
)
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult

from app.modules.workflow.llm.fallback_chat_model import FallbackChatModel, child_callback_config

logger = logging.getLogger(__name__)

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


def _sha12(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:12]


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
        """Re-wrap the bound child so a tool loop keeps caching its system prefix"""
        return PromptCachingChatModel(inner=self.inner.bind_tools(tools, **kwargs), cache_style=self.cache_style)

    def _mark_messages(self, messages: List[BaseMessage]) -> List[BaseMessage]:
        """`messages` with the first SystemMessage marked, or unchanged if none is eligible"""
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

    def _prepare(
        self, messages: List[BaseMessage], stop: Optional[List[str]], kwargs: dict
    ) -> tuple[List[BaseMessage], dict]:
        """Marked messages plus the kwargs the delegated call should carry"""
        invoke_kwargs = dict(kwargs)
        if stop is not None:
            invoke_kwargs["stop"] = stop
        return self._mark_messages(messages), invoke_kwargs

    def _log_cache_call(self, marked: List[BaseMessage], ai: Any) -> None:
        """Logs for diagnosing unstable cache reads: the hashes tie a call to the
        prefix and tool set it should hit, without logging prompt content"""
        if not logger.isEnabledFor(logging.DEBUG):
            return
        try:
            system = next((m for m in marked if isinstance(m, SystemMessage)), None)
            stable = ""
            if system is not None:
                if isinstance(system.content, list) and system.content and isinstance(system.content[0], dict):
                    stable = str(system.content[0].get("text", ""))
                elif isinstance(system.content, str):
                    stable = system.content
            bound_kwargs = getattr(self.inner, "kwargs", None)
            tools = bound_kwargs.get("tools") if isinstance(bound_kwargs, dict) else None
            base = getattr(self.inner, "bound", self.inner)
            metadata = getattr(ai, "response_metadata", None) or {}
            usage = getattr(ai, "usage_metadata", None) or {}
            details = usage.get("input_token_details") or {}
            logger.debug(
                "prompt-cache call style=%s model=%s request_id=%s prefix_sha=%s tools_sha=%s "
                "cache_read=%s cache_creation=%s",
                self.cache_style,
                getattr(base, "model_id", None) or getattr(base, "model", None),
                metadata.get("id") or (metadata.get("ResponseMetadata") or {}).get("RequestId"),
                _sha12(stable) if stable else None,
                _sha12(json.dumps(tools, sort_keys=True, default=str)) if tools else None,
                details.get("cache_read"),
                details.get("cache_creation"),
            )
        except Exception:
            logger.debug("prompt-cache call breadcrumb failed", exc_info=True)

    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        marked, invoke_kwargs = self._prepare(messages, stop, kwargs)
        ai = await self.inner.ainvoke(marked, config=child_callback_config(run_manager), **invoke_kwargs)
        self._log_cache_call(marked, ai)
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
        self._log_cache_call(marked, ai)
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
