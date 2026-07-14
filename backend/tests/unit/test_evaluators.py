"""Unit tests for trace-aware grading (process evaluation)."""

import pytest

from app.services.test_suite import SimpleEvaluatorRegistry, _build_grading_context


def _sample_trace(*, node_error=None, risk_level="low"):
    return {
        "output": "Risk assessment: low. The contract looks fine.",
        "state": {
            "input": {"risk_level": risk_level, "contract_text": "MASTER SERVICES AGREEMENT"},
            "errors": [],
            "nodeExecutionStatus": {
                "n1": {
                    "name": "File Reader",
                    "type": "fileReaderNode",
                    "output": "contract text...",
                    "status": "success",
                    "error": None,
                },
                "n2": {
                    "name": "Knowledge Query",
                    "type": "knowledgeBaseNode",
                    "output": "retrieved clause",
                    "status": "success",
                    "error": node_error,
                },
            },
        },
        "token_usage": {"total_tokens": 100},
        "cost_usd": 0.001,
    }


class TestBuildGradingContext:
    def test_exposes_nodes_session_and_metrics(self):
        ctx = _build_grading_context(_sample_trace())
        assert ctx["nodes"]["n1"]["label"] == "File Reader"
        assert ctx["nodes_by_type"]["knowledgeBaseNode"][0]["output"] == "retrieved clause"
        assert ctx["session"]["risk_level"] == "low"
        assert ctx["errors"] == []
        assert ctx["tokens"]["total_tokens"] == 100

    def test_collects_node_errors(self):
        ctx = _build_grading_context(_sample_trace(node_error="NoneType has no len()"))
        assert len(ctx["errors"]) == 1
        assert ctx["errors"][0]["node"] == "n2"

    def test_handles_missing_trace(self):
        ctx = _build_grading_context(None)
        assert ctx["nodes"] == {}
        assert ctx["errors"] == []


class TestTraceAwareEvaluators:
    def setup_method(self):
        self.registry = SimpleEvaluatorRegistry()

    @pytest.mark.asyncio
    async def test_field_equals_reads_internal_value(self):
        metrics = await self.registry.evaluate(
            ["field_equals"],
            inputs={},
            outputs="some final text that differs",
            reference_outputs={"value": "low"},
            execution_trace=_sample_trace(risk_level="low"),
            technique_configs={"field_equals": {"field": "trace.session.risk_level"}},
        )
        assert metrics["field_equals"]["passed"] is True

    @pytest.mark.asyncio
    async def test_field_equals_fails_on_wrong_internal_value(self):
        metrics = await self.registry.evaluate(
            ["field_equals"],
            inputs={},
            outputs="Risk assessment: low.",
            reference_outputs=None,
            execution_trace=_sample_trace(risk_level="low"),
            technique_configs={
                "field_equals": {"field": "trace.session.risk_level", "expected": "high"}
            },
        )
        assert metrics["field_equals"]["passed"] is False

    @pytest.mark.asyncio
    async def test_field_equals_reads_node_output(self):
        metrics = await self.registry.evaluate(
            ["field_equals"],
            inputs={},
            outputs="",
            reference_outputs={"value": "retrieved clause"},
            execution_trace=_sample_trace(),
            technique_configs={"field_equals": {"field": "trace.nodes.n2.output"}},
        )
        assert metrics["field_equals"]["passed"] is True

    @pytest.mark.asyncio
    async def test_no_errors_passes_on_clean_run(self):
        metrics = await self.registry.evaluate(
            ["no_errors"],
            inputs={},
            outputs="ok",
            reference_outputs=None,
            execution_trace=_sample_trace(),
        )
        assert metrics["no_errors"]["passed"] is True

    @pytest.mark.asyncio
    async def test_process_grading_catches_error_behind_good_output(self):
        # Same good final output, but a node errored: contains passes, no_errors fails.
        trace = _sample_trace(node_error="ThreadScopedRAG: NoneType has no len()")
        metrics = await self.registry.evaluate(
            ["contains", "no_errors"],
            inputs={},
            outputs="Risk assessment: low. The contract looks fine.",
            reference_outputs={"value": "low"},
            execution_trace=trace,
        )
        assert metrics["contains"]["passed"] is True
        assert metrics["no_errors"]["passed"] is False

    @pytest.mark.asyncio
    async def test_existing_metrics_unchanged_without_trace(self):
        metrics = await self.registry.evaluate(
            ["contains"],
            inputs={},
            outputs="We are available 24/7",
            reference_outputs={"value": "24/7"},
        )
        assert metrics["contains"]["passed"] is True
