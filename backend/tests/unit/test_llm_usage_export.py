"""Unit tests for the LLM usage exporters: provenance, labels and nullables in all three formats"""

from datetime import date

import pytest

from app.schemas.llm_usage import (
    EXPORT_DIMENSIONS,
    LlmUsageBreakdownItem,
    LlmUsageBreakdownResponse,
    LlmUsageSummaryResponse,
)
from app.services.llm_usage_export import export_llm_usage


def _summary(**overrides) -> LlmUsageSummaryResponse:
    values = {
        "from_date": date(2026, 7, 1),
        "to_date": date(2026, 7, 7),
        "total_cost_usd": 1.5,
        "cost_is_partial": True,
        "cost_per_conversation_usd": 0.25,
        "agent_studio_test_cost_usd": 0.5,
        "total_input_tokens": 600,
        "total_output_tokens": 400,
        "total_tokens": 1000,
        "total_calls": 10,
        "configured_calls": 6,
        "fallback_calls": 2,
        "legacy_estimate_calls": 1,
        "unpriced_calls": 1,
        "priced_token_coverage_pct": 90.0,
    }
    values.update(overrides)
    return LlmUsageSummaryResponse(**values)


def _breakdown(dimension="source") -> LlmUsageBreakdownResponse:
    return LlmUsageBreakdownResponse(
        dimension=dimension,
        items=[
            LlmUsageBreakdownItem(
                key="workflow",
                label="Workflow",
                cost_usd=1.0,
                cost_is_partial=False,
                total_tokens=800,
                calls=8,
                unpriced_calls=0,
            )
        ],
        total=1,
    )


def _csv_text(summary=None, breakdown=None) -> str:
    content, media_type = export_llm_usage(
        "csv", summary or _summary(), breakdown or _breakdown(), date(2026, 7, 1), date(2026, 7, 7)
    )
    assert media_type
    return content.decode("utf-8-sig")


def test_node_stays_out_of_export_dimensions():
    assert "node" not in EXPORT_DIMENSIONS


def test_csv_labels_source_dimension_as_usage_type():
    assert "Usage type" in _csv_text()


@pytest.mark.parametrize(
    "dimension,header", [("provider", "Provider"), ("model", "Model"), ("agent", "Agent"), ("source", "Usage type")]
)
def test_csv_header_per_dimension(dimension, header):
    assert header in _csv_text(breakdown=_breakdown(dimension))


def test_csv_includes_rate_provenance_counts():
    text = _csv_text()
    assert "Calls priced at configured rates,6" in text
    assert "Calls priced at bundled fallback rates,2" in text
    assert "Calls carrying legacy estimated cost,1" in text
    assert "Unpriced calls,1" in text


def test_csv_reports_the_cache_token_buckets():
    text = _csv_text(summary=_summary(total_cache_read_tokens=3697, total_cache_creation_tokens=120))
    assert "Cache read tokens,3697" in text
    assert "Cache write tokens,120" in text


def test_csv_reports_zero_cache_tokens_for_summaries_without_them():
    text = _csv_text()
    assert "Cache read tokens,0" in text
    assert "Cache write tokens,0" in text


def test_csv_labels_agent_studio_test_cost():
    assert "Agent Studio test cost (USD),0.5000" in _csv_text()


def test_csv_states_the_calculated_cost_limitation():
    assert "may differ from provider invoices" in _csv_text()


def test_csv_renders_null_cost_per_conversation_as_na():
    text = _csv_text(summary=_summary(cost_per_conversation_usd=None))
    assert "Cost per conversation (USD),N/A" in text


def test_csv_keeps_real_zero_cost_per_conversation():
    text = _csv_text(summary=_summary(cost_per_conversation_usd=0.0))
    assert "Cost per conversation (USD),0.0000" in text


def test_xlsx_and_pdf_render_with_the_same_report():
    xlsx, xlsx_type = export_llm_usage("xlsx", _summary(), _breakdown(), date(2026, 7, 1), date(2026, 7, 7))
    pdf, pdf_type = export_llm_usage("pdf", _summary(), _breakdown(), date(2026, 7, 1), date(2026, 7, 7))
    assert xlsx.startswith(b"PK") and "spreadsheet" in xlsx_type
    assert pdf.startswith(b"%PDF") and "pdf" in pdf_type


def test_xlsx_and_pdf_accept_null_cost_per_conversation():
    summary = _summary(cost_per_conversation_usd=None)
    assert export_llm_usage("xlsx", summary, _breakdown(), None, None)[0].startswith(b"PK")
    assert export_llm_usage("pdf", summary, _breakdown(), None, None)[0].startswith(b"%PDF")
