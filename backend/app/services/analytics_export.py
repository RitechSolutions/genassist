"""
Backend export service for analytics reports.
Supports CSV (stdlib), Excel (XlsxWriter), and PDF (fpdf2).
Receives already-fetched Pydantic model instances — no DB access.
"""

import csv
import io
from datetime import date
from typing import Optional

from app.schemas.analytics import (
    AgentDailyStatsItem,
    AgentStatsSummaryResponse,
    NodeDailyStatsItem,
    NodeTypeBreakdownItem,
)

# ── helpers ────────────────────────────────────────────────────────────────────

def _fmt_ms(val: Optional[float]) -> str:
    return f"{round(val)} ms" if val is not None else "—"


def _fmt_pct(val: Optional[float]) -> str:
    return f"{val * 100:.1f}%" if val is not None else "—"


def _agent_name(agent_id: str, names: dict[str, str]) -> str:
    return names.get(agent_id, agent_id[:8] + "…")


NODE_TYPE_LABELS: dict[str, str] = {
    "llm": "LLM",
    "llm_node": "LLM",
    "condition": "Condition",
    "condition_node": "Condition",
    "api_call": "API Call",
    "api_call_node": "API Call",
    "knowledge_base": "Knowledge Base",
    "knowledge_base_node": "Knowledge Base",
    "user_input": "User Input",
    "user_input_node": "User Input",
    "set_variable": "Set Variable",
    "set_variable_node": "Set Variable",
    "function": "Function",
    "function_node": "Function",
    "send_message": "Send Message",
    "send_message_node": "Send Message",
    "start": "Start",
    "start_node": "Start",
    "end": "End",
    "end_node": "End",
}


def _node_label(node_type: str) -> str:
    return NODE_TYPE_LABELS.get(node_type, node_type.replace("_", " ").title())


def _format_period(from_date: Optional[date], to_date: Optional[date]) -> str:
    if from_date and to_date:
        return f"{from_date} - {to_date}"
    if from_date or to_date:
        return str(from_date or to_date)
    return "All time"


# ── aggregation ────────────────────────────────────────────────────────────────

def _aggregate_agent_items(
    items: list[AgentDailyStatsItem],
) -> list[dict]:
    """Roll up daily rows into one dict per agent (weighted-avg for ms)."""
    agg: dict[str, dict] = {}
    for item in items:
        aid = str(item.agent_id)
        if aid not in agg:
            agg[aid] = {
                "agent_id": aid,
                "unique_conversations": 0,
                "finalized_conversations": 0,
                "in_progress_conversations": 0,
                "execution_count": 0,
                "success_count": 0,
                "error_count": 0,
                "total_nodes_executed": 0,
                "rag_used_count": 0,
                "thumbs_up_count": 0,
                "thumbs_down_count": 0,
                "_total_ms": 0.0,
                "_ms_count": 0,
            }
        a = agg[aid]
        a["unique_conversations"] += item.unique_conversations
        a["finalized_conversations"] += item.finalized_conversations
        a["in_progress_conversations"] += item.in_progress_conversations
        a["execution_count"] += item.execution_count
        a["success_count"] += item.success_count
        a["error_count"] += item.error_count
        a["total_nodes_executed"] += item.total_nodes_executed
        a["rag_used_count"] += item.rag_used_count
        a["thumbs_up_count"] += item.thumbs_up_count
        a["thumbs_down_count"] += item.thumbs_down_count
        if item.avg_response_ms is not None:
            a["_total_ms"] += item.avg_response_ms * item.execution_count
            a["_ms_count"] += item.execution_count

    result = []
    for a in agg.values():
        a["avg_response_ms"] = (a["_total_ms"] / a["_ms_count"]) if a["_ms_count"] > 0 else None
        result.append(a)
    return sorted(result, key=lambda x: x["execution_count"], reverse=True)


def _aggregate_node_items(items: list[NodeDailyStatsItem]) -> list[dict]:
    """Roll up daily node rows into one dict per agent×node_type."""
    agg: dict[str, dict] = {}
    for item in items:
        key = f"{item.agent_id}__{item.node_type}"
        if key not in agg:
            agg[key] = {
                "agent_id": str(item.agent_id),
                "node_type": item.node_type,
                "execution_count": 0,
                "success_count": 0,
                "failure_count": 0,
                "_total_ms": 0.0,
                "_ms_count": 0,
            }
        a = agg[key]
        a["execution_count"] += item.execution_count
        a["success_count"] += item.success_count
        a["failure_count"] += item.failure_count
        if item.avg_execution_ms is not None:
            a["_total_ms"] += item.avg_execution_ms * item.execution_count
            a["_ms_count"] += item.execution_count

    result = []
    for a in agg.values():
        a["avg_execution_ms"] = (a["_total_ms"] / a["_ms_count"]) if a["_ms_count"] > 0 else None
        result.append(a)
    return sorted(result, key=lambda x: x["execution_count"], reverse=True)


# ── CSV ────────────────────────────────────────────────────────────────────────

def _csv_write_rows(writer: csv.writer, headers: list[str], rows: list[list]) -> None:  # type: ignore[type-arg]
    writer.writerow(headers)
    writer.writerows(rows)


def _export_agents_csv(
    summary: AgentStatsSummaryResponse,
    items: list[AgentDailyStatsItem],
    agent_id: Optional[str],
    agent_names: dict[str, str],
    from_date: Optional[date],
    to_date: Optional[date],
    node_breakdown: Optional[list[NodeTypeBreakdownItem]],
) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf)

    # title / filters
    w.writerow(["Agent Performance Report"])
    w.writerow([f"Period: {_format_period(from_date, to_date)}"])
    if agent_id:
        w.writerow([f"Agent: {_agent_name(agent_id, agent_names)}"])
    w.writerow([])

    # summary
    success_rate = (summary.total_success / summary.total_executions * 100) if summary.total_executions > 0 else 0
    total_feedback = summary.total_thumbs_up + summary.total_thumbs_down
    satisfaction = f"{summary.total_thumbs_up / total_feedback * 100:.0f}%" if total_feedback > 0 else "—"
    w.writerow(["Summary"])
    w.writerow(["Conversations", summary.total_unique_conversations])
    w.writerow(["Success Rate", f"{success_rate:.1f}% ({summary.total_success} of {summary.total_executions})"])
    w.writerow(["Avg Response Time", _fmt_ms(summary.avg_response_ms)])
    w.writerow(["Satisfaction", f"{satisfaction} ({summary.total_thumbs_up} positive, {summary.total_thumbs_down} negative)"])
    w.writerow([])

    # data section
    if agent_id:
        # per-day
        w.writerow(["By Date"])
        _csv_write_rows(w,
            ["Date", "Conversations", "Completed", "In Progress", "Success Rate", "Avg Response (ms)", "Thumbs Up", "Thumbs Down"],
            [
                [
                    str(i.stat_date),
                    i.unique_conversations,
                    i.finalized_conversations,
                    i.in_progress_conversations,
                    f"{i.success_count / i.execution_count * 100:.1f}% ({i.success_count}/{i.execution_count})" if i.execution_count > 0 else "—",
                    round(i.avg_response_ms) if i.avg_response_ms is not None else "",
                    i.thumbs_up_count,
                    i.thumbs_down_count,
                ]
                for i in sorted(items, key=lambda x: x.stat_date)
            ],
        )
    else:
        # per-agent aggregated
        w.writerow(["By Agent"])
        rows_agg = _aggregate_agent_items(items)
        _csv_write_rows(w,
            ["Agent", "Conversations", "Completed", "In Progress", "Success Rate", "Avg Response (ms)", "Thumbs Up", "Thumbs Down"],
            [
                [
                    _agent_name(a["agent_id"], agent_names),
                    a["unique_conversations"],
                    a["finalized_conversations"],
                    a["in_progress_conversations"],
                    f"{a['success_count'] / a['execution_count'] * 100:.1f}% ({a['success_count']}/{a['execution_count']})" if a["execution_count"] > 0 else "—",
                    round(a["avg_response_ms"]) if a["avg_response_ms"] is not None else "",
                    a["thumbs_up_count"],
                    a["thumbs_down_count"],
                ]
                for a in rows_agg
            ],
        )

    # node breakdown (single agent only)
    if node_breakdown:
        w.writerow([])
        w.writerow(["Node Breakdown"])
        _csv_write_rows(w,
            ["Node Type", "Executions", "Success", "Failures", "Success Rate", "Avg Exec (ms)"],
            [
                [
                    _node_label(n.node_type),
                    n.execution_count,
                    n.success_count,
                    n.failure_count,
                    _fmt_pct(n.success_rate),
                    _fmt_ms(n.avg_execution_ms),
                ]
                for n in sorted(node_breakdown, key=lambda x: x.execution_count, reverse=True)
            ],
        )

    return buf.getvalue().encode("utf-8-sig")


def _export_nodes_csv(
    items: list[NodeDailyStatsItem],
    agent_names: dict[str, str],
    agent_id: Optional[str],
    from_date: Optional[date],
    to_date: Optional[date],
) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf)

    w.writerow(["Node Analytics Report"])
    w.writerow([f"Period: {_format_period(from_date, to_date)}"])
    if agent_id:
        w.writerow([f"Agent: {_agent_name(agent_id, agent_names)}"])
    w.writerow([])

    rows_agg = _aggregate_node_items(items)
    _csv_write_rows(w,
        ["Agent", "Node Type", "Executions", "Success", "Failures", "Avg Exec (ms)"],
        [
            [
                _agent_name(a["agent_id"], agent_names),
                _node_label(a["node_type"]),
                a["execution_count"],
                a["success_count"],
                a["failure_count"],
                _fmt_ms(a["avg_execution_ms"]),
            ]
            for a in rows_agg
        ],
    )

    return buf.getvalue().encode("utf-8-sig")


# ── Excel ──────────────────────────────────────────────────────────────────────
# Blue palette: header = blue-600 (#2563EB), alt row = blue-50 (#EFF6FF)

def _excel_header_format(wb):  # type: ignore[no-untyped-def]
    return wb.add_format({
        "bold": True,
        "bg_color": "#2563EB",
        "font_color": "#FFFFFF",
        "border": 1,
        "border_color": "#1D4ED8",
    })


def _excel_alt_format(wb):  # type: ignore[no-untyped-def]
    return wb.add_format({"bg_color": "#EFF6FF", "border": 1, "border_color": "#BFDBFE"})


def _excel_plain_format(wb):  # type: ignore[no-untyped-def]
    return wb.add_format({"border": 1, "border_color": "#BFDBFE"})


def _excel_title_format(wb):  # type: ignore[no-untyped-def]
    return wb.add_format({"bold": True, "font_size": 14, "font_color": "#1D4ED8"})


def _excel_label_format(wb):  # type: ignore[no-untyped-def]
    return wb.add_format({"bold": True, "font_color": "#64748B"})


def _excel_section_format(wb):  # type: ignore[no-untyped-def]
    return wb.add_format({"bold": True, "font_size": 11, "font_color": "#2563EB"})


def _xl_write_table(ws, row: int, headers: list[str], data_rows: list[list], header_fmt, alt_fmt, plain_fmt) -> int:  # type: ignore[no-untyped-def]
    for col, h in enumerate(headers):
        ws.write(row, col, h, header_fmt)
    row += 1
    for i, data_row in enumerate(data_rows):
        fmt = alt_fmt if i % 2 == 1 else plain_fmt
        for col, val in enumerate(data_row):
            ws.write(row, col, val, fmt)
        row += 1
    return row + 1  # blank row after table


def _export_agents_excel(
    summary: AgentStatsSummaryResponse,
    items: list[AgentDailyStatsItem],
    agent_id: Optional[str],
    agent_names: dict[str, str],
    from_date: Optional[date],
    to_date: Optional[date],
    node_breakdown: Optional[list[NodeTypeBreakdownItem]],
) -> bytes:
    import xlsxwriter  # type: ignore[import-untyped]

    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {"in_memory": True})
    header_fmt = _excel_header_format(wb)
    alt_fmt = _excel_alt_format(wb)
    plain_fmt = _excel_plain_format(wb)
    titlefmt = _excel_title_format(wb)
    labelfmt = _excel_label_format(wb)
    sectionfmt = _excel_section_format(wb)

    # ── Sheet 1: Summary ──────────────────────────────────────────────────────
    ws_sum = wb.add_worksheet("Summary")
    ws_sum.set_column(0, 0, 28)
    ws_sum.set_column(1, 1, 20)

    ws_sum.write(0, 0, "Agent Performance Report", titlefmt)
    ws_sum.write(1, 0, "Period", labelfmt)
    ws_sum.write(1, 1, _format_period(from_date, to_date))
    if agent_id:
        ws_sum.write(2, 0, "Agent", labelfmt)
        ws_sum.write(2, 1, _agent_name(agent_id, agent_names))

    ws_sum.write(3, 0, "Summary", sectionfmt)

    success_rate = (summary.total_success / summary.total_executions * 100) if summary.total_executions > 0 else 0
    total_feedback = summary.total_thumbs_up + summary.total_thumbs_down
    satisfaction = f"{summary.total_thumbs_up / total_feedback * 100:.0f}%" if total_feedback > 0 else "—"
    metrics = [
        ("Conversations", summary.total_unique_conversations),
        ("Success Rate", f"{success_rate:.1f}% ({summary.total_success} of {summary.total_executions})"),
        ("Avg Response Time", _fmt_ms(summary.avg_response_ms)),
        ("Satisfaction", f"{satisfaction} ({summary.total_thumbs_up} positive, {summary.total_thumbs_down} negative)"),
    ]
    start_row = 4
    _xl_write_table(ws_sum, start_row, ["Metric", "Value"], [[m, v] for m, v in metrics], header_fmt, alt_fmt, plain_fmt)

    # ── Sheet 2: Data ─────────────────────────────────────────────────────────
    ws_data = wb.add_worksheet("Data")
    ws_data.write(0, 0, "By Date" if agent_id else "By Agent", sectionfmt)
    ws_data.set_column(0, 0, 20)
    ws_data.set_column(1, 9, 14)

    if agent_id:
        headers = ["Date", "Conversations", "Completed", "In Progress", "Success Rate", "Avg Response (ms)", "Thumbs Up", "Thumbs Down"]
        data_rows = [
            [
                str(i.stat_date),
                i.unique_conversations,
                i.finalized_conversations,
                i.in_progress_conversations,
                f"{i.success_count / i.execution_count * 100:.1f}%" if i.execution_count > 0 else "—",
                round(i.avg_response_ms) if i.avg_response_ms is not None else "",
                i.thumbs_up_count,
                i.thumbs_down_count,
            ]
            for i in sorted(items, key=lambda x: x.stat_date)
        ]
    else:
        headers = ["Agent", "Conversations", "Completed", "In Progress", "Success Rate", "Avg Response (ms)", "Thumbs Up", "Thumbs Down"]
        rows_agg = _aggregate_agent_items(items)
        data_rows = [
            [
                _agent_name(a["agent_id"], agent_names),
                a["unique_conversations"],
                a["finalized_conversations"],
                a["in_progress_conversations"],
                f"{a['success_count'] / a['execution_count'] * 100:.1f}%" if a["execution_count"] > 0 else "—",
                round(a["avg_response_ms"]) if a["avg_response_ms"] is not None else "",
                a["thumbs_up_count"],
                a["thumbs_down_count"],
            ]
            for a in rows_agg
        ]
    _xl_write_table(ws_data, 1, headers, data_rows, header_fmt, alt_fmt, plain_fmt)

    # ── Sheet 3: Node Breakdown (if applicable) ───────────────────────────────
    if node_breakdown:
        ws_nb = wb.add_worksheet("Node Breakdown")
        ws_nb.set_column(0, 0, 22)
        ws_nb.set_column(1, 5, 14)
        ws_nb.write(0, 0, "Node Breakdown", sectionfmt)
        nb_rows = [
            [
                _node_label(n.node_type),
                n.execution_count,
                n.success_count,
                n.failure_count,
                _fmt_pct(n.success_rate),
                _fmt_ms(n.avg_execution_ms),
            ]
            for n in sorted(node_breakdown, key=lambda x: x.execution_count, reverse=True)
        ]
        _xl_write_table(ws_nb, 1,
            ["Node Type", "Executions", "Success", "Failures", "Success Rate", "Avg Exec (ms)"],
            nb_rows, header_fmt, alt_fmt, plain_fmt)

    wb.close()
    return buf.getvalue()


def _export_nodes_excel(
    items: list[NodeDailyStatsItem],
    agent_names: dict[str, str],
    agent_id: Optional[str],
    from_date: Optional[date],
    to_date: Optional[date],
) -> bytes:
    import xlsxwriter  # type: ignore[import-untyped]

    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {"in_memory": True})
    header_fmt = _excel_header_format(wb)
    alt_fmt = _excel_alt_format(wb)
    plain_fmt = _excel_plain_format(wb)
    sectionfmt = _excel_section_format(wb)

    ws = wb.add_worksheet("Node Analytics")
    ws.set_column(0, 0, 22)
    ws.set_column(1, 5, 14)
    ws.write(0, 0, "Node Analytics", sectionfmt)

    rows_agg = _aggregate_node_items(items)
    data_rows = [
        [
            _agent_name(a["agent_id"], agent_names),
            _node_label(a["node_type"]),
            a["execution_count"],
            a["success_count"],
            a["failure_count"],
            _fmt_ms(a["avg_execution_ms"]),
        ]
        for a in rows_agg
    ]
    _xl_write_table(ws, 1,
        ["Agent", "Node Type", "Executions", "Success", "Failures", "Avg Exec (ms)"],
        data_rows, header_fmt, alt_fmt, plain_fmt)

    wb.close()
    return buf.getvalue()


# ── PDF ────────────────────────────────────────────────────────────────────────

# Map Unicode characters unsupported by the default Helvetica font to ASCII equivalents.
_PDF_CHAR_MAP = str.maketrans({"\u2013": "-", "\u2014": "-", "\u2026": "...", "\u00b7": "."})


def _pdf_safe(text: str) -> str:
    """Replace Unicode characters that the default PDF font cannot render."""
    return text.translate(_PDF_CHAR_MAP)


def _pdf_title_block(pdf, title: str, subtitle: str, filters: list[str]) -> None:  # type: ignore[no-untyped-def]
    """Render a blue header band with white title text, then subtitle + filters."""
    page_w = pdf.w - pdf.l_margin - pdf.r_margin
    # Blue band
    pdf.set_fill_color(37, 99, 235)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 15)
    pdf.cell(page_w, 12, _pdf_safe(title), border=0, ln=0, fill=True)
    pdf.ln(12)
    # Subtitle
    pdf.set_fill_color(255, 255, 255)
    pdf.set_text_color(100, 116, 139)
    pdf.set_font("Helvetica", "", 8)
    pdf.cell(0, 5, _pdf_safe(subtitle), ln=True)
    if filters:
        pdf.cell(0, 5, _pdf_safe("  .  ".join(filters)), ln=True)
    pdf.ln(3)
    pdf.set_text_color(24, 24, 27)


def _pdf_section_header(pdf, label: str) -> None:  # type: ignore[no-untyped-def]
    """Render a blue section label above a table."""
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(37, 99, 235)
    pdf.cell(0, 7, _pdf_safe(label), ln=True)
    pdf.set_text_color(24, 24, 27)


def _pdf_table(pdf, headers: list[str], rows: list[list[str]], col_widths: list[int]) -> None:  # type: ignore[no-untyped-def]
    # Header row — blue-600
    pdf.set_fill_color(37, 99, 235)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 8)
    for i, h in enumerate(headers):
        pdf.cell(col_widths[i], 7, _pdf_safe(h), border=1, fill=True)
    pdf.ln()

    # Data rows — alt = blue-50
    pdf.set_text_color(24, 24, 27)
    pdf.set_font("Helvetica", "", 8)
    for row_idx, row in enumerate(rows):
        if row_idx % 2 == 1:
            pdf.set_fill_color(239, 246, 255)
            fill = True
        else:
            fill = False
        for i, val in enumerate(row):
            pdf.cell(col_widths[i], 6, _pdf_safe(str(val)), border=1, fill=fill)
        pdf.ln()
    pdf.ln(4)


def _export_agents_pdf(
    summary: AgentStatsSummaryResponse,
    items: list[AgentDailyStatsItem],
    agent_id: Optional[str],
    agent_names: dict[str, str],
    from_date: Optional[date],
    to_date: Optional[date],
    node_breakdown: Optional[list[NodeTypeBreakdownItem]],
) -> bytes:
    from fpdf import FPDF  # type: ignore[import-untyped]

    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=10)

    filters = [f"Period: {_format_period(from_date, to_date)}"]
    if agent_id:
        filters.append(f"Agent: {_agent_name(agent_id, agent_names)}")
    _pdf_title_block(pdf, "Agent Performance Report", "Pre-aggregated daily execution statistics per agent", filters)

    # Summary table
    success_rate = (summary.total_success / summary.total_executions * 100) if summary.total_executions > 0 else 0
    total_feedback = summary.total_thumbs_up + summary.total_thumbs_down
    satisfaction = f"{summary.total_thumbs_up / total_feedback * 100:.0f}%" if total_feedback > 0 else "—"
    sum_rows = [
        ["Conversations", str(summary.total_unique_conversations)],
        ["Success Rate", f"{success_rate:.1f}% ({summary.total_success} of {summary.total_executions})"],
        ["Avg Response Time", _fmt_ms(summary.avg_response_ms)],
        ["Satisfaction", f"{satisfaction} ({summary.total_thumbs_up} pos, {summary.total_thumbs_down} neg)"],
    ]
    _pdf_section_header(pdf, "Summary")
    _pdf_table(pdf, ["Metric", "Value"], sum_rows, [70, 100])

    # Data table
    if agent_id:
        _pdf_section_header(pdf, "By Date")
        data_rows = [
            [
                str(i.stat_date),
                str(i.unique_conversations),
                str(i.finalized_conversations),
                str(i.in_progress_conversations),
                f"{i.success_count / i.execution_count * 100:.1f}%" if i.execution_count > 0 else "—",
                _fmt_ms(i.avg_response_ms),
                str(i.thumbs_up_count),
                str(i.thumbs_down_count),
            ]
            for i in sorted(items, key=lambda x: x.stat_date)
        ]
        _pdf_table(pdf,
            ["Date", "Conv.", "Completed", "In Prog.", "Success Rate", "Avg (ms)", "Thumbs Up", "Thumbs Down"],
            data_rows,
            [26, 22, 26, 24, 30, 28, 26, 26],
        )
    else:
        _pdf_section_header(pdf, "By Agent")
        rows_agg = _aggregate_agent_items(items)
        data_rows = [
            [
                _agent_name(a["agent_id"], agent_names),
                str(a["unique_conversations"]),
                str(a["finalized_conversations"]),
                str(a["in_progress_conversations"]),
                f"{a['success_count'] / a['execution_count'] * 100:.1f}%" if a["execution_count"] > 0 else "—",
                _fmt_ms(a["avg_response_ms"]),
                str(a["thumbs_up_count"]),
                str(a["thumbs_down_count"]),
            ]
            for a in rows_agg
        ]
        _pdf_table(pdf,
            ["Agent", "Conv.", "Completed", "In Prog.", "Success Rate", "Avg (ms)", "Thumbs Up", "Thumbs Down"],
            data_rows,
            [40, 22, 26, 24, 30, 28, 26, 26],
        )

    # Node breakdown
    if node_breakdown:
        _pdf_section_header(pdf, "Node Breakdown")
        nb_rows = [
            [
                _node_label(n.node_type),
                str(n.execution_count),
                str(n.success_count),
                str(n.failure_count),
                _fmt_pct(n.success_rate),
                _fmt_ms(n.avg_execution_ms),
            ]
            for n in sorted(node_breakdown, key=lambda x: x.execution_count, reverse=True)
        ]
        _pdf_table(pdf,
            ["Node Type", "Executions", "Success", "Failures", "Success Rate", "Avg Exec (ms)"],
            nb_rows,
            [50, 30, 30, 30, 36, 36],
        )

    return bytes(pdf.output())


def _export_nodes_pdf(
    items: list[NodeDailyStatsItem],
    agent_names: dict[str, str],
    agent_id: Optional[str],
    from_date: Optional[date],
    to_date: Optional[date],
) -> bytes:
    from fpdf import FPDF  # type: ignore[import-untyped]

    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=10)

    filters = [f"Period: {_format_period(from_date, to_date)}"]
    if agent_id:
        filters.append(f"Agent: {_agent_name(agent_id, agent_names)}")
    _pdf_title_block(pdf, "Node Analytics Report", "Workflow node execution metrics by type and agent", filters)

    rows_agg = _aggregate_node_items(items)
    data_rows = [
        [
            _agent_name(a["agent_id"], agent_names),
            _node_label(a["node_type"]),
            str(a["execution_count"]),
            str(a["success_count"]),
            str(a["failure_count"]),
            _fmt_ms(a["avg_execution_ms"]),
        ]
        for a in rows_agg
    ]
    _pdf_table(pdf,
        ["Agent", "Node Type", "Executions", "Success", "Failures", "Avg Exec (ms)"],
        data_rows,
        [55, 45, 28, 28, 28, 36],
    )

    return bytes(pdf.output())


# ── Public API ─────────────────────────────────────────────────────────────────

MEDIA_TYPES = {
    "csv": "text/csv",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pdf": "application/pdf",
}

EXTENSIONS = {"csv": "csv", "xlsx": "xlsx", "pdf": "pdf"}

VALID_FORMATS = frozenset(MEDIA_TYPES.keys())


async def get_agent_names(repo) -> dict[str, str]:
    """Build {agent_id: agent_name} lookup from the agent repository."""
    agents = await repo.get_all_full()
    return {str(a.id): a.name for a in agents}


def export_agent_stats(
    fmt: str,
    summary: AgentStatsSummaryResponse,
    items: list[AgentDailyStatsItem],
    agent_id: Optional[str],
    agent_names: dict[str, str],
    from_date: Optional[date],
    to_date: Optional[date],
    node_breakdown: Optional[list[NodeTypeBreakdownItem]] = None,
) -> tuple[bytes, str]:
    """Returns (content_bytes, media_type)."""
    if fmt == "csv":
        return _export_agents_csv(summary, items, agent_id, agent_names, from_date, to_date, node_breakdown), MEDIA_TYPES["csv"]
    if fmt == "xlsx":
        return _export_agents_excel(summary, items, agent_id, agent_names, from_date, to_date, node_breakdown), MEDIA_TYPES["xlsx"]
    if fmt == "pdf":
        return _export_agents_pdf(summary, items, agent_id, agent_names, from_date, to_date, node_breakdown), MEDIA_TYPES["pdf"]
    raise ValueError(f"Unsupported format: {fmt}")


def export_node_stats(
    fmt: str,
    items: list[NodeDailyStatsItem],
    agent_names: dict[str, str],
    agent_id: Optional[str],
    from_date: Optional[date],
    to_date: Optional[date],
) -> tuple[bytes, str]:
    """Returns (content_bytes, media_type)."""
    if fmt == "csv":
        return _export_nodes_csv(items, agent_names, agent_id, from_date, to_date), MEDIA_TYPES["csv"]
    if fmt == "xlsx":
        return _export_nodes_excel(items, agent_names, agent_id, from_date, to_date), MEDIA_TYPES["xlsx"]
    if fmt == "pdf":
        return _export_nodes_pdf(items, agent_names, agent_id, from_date, to_date), MEDIA_TYPES["pdf"]
    raise ValueError(f"Unsupported format: {fmt}")
