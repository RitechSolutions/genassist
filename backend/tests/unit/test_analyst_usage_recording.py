"""Unit tests for analyst LLM-usage recording (per-attempt + hostility + agent_id)"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage

from app.core.exceptions.exception_classes import AppException
from app.services.gpt_kpi_analyzer import GptKpiAnalyzer


def _llm_returning(content: str, usage: dict | None = None):
    msg = AIMessage(content=content, usage_metadata=usage) if usage else AIMessage(content=content)
    llm = MagicMock()
    llm.ainvoke = AsyncMock(return_value=msg)
    provider = MagicMock()
    provider.get_model = AsyncMock(return_value=llm)
    return provider


def _analyst(llm_provider=None):
    a = MagicMock()
    a.id = uuid4()
    a.llm_provider_id = uuid4()
    a.llm_provider = llm_provider
    a.prompt = "you are an analyst"
    a.context_enrichments = []
    return a


@pytest.fixture
def recorder_calls():
    rec = MagicMock()
    rec.record_analyst_call = AsyncMock()
    with patch("app.services.llm_usage_recorder.LlmUsageRecorder", return_value=rec):
        yield rec.record_analyst_call


def _patch_injector(provider):
    logs = MagicMock()
    logs.build_enrichment_context = AsyncMock(return_value="")

    def _get(cls):
        name = getattr(cls, "__name__", "")
        if name == "LLMProvider":
            return provider
        return logs

    inj = MagicMock()
    inj.get = _get
    return patch("app.dependencies.injector.injector", inj)


class TestHostilityRecording:
    @pytest.mark.asyncio
    async def test_records_once_with_agent_id_and_purpose(self, recorder_calls):
        provider = _llm_returning(
            '{"topic": "Other", "hostile_score": 5, "negative_reason": "Other"}',
            {"input_tokens": 40, "output_tokens": 6, "total_tokens": 46},
        )
        analyst = _analyst()
        aid, cid = uuid4(), uuid4()
        svc = GptKpiAnalyzer()

        with _patch_injector(provider), patch.object(
            GptKpiAnalyzer, "_resolve_analyst_provider_model", AsyncMock(return_value=("openai", "gpt-4o"))
        ), patch.object(GptKpiAnalyzer, "_get_topics_csv", return_value="Billing,Other"):
            result = await svc.partial_hostility_analysis("[]", llm_analyst=analyst, conversation_id=cid, agent_id=aid)

        assert result["hostile_score"] == 5
        recorder_calls.assert_awaited_once()
        kwargs = recorder_calls.await_args.kwargs
        assert kwargs["agent_id"] == aid
        assert kwargs["conversation_id"] == cid
        assert kwargs["purpose"] == "hostility_analysis"
        assert kwargs["call_index"] == 0
        assert kwargs["usage"]["input_tokens"] == 40 and kwargs["usage"]["output_tokens"] == 6

    @pytest.mark.asyncio
    async def test_bad_json_still_records_and_returns_safe_default(self, recorder_calls):
        provider = _llm_returning("not json", {"input_tokens": 10, "output_tokens": 2, "total_tokens": 12})
        analyst = _analyst()
        svc = GptKpiAnalyzer()

        with _patch_injector(provider), patch.object(
            GptKpiAnalyzer, "_resolve_analyst_provider_model", AsyncMock(return_value=("openai", "gpt-4o"))
        ), patch.object(GptKpiAnalyzer, "_get_topics_csv", return_value="Other"):
            result = await svc.partial_hostility_analysis("[]", llm_analyst=analyst)

        assert result == {"topic": "Other", "hostile_score": 0, "negative_reason": "Other"}
        recorder_calls.assert_awaited_once()
        assert recorder_calls.await_args.kwargs["usage"]["input_tokens"] == 10


class TestAnalyzeTranscriptRecording:
    @pytest.mark.asyncio
    async def test_passes_agent_id_per_attempt(self, recorder_calls):
        provider = _llm_returning(
            'A) Title: T\nB) Summary: S\n{"metric": 5}',
            {"input_tokens": 100, "output_tokens": 20, "total_tokens": 120},
        )
        analyst = _analyst()
        aid, cid = uuid4(), uuid4()
        svc = GptKpiAnalyzer()

        with _patch_injector(provider), patch.object(
            GptKpiAnalyzer, "_resolve_analyst_provider_model", AsyncMock(return_value=("openai", "gpt-4o"))
        ), patch.object(GptKpiAnalyzer, "_extract_summary_and_title", return_value={"summary": "S", "title": "T"}), patch.object(
            GptKpiAnalyzer, "_extract_metrics", return_value={"m": 5}
        ):
            await svc.analyze_transcript("some transcript", llm_analyst=analyst, conversation_id=cid, agent_id=aid)

        recorder_calls.assert_awaited()
        kwargs = recorder_calls.await_args.kwargs
        assert kwargs["agent_id"] == aid
        assert kwargs["purpose"] == "conversation_analysis"
        assert kwargs["call_index"] == 0

    @pytest.mark.asyncio
    async def test_every_parse_retry_is_recorded_as_its_own_call(self, recorder_calls):
        provider = _llm_returning("unparseable", {"input_tokens": 30, "output_tokens": 5, "total_tokens": 35})
        analyst = _analyst()
        svc = GptKpiAnalyzer()

        with _patch_injector(provider), patch.object(
            GptKpiAnalyzer, "_resolve_analyst_provider_model", AsyncMock(return_value=("openai", "gpt-4o"))
        ), patch.object(GptKpiAnalyzer, "_extract_summary_and_title", return_value={}), patch.object(
            GptKpiAnalyzer, "_extract_metrics", return_value={}
        ):
            with pytest.raises(AppException):
                await svc.analyze_transcript("some transcript", llm_analyst=analyst, max_attempts=3)

        assert provider.get_model.return_value.ainvoke.await_count == 3
        assert [c.kwargs["call_index"] for c in recorder_calls.await_args_list] == [0, 1, 2]

    @pytest.mark.asyncio
    async def test_recorder_failure_does_not_consume_an_llm_retry(self, recorder_calls):
        recorder_calls.side_effect = RuntimeError("ledger unavailable")
        provider = _llm_returning(
            'A) Title: T\nB) Summary: S\n{"metric": 5}',
            {"input_tokens": 100, "output_tokens": 20, "total_tokens": 120},
        )
        analyst = _analyst()
        svc = GptKpiAnalyzer()

        with _patch_injector(provider), patch.object(
            GptKpiAnalyzer, "_resolve_analyst_provider_model", AsyncMock(return_value=("openai", "gpt-4o"))
        ), patch.object(
            GptKpiAnalyzer, "_extract_summary_and_title", return_value={"summary": "S", "title": "T"}
        ), patch.object(GptKpiAnalyzer, "_extract_metrics", return_value={"m": 5}):
            result = await svc.analyze_transcript("some transcript", llm_analyst=analyst)

        assert result.title == "T"
        assert provider.get_model.return_value.ainvoke.await_count == 1

    @pytest.mark.asyncio
    async def test_missing_provider_metadata_is_recorded_as_a_call(self, recorder_calls):
        provider = _llm_returning('A) Title: T\nB) Summary: S\n{"metric": 5}')
        analyst = _analyst()
        svc = GptKpiAnalyzer()

        with _patch_injector(provider), patch.object(
            GptKpiAnalyzer, "_resolve_analyst_provider_model", AsyncMock(return_value=("openai", "gpt-4o"))
        ), patch.object(
            GptKpiAnalyzer, "_extract_summary_and_title", return_value={"summary": "S", "title": "T"}
        ), patch.object(GptKpiAnalyzer, "_extract_metrics", return_value={"m": 5}):
            await svc.analyze_transcript("some transcript", llm_analyst=analyst)

        recorder_calls.assert_awaited_once()
        assert recorder_calls.await_args.kwargs["usage"] is None


class TestAnalystAttribution:
    @pytest.mark.asyncio
    async def test_prefers_the_loaded_provider_relation(self):
        analyst = _analyst(llm_provider=MagicMock(llm_model_provider="OpenAI", llm_model="gpt-4o"))
        assert await GptKpiAnalyzer()._resolve_analyst_provider_model(analyst) == ("openai", "gpt-4o")

    @pytest.mark.asyncio
    async def test_falls_back_to_a_lookup_when_the_relation_is_absent(self):
        analyst = _analyst()
        with patch(
            "app.modules.workflow.engine.llm_usage_tracking.resolve_provider_model",
            AsyncMock(return_value=("anthropic", "claude-3-opus")),
        ) as lookup:
            assert await GptKpiAnalyzer()._resolve_analyst_provider_model(analyst) == ("anthropic", "claude-3-opus")
        lookup.assert_awaited_once_with(analyst.llm_provider_id)

    @pytest.mark.asyncio
    async def test_lookup_failure_leaves_blank_keys(self):
        analyst = _analyst()
        with patch(
            "app.services.llm_providers.LlmProviderService.get_by_id",
            AsyncMock(side_effect=RuntimeError("provider gone")),
        ):
            assert await GptKpiAnalyzer()._resolve_analyst_provider_model(analyst) == ("", "")
