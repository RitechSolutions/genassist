"""Unit tests for the LLM provider fallback chain core.

Covers exception classification (is_retryable) and the FallbackChatModel wrapper:
ordering, per-provider retry, fail-fast on permanent errors, streaming failover,
bind_tools type-stability, and responding-provider attribution.
"""

import httpx
import openai
import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult

from app.modules.workflow.llm.fallback_chat_model import (
    FALLBACK_PROVIDER_ID_KEY,
    FallbackChatModel,
)
from app.modules.workflow.llm.fallback_exceptions import is_retryable


def _openai_status_error(code: int) -> openai.APIStatusError:
    req = httpx.Request("POST", "http://x")
    return openai.APIStatusError("boom", response=httpx.Response(code, request=req), body=None)


class _FakeModel(BaseChatModel):
    """Configurable fake chat model for exercising the wrapper."""

    behavior: str = "ok"  # "ok" | "rate" | "badreq"
    text: str = "ok-response"
    call_count: int = 0
    tools_bound: list = []

    @property
    def _llm_type(self) -> str:
        return "fake"

    def _maybe_raise(self):
        if self.behavior == "rate":
            req = httpx.Request("POST", "http://x")
            raise openai.RateLimitError(
                "rate", response=httpx.Response(429, request=req), body=None
            )
        if self.behavior == "badreq":
            req = httpx.Request("POST", "http://x")
            raise openai.BadRequestError(
                "bad", response=httpx.Response(400, request=req), body=None
            )

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        self.call_count += 1
        self._maybe_raise()
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=self.text))])

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        self.call_count += 1
        self._maybe_raise()
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=self.text))])

    async def _astream(self, messages, stop=None, run_manager=None, **kwargs):
        self.call_count += 1
        self._maybe_raise()
        yield ChatGenerationChunk(message=AIMessageChunk(content=self.text))

    def bind_tools(self, tools, **kwargs):
        return _FakeModel(behavior=self.behavior, text=self.text, tools_bound=list(tools))


class TestIsRetryable:
    @pytest.mark.parametrize(
        "code,expected",
        [
            (400, False), (401, False), (403, False), (404, False), (422, False),
            (408, True), (409, True), (429, True), (500, True), (502, True),
            (503, True), (504, True),
        ],
    )
    def test_status_code_classification(self, code, expected):
        assert is_retryable(_openai_status_error(code)) is expected

    def test_timeout_is_retryable(self):
        assert is_retryable(TimeoutError("slow")) is True
        assert is_retryable(httpx.ConnectError("no route")) is True

    def test_unknown_exception_fails_fast(self):
        assert is_retryable(ValueError("nonsense")) is False

    def test_bedrock_botocore_classification(self):
        """AWS Bedrock errors come from botocore (dict response, no .status_code)."""
        import botocore.exceptions as be

        def client_err(code: str, http: int) -> be.ClientError:
            return be.ClientError(
                {"Error": {"Code": code, "Message": "x"},
                 "ResponseMetadata": {"HTTPStatusCode": http}},
                "InvokeModel",
            )

        # Transient Bedrock errors → retryable
        assert is_retryable(client_err("ThrottlingException", 429)) is True
        assert is_retryable(client_err("ServiceUnavailableException", 503)) is True
        assert is_retryable(client_err("ModelTimeoutException", 408)) is True
        assert is_retryable(be.ReadTimeoutError(endpoint_url="https://b")) is True
        assert is_retryable(be.ConnectTimeoutError(endpoint_url="https://b")) is True
        assert is_retryable(be.EndpointConnectionError(endpoint_url="https://b")) is True

        # Permanent Bedrock errors → fail fast
        assert is_retryable(client_err("AccessDeniedException", 403)) is False
        assert is_retryable(client_err("ValidationException", 400)) is False

    def test_gemini_google_classification(self):
        """Gemini/Vertex errors come from google.api_core (HTTP status on `.code`)."""
        import google.api_core.exceptions as g

        # Transient → retryable
        assert is_retryable(g.ResourceExhausted("rate")) is True       # 429
        assert is_retryable(g.ServiceUnavailable("down")) is True      # 503
        assert is_retryable(g.DeadlineExceeded("slow")) is True        # 504
        assert is_retryable(g.InternalServerError("boom")) is True     # 500

        # Permanent → fail fast
        assert is_retryable(g.BadRequest("bad")) is False              # 400
        assert is_retryable(g.Unauthorized("no")) is False             # 401
        assert is_retryable(g.Forbidden("no")) is False                # 403


@pytest.mark.asyncio
class TestFallbackChatModel:
    async def test_falls_over_on_transient_error_and_stamps_provider(self):
        fm = FallbackChatModel(
            models=[_FakeModel(behavior="rate"), _FakeModel(behavior="ok", text="from-fallback")],
            provider_ids=["p1", "p2"],
        )
        resp = await fm.ainvoke([HumanMessage(content="hi")])
        assert resp.content == "from-fallback"
        assert resp.response_metadata.get(FALLBACK_PROVIDER_ID_KEY) == "p2"

    async def test_permanent_error_fails_fast_without_fallback(self):
        fallback = _FakeModel(behavior="ok")
        fm = FallbackChatModel(
            models=[_FakeModel(behavior="badreq"), fallback],
            provider_ids=["p1", "p2"],
        )
        with pytest.raises(openai.BadRequestError):
            await fm.ainvoke([HumanMessage(content="hi")])
        assert fallback.call_count == 0  # never reached

    async def test_retry_count_attempts_before_fallback(self):
        primary = _FakeModel(behavior="rate")
        fm = FallbackChatModel(
            models=[primary, _FakeModel(behavior="ok", text="fb")],
            provider_ids=["p1", "p2"],
            retry_count=2,
            retry_backoff_seconds=0,
        )
        resp = await fm.ainvoke([HumanMessage(content="hi")])
        assert resp.content == "fb"
        assert primary.call_count == 3  # 1 initial + 2 retries

    async def test_all_providers_fail_raises_last_exception(self):
        fm = FallbackChatModel(
            models=[_FakeModel(behavior="rate"), _FakeModel(behavior="rate")],
            provider_ids=["p1", "p2"],
        )
        with pytest.raises(openai.RateLimitError):
            await fm.ainvoke([HumanMessage(content="hi")])

    async def test_streaming_falls_over_before_first_chunk(self):
        fm = FallbackChatModel(
            models=[_FakeModel(behavior="rate"), _FakeModel(behavior="ok", text="streamed")],
            provider_ids=["p1", "p2"],
        )
        out = "".join([chunk.content async for chunk in fm.astream([HumanMessage(content="hi")])])
        assert out == "streamed"

    async def test_slow_provider_times_out_and_falls_over(self):
        import asyncio as _asyncio

        class _SlowModel(BaseChatModel):
            @property
            def _llm_type(self):
                return "slow"

            def _generate(self, messages, stop=None, run_manager=None, **kwargs):
                raise NotImplementedError

            async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
                await _asyncio.sleep(5)  # far longer than the timeout
                return ChatResult(generations=[ChatGeneration(message=AIMessage(content="too late"))])

            def bind_tools(self, tools, **kwargs):
                return self

        # Per-provider timeouts: slow provider gets 0.05s (times out), fast gets 0 (no limit).
        fm = FallbackChatModel(
            models=[_SlowModel(), _FakeModel(behavior="ok", text="fast-fallback")],
            provider_ids=["slow", "fast"],
            request_timeouts=[0.05, 0],
        )
        resp = await fm.ainvoke([HumanMessage(content="hi")])
        assert resp.content == "fast-fallback"
        assert resp.response_metadata.get(FALLBACK_PROVIDER_ID_KEY) == "fast"

    async def test_per_provider_timeout_only_applies_to_its_own_provider(self):
        import asyncio as _asyncio

        class _SlowModel(BaseChatModel):
            @property
            def _llm_type(self):
                return "slow"

            def _generate(self, messages, stop=None, run_manager=None, **kwargs):
                raise NotImplementedError

            async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
                await _asyncio.sleep(0.2)
                return ChatResult(generations=[ChatGeneration(message=AIMessage(content="slow-but-ok"))])

            def bind_tools(self, tools, **kwargs):
                return self

        # First provider has a generous timeout (0.5s) so its 0.2s reply succeeds;
        # it should answer and the fast fallback is never reached.
        fm = FallbackChatModel(
            models=[_SlowModel(), _FakeModel(behavior="ok", text="fallback")],
            provider_ids=["slow", "fast"],
            request_timeouts=[0.5, 0],
        )
        resp = await fm.ainvoke([HumanMessage(content="hi")])
        assert resp.content == "slow-but-ok"
        assert resp.response_metadata.get(FALLBACK_PROVIDER_ID_KEY) == "slow"

    async def test_bind_tools_preserves_wrapper_and_settings(self):
        fm = FallbackChatModel(
            models=[_FakeModel(behavior="ok"), _FakeModel(behavior="ok")],
            provider_ids=["p1", "p2"],
            retry_count=3,
            retry_backoff_seconds=1.5,
            request_timeouts=[12, 30],
        )
        bound = fm.bind_tools([{"type": "function"}])
        assert isinstance(bound, FallbackChatModel)
        assert bound.retry_count == 3 and bound.retry_backoff_seconds == 1.5
        assert bound.request_timeouts == [12, 30]
        assert all(getattr(m, "tools_bound", None) for m in bound.models)
