"""LLM usage report exporters (csv / xlsx / pdf)"""

import csv
import io
from datetime import date
from typing import Optional

from app.schemas.llm_usage import BREAKDOWN_DIMENSIONS, LlmUsageBreakdownResponse, LlmUsageSummaryResponse
from app.services.analytics_export import EXTENSIONS, MEDIA_TYPES, VALID_FORMATS  # noqa: F401

_DIMENSION_HEADER = {d: d.capitalize() for d in BREAKDOWN_DIMENSIONS} | {"source": "Usage type"}

METHODOLOGY_NOTE = (
    "Costs are calculated from reported tokens and the configured rates; they may differ from provider invoices."
)


def _period(from_date: Optional[date], to_date: Optional[date]) -> str:
    if from_date and to_date:
        return f"{from_date.isoformat()} to {to_date.isoformat()}"
    if from_date:
        return f"from {from_date.isoformat()}"
    if to_date:
        return f"through {to_date.isoformat()}"
    return "all time"


def _usd(value: Optional[float]) -> str:
    return "N/A" if value is None else f"{value:.4f}"


def _summary_rows(summary: LlmUsageSummaryResponse) -> list[tuple[str, str]]:
    return [
        ("Total LLM cost (USD)", _usd(summary.total_cost_usd)),
        ("Cost is partial (unpriced calls present)", "yes" if summary.cost_is_partial else "no"),
        ("Cost per conversation (USD)", _usd(summary.cost_per_conversation_usd)),
        ("Agent Studio test cost (USD)", _usd(summary.agent_studio_test_cost_usd)),
        ("Total tokens", str(summary.total_tokens)),
        ("Cache read tokens", str(summary.total_cache_read_tokens)),
        ("Cache write tokens", str(summary.total_cache_creation_tokens)),
        ("Total calls", str(summary.total_calls)),
        ("Calls priced at configured rates", str(summary.configured_calls)),
        ("Calls priced at bundled fallback rates", str(summary.fallback_calls)),
        ("Calls carrying legacy estimated cost", str(summary.legacy_estimate_calls)),
        ("Unpriced calls", str(summary.unpriced_calls)),
        ("Priced token coverage (%)", f"{summary.priced_token_coverage_pct:.2f}"),
    ]


def export_llm_usage(
    fmt: str,
    summary: LlmUsageSummaryResponse,
    breakdown: LlmUsageBreakdownResponse,
    from_date: Optional[date],
    to_date: Optional[date],
) -> tuple[bytes, str]:
    if fmt == "csv":
        content = _csv(summary, breakdown, from_date, to_date)
    elif fmt == "xlsx":
        content = _xlsx(summary, breakdown, from_date, to_date)
    elif fmt == "pdf":
        content = _pdf(summary, breakdown, from_date, to_date)
    else:
        raise ValueError(f"Unsupported format: {fmt}")
    return content, MEDIA_TYPES[fmt]


def _breakdown_header(breakdown: LlmUsageBreakdownResponse) -> list[str]:
    return [_DIMENSION_HEADER.get(breakdown.dimension, "Key"), "Cost (USD)", "Tokens", "Calls", "Unpriced calls"]


def _breakdown_rows(breakdown: LlmUsageBreakdownResponse) -> list[list[str]]:
    return [
        [i.label, f"{i.cost_usd:.4f}", str(i.total_tokens), str(i.calls), str(i.unpriced_calls)]
        for i in breakdown.items
    ]


def _csv(summary, breakdown, from_date, to_date) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["LLM Usage Report"])
    w.writerow([f"Period: {_period(from_date, to_date)}"])
    w.writerow([METHODOLOGY_NOTE])
    w.writerow([])
    w.writerow(["Metric", "Value"])
    w.writerows(_summary_rows(summary))
    w.writerow([])
    w.writerow(_breakdown_header(breakdown))
    w.writerows(_breakdown_rows(breakdown))
    return buf.getvalue().encode("utf-8-sig")


def _xlsx(summary, breakdown, from_date, to_date) -> bytes:
    import xlsxwriter

    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {"in_memory": True})
    bold = wb.add_format({"bold": True})

    ws = wb.add_worksheet("Summary")
    ws.write(0, 0, "LLM Usage Report", bold)
    ws.write(1, 0, f"Period: {_period(from_date, to_date)}")
    ws.write(2, 0, METHODOLOGY_NOTE)
    ws.write(4, 0, "Metric", bold)
    ws.write(4, 1, "Value", bold)
    for r, (label, value) in enumerate(_summary_rows(summary), start=5):
        ws.write(r, 0, label)
        ws.write(r, 1, value)
    ws.set_column(0, 0, 42)
    ws.set_column(1, 1, 24)

    bd = wb.add_worksheet("Breakdown")
    for c, header in enumerate(_breakdown_header(breakdown)):
        bd.write(0, c, header, bold)
    for r, row in enumerate(_breakdown_rows(breakdown), start=1):
        for c, value in enumerate(row):
            bd.write(r, c, value)
    bd.set_column(0, 0, 32)
    bd.set_column(1, 4, 16)

    wb.close()
    return buf.getvalue()


def _pdf(summary, breakdown, from_date, to_date) -> bytes:
    from fpdf import FPDF

    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, "LLM Usage Report", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=10)
    pdf.cell(0, 6, f"Period: {_period(from_date, to_date)}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, METHODOLOGY_NOTE, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 7, "Summary", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=10)
    for label, value in _summary_rows(summary):
        pdf.cell(90, 6, label, border=1)
        pdf.cell(60, 6, value, border=1, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 7, "Breakdown", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "B", 9)
    widths = [90, 40, 40, 30, 40]
    for w, header in zip(widths, _breakdown_header(breakdown)):
        pdf.cell(w, 6, header, border=1)
    pdf.ln()
    pdf.set_font("Helvetica", size=9)
    for row in _breakdown_rows(breakdown):
        for w, value in zip(widths, row):
            pdf.cell(w, 6, str(value)[:48], border=1)
        pdf.ln()
    return bytes(pdf.output())
