"""Unit tests for topics and sub-topics in the analyst prompts and the normalised verdicts"""

import json
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage

from app.services.gpt_kpi_analyzer import GptKpiAnalyzer

SETTINGS = {"topics": ["Technical issue", "Technical issue > Login issues", "Other"]}
METRICS = {
    "Response Time": 8,
    "Customer Satisfaction": 9,
    "Quality of Service": 8,
    "Efficiency": 7,
    "Resolution Rate": 9,
    "Operator Knowledge": 8,
    "Tone": "Polite",
    "Sentiment": {"positive": 70, "neutral": 20, "negative": 10},
}
analyzer = GptKpiAnalyzer()


def _analyst(settings=SETTINGS):
    a = MagicMock()
    a.id = uuid4()
    a.llm_provider_id = uuid4()
    a.prompt = "you are an analyst"
    a.context_enrichments = []
    a.settings = settings
    return a


def _reply(title, subtopic):
    block = json.dumps({**METRICS, "Subtopic": subtopic}, indent=4)
    return f"**A) Title:** {title}\n\n**B) Summary:**\n- Helpful\n\n**C) KPI Metrics:**\n```json\n{block}\n```"


@contextmanager
def _llm_replying(content):
    llm = MagicMock()
    llm.ainvoke = AsyncMock(return_value=AIMessage(content=content))
    provider = MagicMock(get_model=AsyncMock(return_value=llm))
    logs = MagicMock(build_enrichment_context=AsyncMock(return_value=""))
    injector = MagicMock(get=lambda cls: provider if getattr(cls, "__name__", "") == "LLMProvider" else logs)
    recorder = MagicMock(record_analyst_call=AsyncMock())
    with (
        patch("app.dependencies.injector.injector", injector),
        patch("app.services.llm_usage_recorder.LlmUsageRecorder", return_value=recorder),
        patch.object(GptKpiAnalyzer, "_resolve_analyst_provider_model", AsyncMock(return_value=("openai", "gpt-4o"))),
    ):
        yield


def test_final_prompt_lists_sub_topics_and_asks_for_one():
    prompt = analyzer._build_system_prompt("base", _analyst())
    assert "**A) Title:** <one from: Technical issue, Other>" in prompt
    assert "Titles and their sub-topics: Technical issue (sub-topics: Login issues), Other" in prompt
    assert '"Subtopic":' in prompt


def test_final_prompt_without_sub_topics_is_unchanged():
    prompt = analyzer._build_system_prompt("base", _analyst({"topics": ["Technical issue", "Other"]}))
    assert "Subtopic" not in prompt and "sub-topics" not in prompt
    assert "analysis.\n\nAlways respond" in prompt
    assert '"Operator Knowledge": (integer 0-10),\n    "Tone"' in prompt


def test_live_topics_use_top_level_names_only():
    assert analyzer._get_topics_csv(_analyst()) == "Technical issue, Other"


@pytest.mark.parametrize("subtopic, expected", [("login issues", "Login issues"), ("Wrong plate", "")])
@pytest.mark.asyncio
async def test_final_verdict_is_normalised(subtopic, expected):
    with _llm_replying(_reply("technical issue", subtopic)):
        result = await analyzer.analyze_transcript("customer: hi", llm_analyst=_analyst())

    assert result.title == "Technical issue"
    assert result.kpi_metrics["Subtopic"] == expected


@pytest.mark.parametrize("topic, expected", [("technical issue", "Technical issue"), (None, None)])
@pytest.mark.asyncio
async def test_live_topic_is_normalised_only_when_a_string(topic, expected):
    reply = json.dumps({"topic": topic, "hostile_score": 5, "negative_reason": "Other"})
    with _llm_replying(reply):
        result = await analyzer.partial_hostility_analysis("customer: hi", llm_analyst=_analyst())

    assert result["topic"] == expected
