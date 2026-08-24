"""
FallbackChatModel — an ordered list of chat models tried in sequence.

Why a custom BaseChatModel subclass instead of LangChain's `.with_fallbacks()`?
`RunnableWithFallbacks` is a plain Runnable and does NOT expose `bind_tools()`.
LangGraph's `create_agent(model=...)` (used by ReActAgentLC) calls
`model.bind_tools(...)`, so a `RunnableWithFallbacks` breaks that path. By
subclassing `BaseChatModel` and re-wrapping children on `bind_tools`, this single
object works for BOTH the direct `.ainvoke()` path and the LangGraph agent path.

On a *transient* failure (see `fallback_exceptions.is_retryable`) the next model
is tried; on a permanent failure (auth/bad-request) the error is re-raised
immediately. The model that actually answered is recorded in
`response_metadata["__fallback_provider_id__"]` so token usage can be attributed
correctly downstream.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, AsyncIterator, Iterator, List, Optional, Sequence

from langchain_core.callbacks import (
    AsyncCallbackManagerForLLMRun,
    CallbackManagerForLLMRun,
)
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult

from app.modules.workflow.llm.fallback_exceptions import (
    FALLBACK_PROVIDER_ID_KEY,
    is_retryable,
)

logger = logging.getLogger(__name__)

# Re-exported for callers that import it from here (defined in fallback_exceptions
# so lightweight modules like llm_usage_utils can use it without importing langchain).
__all__ = ["FallbackChatModel", "FALLBACK_PROVIDER_ID_KEY", "child_callback_config"]


def child_callback_config(run_manager: Optional[Any]) -> Optional[dict]:
    """Config that nests a delegated call under the caller's run"""
    if run_manager is None:
        return None
    from langchain_core.callbacks import AsyncCallbackManager, CallbackManager

    manager_cls = AsyncCallbackManager if isinstance(run_manager, AsyncCallbackManagerForLLMRun) else CallbackManager
    manager = manager_cls(handlers=[], parent_run_id=run_manager.run_id)
    manager.set_handlers(run_manager.inheritable_handlers)
    manager.add_tags(list(run_manager.inheritable_tags or []))
    manager.add_metadata(dict(run_manager.inheritable_metadata or {}))
    return {"callbacks": manager}


class FallbackChatModel(BaseChatModel):
    """Tries an ordered list of chat models, falling back on transient errors.

    Each provider is attempted up to ``retry_count + 1`` times (exponential backoff
    between attempts) before moving on to the next provider in the list. Retry is
    implemented here rather than via ``Runnable.with_retry`` because the latter
    returns a ``RunnableRetry`` that lacks ``bind_tools`` and would break the
    LangGraph ``create_agent`` path.

    Args:
        models: Ordered list of chat models / runnables. Index 0 is the primary.
            Entries may be `BaseChatModel` instances or `RunnableBinding` objects
            (the result of `bind_tools`); only `.ainvoke` / `.astream` are required.
        provider_ids: Provider-id strings parallel to `models`, used to stamp the
            responding provider onto `response_metadata`. May be shorter/empty.
        retry_count: Extra attempts per provider beyond the first (0 = no retry).
        retry_backoff_seconds: Initial backoff; doubles each retry (0 = no wait).
        request_timeouts: Per-provider max wall-clock seconds to wait for a single
            attempt's reply before cancelling it and treating it as a retryable
            failure. Parallel to `models` (0 or missing = no limit for that
            provider). For streaming this bounds time-to-first-token.
    """

    models: List[Any]
    provider_ids: List[str] = []
    retry_count: int = 0
    retry_backoff_seconds: float = 0.0
    request_timeouts: List[float] = []

    @property
    def _llm_type(self) -> str:
        return "fallback_chat_model"

    def _provider_id_at(self, idx: int) -> Optional[str]:
        if 0 <= idx < len(self.provider_ids):
            return self.provider_ids[idx]
        return None

    def _timeout_at(self, idx: int) -> float:
        """Response timeout for the provider at `idx` (0 = no limit)."""
        if 0 <= idx < len(self.request_timeouts):
            return self.request_timeouts[idx] or 0.0
        return 0.0

    def _backoff_for(self, attempt: int) -> float:
        """Backoff before retry `attempt` (1-based) of the same provider."""
        if self.retry_backoff_seconds <= 0:
            return 0.0
        return self.retry_backoff_seconds * (2 ** (attempt - 1))

    def _stamp(self, message: BaseMessage, idx: int) -> BaseMessage:
        provider_id = self._provider_id_at(idx)
        if provider_id is not None and isinstance(message, (AIMessage,)):
            if message.response_metadata is None:
                message.response_metadata = {}
            message.response_metadata.setdefault(FALLBACK_PROVIDER_ID_KEY, provider_id)
        return message

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> "FallbackChatModel":
        """Re-wrap every child with its tool binding, preserving the fallback order.

        Returning a FallbackChatModel (rather than a RunnableBinding) keeps the type
        stable so LangGraph's create_agent — which calls bind_tools on the model —
        continues to see a BaseChatModel that still fails over across providers.
        """
        return FallbackChatModel(
            models=[m.bind_tools(tools, **kwargs) for m in self.models],
            provider_ids=list(self.provider_ids),
            retry_count=self.retry_count,
            retry_backoff_seconds=self.retry_backoff_seconds,
            request_timeouts=list(self.request_timeouts),
        )

    async def _ainvoke_one(
        self, model: Any, messages: List[BaseMessage], config: Optional[dict], invoke_kwargs: dict, timeout: float
    ) -> AIMessage:
        """Invoke a single child, enforcing this provider's timeout if set.

        A timeout raises asyncio.TimeoutError, which is_retryable() treats as a
        transient failure, so the caller will retry / fall over to the next provider.
        """
        if timeout and timeout > 0:
            return await asyncio.wait_for(
                model.ainvoke(messages, config=config, **invoke_kwargs),
                timeout=timeout,
            )
        return await model.ainvoke(messages, config=config, **invoke_kwargs)

    # ----- async (primary path) --------------------------------------------

    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        invoke_kwargs = dict(kwargs)
        if stop is not None:
            invoke_kwargs["stop"] = stop
        config = child_callback_config(run_manager)

        last_exc: Optional[BaseException] = None
        for idx, model in enumerate(self.models):
            timeout = self._timeout_at(idx)
            for attempt in range(self.retry_count + 1):
                try:
                    ai = await self._ainvoke_one(model, messages, config, invoke_kwargs, timeout)
                except BaseException as exc:  # noqa: BLE001 - re-raised below when not retryable
                    if not is_retryable(exc):
                        raise
                    last_exc = exc
                    if attempt < self.retry_count:
                        delay = self._backoff_for(attempt + 1)
                        logger.warning(
                            "FallbackChatModel: provider index %s (%s) failed (%s); "
                            "retry %s/%s after %.2fs",
                            idx, self._provider_id_at(idx), type(exc).__name__,
                            attempt + 1, self.retry_count, delay,
                        )
                        if delay:
                            await asyncio.sleep(delay)
                        continue
                    logger.warning(
                        "FallbackChatModel: provider index %s (%s) exhausted retries (%s); "
                        "trying next provider",
                        idx, self._provider_id_at(idx), type(exc).__name__,
                    )
                    break  # move to next provider
                self._stamp(ai, idx)
                return ChatResult(generations=[ChatGeneration(message=ai)])

        assert last_exc is not None  # loop ran at least once and only continues on a caught exc
        raise last_exc

    async def _astream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatGenerationChunk]:
        invoke_kwargs = dict(kwargs)
        if stop is not None:
            invoke_kwargs["stop"] = stop
        config = child_callback_config(run_manager)

        last_exc: Optional[BaseException] = None
        for idx, model in enumerate(self.models):
            _t = self._timeout_at(idx)
            timeout = _t if _t > 0 else None
            for attempt in range(self.retry_count + 1):
                emitted = False
                try:
                    aiter = model.astream(messages, config=config, **invoke_kwargs).__aiter__()
                    while True:
                        # Bound time-to-first-token by the request timeout. Subsequent
                        # chunks are not individually timed (mid-stream stalls are rare
                        # and can't be cleanly failed over once tokens are emitted).
                        if not emitted and timeout is not None:
                            chunk = await asyncio.wait_for(aiter.__anext__(), timeout=timeout)
                        else:
                            chunk = await aiter.__anext__()
                        if not emitted:
                            self._stamp(chunk, idx)
                            emitted = True
                        yield ChatGenerationChunk(message=chunk)
                except StopAsyncIteration:
                    return  # stream finished normally
                except BaseException as exc:  # noqa: BLE001
                    # Mid-stream failover is not supported: once tokens have been emitted
                    # to the consumer we cannot cleanly replay them on another provider.
                    if emitted or not is_retryable(exc):
                        raise
                    last_exc = exc
                    if attempt < self.retry_count:
                        delay = self._backoff_for(attempt + 1)
                        if delay:
                            await asyncio.sleep(delay)
                        continue
                    logger.warning(
                        "FallbackChatModel(stream): provider index %s (%s) failed before first "
                        "chunk (%s); trying next provider",
                        idx, self._provider_id_at(idx), type(exc).__name__,
                    )
                    break  # move to next provider

        assert last_exc is not None
        raise last_exc

    # ----- sync (not used in this async codebase; defined to satisfy the ABC) ----

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        invoke_kwargs = dict(kwargs)
        if stop is not None:
            invoke_kwargs["stop"] = stop
        config = child_callback_config(run_manager)

        last_exc: Optional[BaseException] = None
        for idx, model in enumerate(self.models):
            for attempt in range(self.retry_count + 1):
                try:
                    ai = model.invoke(messages, config=config, **invoke_kwargs)
                except BaseException as exc:  # noqa: BLE001
                    if not is_retryable(exc):
                        raise
                    last_exc = exc
                    if attempt < self.retry_count:
                        delay = self._backoff_for(attempt + 1)
                        if delay:
                            time.sleep(delay)
                        continue
                    break  # move to next provider
                self._stamp(ai, idx)
                return ChatResult(generations=[ChatGeneration(message=ai)])

        assert last_exc is not None
        raise last_exc

    def _stream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        invoke_kwargs = dict(kwargs)
        if stop is not None:
            invoke_kwargs["stop"] = stop
        config = child_callback_config(run_manager)

        last_exc: Optional[BaseException] = None
        for idx, model in enumerate(self.models):
            for attempt in range(self.retry_count + 1):
                emitted = False
                try:
                    for chunk in model.stream(messages, config=config, **invoke_kwargs):
                        if not emitted:
                            self._stamp(chunk, idx)
                            emitted = True
                        yield ChatGenerationChunk(message=chunk)
                    return
                except BaseException as exc:  # noqa: BLE001
                    if emitted or not is_retryable(exc):
                        raise
                    last_exc = exc
                    if attempt < self.retry_count:
                        delay = self._backoff_for(attempt + 1)
                        if delay:
                            time.sleep(delay)
                        continue
                    break  # move to next provider

        assert last_exc is not None
        raise last_exc