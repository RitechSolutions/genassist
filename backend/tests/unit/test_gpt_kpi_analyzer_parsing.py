"""Unit tests for the lenient, fail-closed parsing of final-analysis replies"""

import json

import pytest

from app.services.gpt_kpi_analyzer import GptKpiAnalyzer

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
KPI_BLOCK = f"```json\n{json.dumps(METRICS, indent=4)}\n```"
analyzer = GptKpiAnalyzer()


def _reply(
    title="**A) Title:** Billing Questions",
    summary="**B) Summary:**",
    kpi="**C) KPI Metrics, Tone, and Sentiment Analysis (JSON Format):**",
    body="- Operator was helpful",
    block=KPI_BLOCK,
):
    return f"{title}\n\n{summary}\n{body}\n\n{kpi}\n{block}"


@pytest.mark.parametrize(
    "reply",
    [
        _reply(),
        _reply(title="**A) Title**: Billing Questions", summary="**B) Summary**:", kpi="**C) KPI Metrics**:"),
        _reply(title="A) Title: Billing Questions", summary="B) Summary:", kpi="C) KPI Metrics:"),
        _reply(title="### A) Title: Billing Questions", summary="### B) Summary:", kpi="### C) KPI Metrics"),
        _reply(title="**A) Title:** **Billing Questions**"),
    ],
    ids=["canonical", "colon-after-bold", "bare", "headings", "bold-value"],
)
def test_markdown_variants_parse_without_a_retry(reply):
    parsed = analyzer._extract_summary_and_title(reply)
    assert parsed == {"title": "Billing Questions", "summary": "- Operator was helpful"}
    assert analyzer._extract_metrics(reply) == METRICS


NOVA = {"A) Title": "Billing Questions", "B) Summary": {"Operator performance": ["helpful"]}}


@pytest.mark.parametrize(
    "reply",
    [
        json.dumps({**NOVA, "C) KPI Metrics, Tone, and Sentiment Analysis": METRICS}),
        f"Here is the analysis:\n```json\n{json.dumps({**NOVA, 'C) KPI Metrics': METRICS}, indent=2)}\n```\nThanks",
        json.dumps({**NOVA, **METRICS}),
    ],
    ids=["nested", "prose-around-fence", "flat-metrics"],
)
def test_nova_json_replies_parse(reply):
    assert analyzer._extract_summary_and_title(reply) == {
        "title": "Billing Questions",
        "summary": "Operator performance:\n- helpful",
    }
    assert {key: analyzer._extract_metrics(reply)[key] for key in METRICS} == METRICS


def test_a_json_reply_is_never_read_as_markdown():
    reply = json.dumps({"A) Title": {"topic": "Billing"}, "B) Summary": "fine", "C) KPI Metrics": {"score": 5}})
    assert analyzer._extract_summary_and_title(reply)["title"] == ""
    assert analyzer._extract_metrics(reply) == {}


def test_a_reply_without_markers_fails_closed():
    reply = 'Billing Questions. The operator was helpful. {"Tone": "Polite"}'
    assert analyzer._extract_summary_and_title(reply) == {"title": "", "summary": ""}
    assert analyzer._extract_metrics(reply) == {}


def test_summary_text_is_never_taken_for_a_section():
    body = 'Customer said {"Tone": "Hostile"} as a joke; see C) KPI Metrics below'
    assert analyzer._extract_summary_and_title(_reply(body=body))["summary"] == body
    assert analyzer._extract_metrics(_reply(body=body)) == METRICS
    assert analyzer._extract_metrics(_reply(body=body, block="No metrics.")) == {}


@pytest.mark.parametrize("block", [KPI_BLOCK, json.dumps(METRICS)], ids=["fenced", "bare"])
def test_trailing_prose_with_braces_after_the_metrics_is_ignored(block):
    assert analyzer._extract_metrics(_reply(block=f"{block}\n\nNote: {{see above}}")) == METRICS


def test_a_block_without_kpi_keys_is_rejected():
    assert analyzer._extract_metrics(_reply(block='```json\n{"score": 5}\n```')) == {}
