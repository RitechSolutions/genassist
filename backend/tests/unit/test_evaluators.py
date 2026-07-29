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


class TestContainsAndNotContains:
    def setup_method(self):
        self.registry = SimpleEvaluatorRegistry()

    @pytest.mark.asyncio
    async def test_contains_is_case_insensitive(self):
        metrics = await self.registry.evaluate(
            ["contains"],
            inputs={},
            outputs="We are OPEN 24/7 for support",
            reference_outputs={"value": "open 24/7"},
        )
        assert metrics["contains"]["passed"] is True

    @pytest.mark.asyncio
    async def test_not_contains_passes_when_forbidden_text_absent(self):
        metrics = await self.registry.evaluate(
            ["not_contains"],
            inputs={},
            outputs="Here is the information you asked for.",
            reference_outputs=None,
            technique_configs={"not_contains": {"text": "I cannot help"}},
        )
        assert metrics["not_contains"]["passed"] is True

    @pytest.mark.asyncio
    async def test_not_contains_fails_when_forbidden_text_present(self):
        metrics = await self.registry.evaluate(
            ["not_contains"],
            inputs={},
            outputs="Sorry, I cannot help with that request.",
            reference_outputs=None,
            technique_configs={"not_contains": {"text": "I cannot help"}},
        )
        assert metrics["not_contains"]["passed"] is False

    @pytest.mark.asyncio
    async def test_not_contains_is_case_insensitive(self):
        metrics = await self.registry.evaluate(
            ["not_contains"],
            inputs={},
            outputs="The password is SECRET123.",
            reference_outputs=None,
            technique_configs={"not_contains": {"text": "secret"}},
        )
        assert metrics["not_contains"]["passed"] is False

    @pytest.mark.asyncio
    async def test_not_contains_fails_when_forbidden_text_missing(self):
        metrics = await self.registry.evaluate(
            ["not_contains"],
            inputs={},
            outputs="Any output at all.",
            reference_outputs=None,
            technique_configs={"not_contains": {"text": ""}},
        )
        assert metrics["not_contains"]["passed"] is False
        assert metrics["not_contains"]["comment"] == "No forbidden phrases configured."

    @pytest.mark.asyncio
    async def test_not_contains_passes_on_empty_output(self):
        metrics = await self.registry.evaluate(
            ["not_contains"],
            inputs={},
            outputs="",
            reference_outputs=None,
            technique_configs={"not_contains": {"text": "forbidden"}},
        )
        assert metrics["not_contains"]["passed"] is True

    @pytest.mark.asyncio
    async def test_not_contains_multiple_phrases_reports_matches(self):
        metrics = await self.registry.evaluate(
            ["not_contains"],
            inputs={},
            outputs="You could try Globex or initech instead.",
            reference_outputs=None,
            technique_configs={"not_contains": {"phrases": ["Acme", "Globex", "Initech"]}},
        )
        assert metrics["not_contains"]["passed"] is False
        assert "Globex" in metrics["not_contains"]["comment"]
        assert "Initech" in metrics["not_contains"]["comment"]
        assert "Acme" not in metrics["not_contains"]["comment"]

    @pytest.mark.asyncio
    async def test_not_contains_passes_when_no_phrase_present(self):
        metrics = await self.registry.evaluate(
            ["not_contains"],
            inputs={},
            outputs="Our service lets you do everything from the app.",
            reference_outputs=None,
            technique_configs={"not_contains": {"phrases": ["Acme", "Globex"]}},
        )
        assert metrics["not_contains"]["passed"] is True

    @pytest.mark.asyncio
    async def test_not_contains_casefold_matches_german_sharp_s(self):
        metrics = await self.registry.evaluate(
            ["not_contains"],
            inputs={},
            outputs="DIE STRASSE IST GESPERRT.",
            reference_outputs=None,
            technique_configs={"not_contains": {"phrases": ["straße"]}},
        )
        assert metrics["not_contains"]["passed"] is False

    @pytest.mark.asyncio
    async def test_contains_casefold_matches_german_sharp_s(self):
        metrics = await self.registry.evaluate(
            ["contains"],
            inputs={},
            outputs="Die Straße ist offen.",
            reference_outputs={"value": "STRASSE"},
        )
        assert metrics["contains"]["passed"] is True

    @pytest.mark.asyncio
    async def test_not_contains_trims_and_dedupes_phrases(self):
        metrics = await self.registry.evaluate(
            ["not_contains"],
            inputs={},
            outputs="Nothing forbidden here.",
            reference_outputs=None,
            technique_configs={"not_contains": {"phrases": ["  Acme  ", "acme", "", "   "]}},
        )
        assert metrics["not_contains"]["passed"] is True

    @pytest.mark.asyncio
    async def test_not_contains_empty_phrase_list_fails_with_config_message(self):
        metrics = await self.registry.evaluate(
            ["not_contains"],
            inputs={},
            outputs="Any output.",
            reference_outputs=None,
            technique_configs={"not_contains": {"phrases": ["", "   "]}},
        )
        assert metrics["not_contains"]["passed"] is False
        assert metrics["not_contains"]["comment"] == "No forbidden phrases configured."

    @pytest.mark.asyncio
    async def test_not_contains_rejects_malformed_phrase_config(self):
        for bad_phrases in (123, True, {"nested": "dict"}, [123, None, {}]):
            metrics = await self.registry.evaluate(
                ["not_contains"],
                inputs={},
                outputs="Any output.",
                reference_outputs=None,
                technique_configs={"not_contains": {"phrases": bad_phrases}},
            )
            assert metrics["not_contains"]["passed"] is False
            assert metrics["not_contains"]["comment"] == "No forbidden phrases configured."

    @pytest.mark.asyncio
    async def test_not_contains_rejects_malformed_legacy_text(self):
        metrics = await self.registry.evaluate(
            ["not_contains"],
            inputs={},
            outputs="Any output.",
            reference_outputs=None,
            technique_configs={"not_contains": {"text": 123}},
        )
        assert metrics["not_contains"]["passed"] is False
        assert metrics["not_contains"]["comment"] == "No forbidden phrases configured."

    @pytest.mark.asyncio
    async def test_contains_and_not_contains_coexist_with_independent_results(self):
        # Same output graded by both: contains passes on the required phrase while
        # not_contains fails on the forbidden one, so the case result reflects both.
        metrics = await self.registry.evaluate(
            ["contains", "not_contains"],
            inputs={},
            outputs="You can use our service, or try Acme instead.",
            reference_outputs={"value": "our service"},
            technique_configs={"not_contains": {"phrases": ["Acme"]}},
        )
        assert set(metrics) == {"contains", "not_contains"}
        assert metrics["contains"]["passed"] is True
        assert metrics["not_contains"]["passed"] is False
        assert "Acme" in metrics["not_contains"]["comment"]


# Synthetic trace fixture with generic placeholder values (not tied to any workflow).
def _agent_trace(*, tool_name="lookup_tool", tool_args=None, tool_result="sample tool result", route="true", action_status="success"):
    return {
        "output": "Sample agent response.",
        "state": {
            "input": {"message": "Sample user question?"},
            "errors": [],
            "nodeExecutionStatus": {
                "agent1": {
                    "name": "Sample Agent",
                    "type": "agentNode",
                    "input": {"query": "sample query"},
                    "output": {
                        "message": "Sample agent response.",
                        "steps": [],
                        "tools_used": [
                            {
                                "tool_name": tool_name,
                                "args": tool_args or {"topic": "sample"},
                                "result": tool_result,
                            }
                        ],
                    },
                    "status": "success",
                    "error": None,
                },
                "kb1": {
                    "name": "Sample Knowledge Node",
                    "type": "knowledgeBaseNode",
                    "input": {"query": "sample query"},
                    "output": "Sample retrieved content.",
                    "status": "success",
                    "error": None,
                },
                "router1": {
                    "name": "Sample Router",
                    "type": "routerNode",
                    "input": {},
                    "output": {"route": route, "next_nodes": []},
                    "status": "success",
                    "error": None,
                },
                "action1": {
                    "name": "Sample Action Node",
                    "type": "zendeskTicketNode",
                    "input": {},
                    "output": {"status": 201, "data": {"id": 1}},
                    "status": action_status,
                    "error": None if action_status == "success" else "action failed",
                },
            },
        },
        "tool_events": [
            {
                "agent_id": "agent1",
                "tool_id": f"node_{tool_name}",
                "tool_name": tool_name,
                "arguments": tool_args or {"topic": "sample"},
                "result": tool_result,
                "status": "succeeded",
            }
        ],
        "token_usage": {},
        "cost_usd": None,
    }


def _agent_workflow():
    """Workflow catalogue matching _agent_trace: agent1 exposes lookup_tool (called
    in the trace) and other_tool (available but never called). Legacy names resolve
    from this catalogue, so an uncalled tool still maps to its id."""
    return {
        "id": "wf1",
        "nodes": [
            {"id": "agent1", "type": "agentNode", "data": {"name": "Sample Agent"}},
            {"id": "node_lookup_tool", "type": "toolNode", "data": {"name": "Lookup Tool"}},
            {"id": "node_other_tool", "type": "toolNode", "data": {"name": "Other Tool"}},
        ],
        "edges": [
            {"source": "node_lookup_tool", "target": "agent1", "targetHandle": "tools"},
            {"source": "node_other_tool", "target": "agent1", "targetHandle": "tools"},
        ],
    }


def _multi_agent_trace():
    """Two agents, each calling a different tool — for agent-scoped assertions."""
    return {
        "output": "Sample multi-agent response.",
        "state": {
            "input": {"message": "Sample user question?"},
            "errors": [],
            "nodeExecutionStatus": {
                "analyst": {
                    "name": "Analyst",
                    "type": "agentNode",
                    "input": {},
                    "output": {
                        "message": "Analyst response.",
                        "tools_used": [
                            {"tool_name": "read_homepage", "args": {"url": "https://x.com"}, "result": "Homepage text."}
                        ],
                    },
                    "status": "success",
                    "error": None,
                },
                "strategist": {
                    "name": "Strategist",
                    "type": "agentNode",
                    "input": {},
                    "output": {
                        "message": "Strategist response.",
                        "tools_used": [
                            {"tool_name": "opportunity_playbook", "args": {"query": "saas"}, "result": "Playbook text."}
                        ],
                    },
                    "status": "success",
                    "error": None,
                },
            },
        },
        "tool_events": [
            {"agent_id": "analyst", "tool_id": "node_read_homepage", "tool_name": "read_homepage",
             "arguments": {"url": "https://x.com"}, "result": "Homepage text.", "status": "succeeded"},
            {"agent_id": "strategist", "tool_id": "node_opportunity_playbook", "tool_name": "opportunity_playbook",
             "arguments": {"query": "saas"}, "result": "Playbook text.", "status": "succeeded"},
        ],
        "token_usage": {},
        "cost_usd": None,
    }


class TestToolUsageMultiAgent:
    def setup_method(self):
        self.registry = SimpleEvaluatorRegistry()

    async def _tool_used(self, rule):
        rule.setdefault("id", "r1")
        metrics = await self.registry.evaluate(
            ["tool_used"],
            inputs={},
            outputs="",
            reference_outputs=None,
            execution_trace=_multi_agent_trace(),
            technique_configs={"tool_used": {"rules": [rule]}},
        )
        return metrics["tool_used"]

    @pytest.mark.asyncio
    async def test_tool_scoped_to_owning_agent_passes(self):
        result = await self._tool_used(
            {"agent_id": "analyst", "tool_ids": ["node_read_homepage"], "operator": "all"}
        )
        assert result["passed"] is True

    @pytest.mark.asyncio
    async def test_tool_scoped_to_other_agent_fails(self):
        result = await self._tool_used(
            {"agent_id": "strategist", "tool_ids": ["node_read_homepage"], "operator": "all"}
        )
        assert result["passed"] is False

    @pytest.mark.asyncio
    async def test_each_agent_matches_its_own_tool(self):
        analyst = await self._tool_used(
            {"agent_id": "analyst", "tool_ids": ["node_read_homepage"], "operator": "all"}
        )
        strategist = await self._tool_used(
            {"agent_id": "strategist", "tool_ids": ["node_opportunity_playbook"], "operator": "all"}
        )
        assert analyst["passed"] is True
        assert strategist["passed"] is True

    @pytest.mark.asyncio
    async def test_forbidden_tool_not_called_by_any_agent_passes(self):
        result = await self._tool_used({"tool_ids": ["node_escalate"], "operator": "none"})
        assert result["passed"] is True

    @pytest.mark.asyncio
    async def test_forbidden_tool_scoped_to_agent_that_did_not_call_it_passes(self):
        result = await self._tool_used(
            {"agent_id": "strategist", "tool_ids": ["node_read_homepage"], "operator": "none"}
        )
        assert result["passed"] is True

    @pytest.mark.asyncio
    async def test_expected_args_and_result_together(self):
        result = await self._tool_used(
            {
                "agent_id": "analyst",
                "tool_ids": ["node_read_homepage"],
                "operator": "all",
                "per_tool": {
                    "node_read_homepage": {
                        "expected_args": {"url": "https://x.com"},
                        "result_not_empty": True,
                    }
                },
            }
        )
        assert result["passed"] is True


class TestEvaluatorFailureVisibility:
    @pytest.mark.asyncio
    async def test_evaluator_exception_becomes_failed_metric(self):
        registry = SimpleEvaluatorRegistry()

        async def _boom(**_kwargs):
            raise RuntimeError("secret-internal-detail")

        registry._evaluators["exact_match"] = _boom
        metrics = await registry.evaluate(
            ["exact_match", "no_errors"],
            inputs={},
            outputs="x",
            reference_outputs="x",
            execution_trace=_agent_trace(),
        )
        # The broken evaluator surfaces as a failed metric, not a missing one.
        assert metrics["exact_match"]["passed"] is False
        comment = metrics["exact_match"]["comment"] or ""
        # The raw exception is not leaked into the user-facing comment.
        assert "secret-internal-detail" not in comment
        assert "server logs" in comment.lower()
        # Other evaluators are unaffected.
        assert "no_errors" in metrics


class TestEnrichedContext:
    def test_exposes_node_input(self):
        ctx = _build_grading_context(_agent_trace())
        assert ctx["nodes"]["agent1"]["input"] == {"query": "sample query"}

    def test_exposes_tool_calls(self):
        ctx = _build_grading_context(_agent_trace(tool_name="other_tool"))
        assert len(ctx["tools"]) == 1
        assert ctx["tools"][0]["name"] == "other_tool"
        assert ctx["tools"][0]["node"] == "agent1"

    def test_exposes_retrievals(self):
        ctx = _build_grading_context(_agent_trace())
        kb = [r for r in ctx["retrievals"] if r["node"] == "kb1"]
        assert kb and kb[0]["results"] == "Sample retrieved content."


class TestProcessCheckEvaluators:
    def setup_method(self):
        self.registry = SimpleEvaluatorRegistry()

    async def _tool_used(self, trace, rule):
        rule.setdefault("id", "r1")
        metrics = await self.registry.evaluate(
            ["tool_used"],
            inputs={},
            outputs="",
            reference_outputs=None,
            execution_trace=trace,
            technique_configs={"tool_used": {"rules": [rule]}},
        )
        return metrics["tool_used"]

    @pytest.mark.asyncio
    async def test_tool_used_passes_for_expected_tool(self):
        result = await self._tool_used(
            _agent_trace(tool_name="lookup_tool"),
            {"tool_ids": ["node_lookup_tool"], "operator": "all"},
        )
        assert result["passed"] is True

    @pytest.mark.asyncio
    async def test_tool_used_fails_for_missing_tool(self):
        result = await self._tool_used(
            _agent_trace(tool_name="lookup_tool"),
            {"tool_ids": ["node_other_tool"], "operator": "all"},
        )
        assert result["passed"] is False

    @pytest.mark.asyncio
    async def test_tool_used_none_fails_when_tool_was_called(self):
        result = await self._tool_used(
            _agent_trace(tool_name="lookup_tool"),
            {"tool_ids": ["node_lookup_tool"], "operator": "none"},
        )
        assert result["passed"] is False

    @pytest.mark.asyncio
    async def test_tool_used_none_passes_when_tool_was_not_called(self):
        result = await self._tool_used(
            _agent_trace(tool_name="lookup_tool"),
            {"tool_ids": ["node_other_tool"], "operator": "none"},
        )
        assert result["passed"] is True

    @pytest.mark.asyncio
    async def test_tool_used_with_expected_args(self):
        result = await self._tool_used(
            _agent_trace(tool_name="notify_tool", tool_args={"priority": "high"}),
            {"tool_ids": ["node_notify_tool"], "operator": "all",
             "per_tool": {"node_notify_tool": {"expected_args": {"priority": "high"}}}},
        )
        assert result["passed"] is True

    @pytest.mark.asyncio
    async def test_tool_used_fails_on_wrong_args(self):
        result = await self._tool_used(
            _agent_trace(tool_name="notify_tool", tool_args={"priority": "low"}),
            {"tool_ids": ["node_notify_tool"], "operator": "all",
             "per_tool": {"node_notify_tool": {"expected_args": {"priority": "high"}}}},
        )
        assert result["passed"] is False

    @pytest.mark.asyncio
    async def test_tool_used_scoped_to_node_id_passes(self):
        metrics = await self.registry.evaluate(
            ["tool_used"],
            inputs={},
            outputs="",
            reference_outputs=None,
            execution_trace=_agent_trace(tool_name="lookup_tool"),
            technique_configs={"tool_used": {"tool": "lookup_tool", "node": "agent1"}},
            workflow=_agent_workflow(),
        )
        assert metrics["tool_used"]["passed"] is True

    @pytest.mark.asyncio
    async def test_tool_used_scoped_to_node_name_passes(self):
        metrics = await self.registry.evaluate(
            ["tool_used"],
            inputs={},
            outputs="",
            reference_outputs=None,
            execution_trace=_agent_trace(tool_name="lookup_tool"),
            technique_configs={"tool_used": {"tool": "lookup_tool", "node": "Sample Agent"}},
            workflow=_agent_workflow(),
        )
        assert metrics["tool_used"]["passed"] is True

    @pytest.mark.asyncio
    async def test_tool_used_scoped_required_tool_not_used_fails(self):
        # other_tool is available to agent1 but never called; the scoped failure names the node.
        metrics = await self.registry.evaluate(
            ["tool_used"],
            inputs={},
            outputs="",
            reference_outputs=None,
            execution_trace=_agent_trace(tool_name="lookup_tool"),
            technique_configs={"tool_used": {"tool": "other_tool", "node": "agent1"}},
            workflow=_agent_workflow(),
        )
        assert metrics["tool_used"]["passed"] is False
        assert "by node" in (metrics["tool_used"]["comment"] or "")

    @pytest.mark.asyncio
    async def test_tool_used_must_not_use_uncalled_tool_passes(self):
        # Regression: a "must not use" rule for a tool that was correctly never called
        # must resolve from the workflow catalogue (not observed calls) and PASS,
        # instead of erroring because the uncalled tool's name can't be resolved.
        metrics = await self.registry.evaluate(
            ["tool_used"],
            inputs={},
            outputs="",
            reference_outputs=None,
            execution_trace=_agent_trace(tool_name="lookup_tool"),
            technique_configs={"tool_used": {"tool": "other_tool", "should_call": False}},
            workflow=_agent_workflow(),
        )
        assert metrics["tool_used"]["passed"] is True

    @pytest.mark.asyncio
    async def test_tool_used_result_not_empty_passes_with_real_result(self):
        metrics = await self.registry.evaluate(
            ["tool_used"],
            inputs={},
            outputs="",
            reference_outputs=None,
            execution_trace=_agent_trace(tool_name="lookup_tool", tool_result="useful content"),
            technique_configs={"tool_used": {"tool": "lookup_tool", "result_not_empty": True}},
            workflow=_agent_workflow(),
        )
        assert metrics["tool_used"]["passed"] is True

    @pytest.mark.asyncio
    async def test_tool_used_result_not_empty_fails_on_no_results_sentinel(self):
        metrics = await self.registry.evaluate(
            ["tool_used"],
            inputs={},
            outputs="",
            reference_outputs=None,
            execution_trace=_agent_trace(tool_name="lookup_tool", tool_result="No results found."),
            technique_configs={"tool_used": {"tool": "lookup_tool", "result_not_empty": True}},
            workflow=_agent_workflow(),
        )
        assert metrics["tool_used"]["passed"] is False
        assert "result" in (metrics["tool_used"]["comment"] or "")

    @pytest.mark.asyncio
    async def test_tool_used_result_not_empty_fails_on_blank_result(self):
        metrics = await self.registry.evaluate(
            ["tool_used"],
            inputs={},
            outputs="",
            reference_outputs=None,
            execution_trace=_agent_trace(tool_name="lookup_tool", tool_result=""),
            technique_configs={"tool_used": {"tool": "lookup_tool", "result_not_empty": True}},
            workflow=_agent_workflow(),
        )
        assert metrics["tool_used"]["passed"] is False

    @pytest.mark.asyncio
    async def test_tool_used_result_assertion_honest_fail_when_trace_lacks_results(self):
        metrics = await self.registry.evaluate(
            ["tool_used"],
            inputs={},
            outputs="",
            reference_outputs=None,
            execution_trace=_agent_trace(tool_name="lookup_tool", tool_result=None),
            technique_configs={"tool_used": {"tool": "lookup_tool", "result_not_empty": True}},
            workflow=_agent_workflow(),
        )
        assert metrics["tool_used"]["passed"] is False
        assert "does not record" in (metrics["tool_used"]["comment"] or "")

    @pytest.mark.asyncio
    async def test_tool_used_result_not_empty_fails_on_structurally_empty_result(self):
        metrics = await self.registry.evaluate(
            ["tool_used"],
            inputs={},
            outputs="",
            reference_outputs=None,
            execution_trace=_agent_trace(tool_name="lookup_tool", tool_result=[]),
            technique_configs={"tool_used": {"tool": "lookup_tool", "result_not_empty": True}},
            workflow=_agent_workflow(),
        )
        assert metrics["tool_used"]["passed"] is False

    @pytest.mark.asyncio
    async def test_tool_used_result_contains(self):
        trace = _agent_trace(tool_name="lookup_tool", tool_result="policy: remote work allowed")
        passing = await self.registry.evaluate(
            ["tool_used"],
            inputs={},
            outputs="",
            reference_outputs=None,
            execution_trace=trace,
            technique_configs={"tool_used": {"tool": "lookup_tool", "result_contains": "remote work"}},
            workflow=_agent_workflow(),
        )
        failing = await self.registry.evaluate(
            ["tool_used"],
            inputs={},
            outputs="",
            reference_outputs=None,
            execution_trace=trace,
            technique_configs={"tool_used": {"tool": "lookup_tool", "result_contains": "vacation days"}},
            workflow=_agent_workflow(),
        )
        assert passing["tool_used"]["passed"] is True
        assert failing["tool_used"]["passed"] is False

    @pytest.mark.asyncio
    async def test_route_taken(self):
        metrics = await self.registry.evaluate(
            ["route_taken"],
            inputs={},
            outputs="",
            reference_outputs=None,
            execution_trace=_agent_trace(route="true"),
            technique_configs={"route_taken": {"expected": "true"}},
        )
        assert metrics["route_taken"]["passed"] is True

    @pytest.mark.asyncio
    async def test_route_taken_fails_on_other_branch(self):
        metrics = await self.registry.evaluate(
            ["route_taken"],
            inputs={},
            outputs="",
            reference_outputs=None,
            execution_trace=_agent_trace(route="false"),
            technique_configs={"route_taken": {"expected": "true"}},
        )
        assert metrics["route_taken"]["passed"] is False

    @pytest.mark.asyncio
    async def test_action_taken_passes_when_node_fired(self):
        metrics = await self.registry.evaluate(
            ["action_taken"],
            inputs={},
            outputs="",
            reference_outputs=None,
            execution_trace=_agent_trace(action_status="success"),
            technique_configs={"action_taken": {"node_type": "zendeskTicketNode"}},
        )
        assert metrics["action_taken"]["passed"] is True

    @pytest.mark.asyncio
    async def test_action_taken_fails_when_node_errored(self):
        metrics = await self.registry.evaluate(
            ["action_taken"],
            inputs={},
            outputs="",
            reference_outputs=None,
            execution_trace=_agent_trace(action_status="failed"),
            technique_configs={"action_taken": {"node_type": "zendeskTicketNode"}},
        )
        assert metrics["action_taken"]["passed"] is False

    @pytest.mark.asyncio
    async def test_route_taken_requires_expected(self):
        metrics = await self.registry.evaluate(
            ["route_taken"],
            inputs={},
            outputs="",
            reference_outputs={"value": "an unrelated answer"},
            execution_trace=_agent_trace(route="true"),
            technique_configs={},
        )
        assert metrics["route_taken"]["passed"] is False
        assert "expected route" in metrics["route_taken"]["comment"].lower()

    @pytest.mark.asyncio
    async def test_action_taken_requires_config(self):
        metrics = await self.registry.evaluate(
            ["action_taken"],
            inputs={},
            outputs="",
            reference_outputs=None,
            execution_trace=_agent_trace(),
            technique_configs={},
        )
        assert metrics["action_taken"]["passed"] is False
        assert "configured" in metrics["action_taken"]["comment"].lower()


class TestLlmJudge:
    def setup_method(self):
        self.registry = SimpleEvaluatorRegistry()

    @pytest.mark.asyncio
    async def test_requires_a_rubric(self):
        metrics = await self.registry.evaluate(
            ["llm_judge"],
            inputs={},
            outputs="Hello there",
            reference_outputs=None,
        )
        assert metrics["llm_judge"]["passed"] is False
        assert "rubric" in metrics["llm_judge"]["comment"].lower()

    @pytest.mark.asyncio
    async def test_passes_above_threshold(self):
        async def fake_judge(*, system_prompt, user_content, provider_id=None):
            return 0.8, "professional and complete"

        self.registry._invoke_json_judge = fake_judge
        metrics = await self.registry.evaluate(
            ["llm_judge"],
            inputs={},
            outputs="A polite, complete reply.",
            reference_outputs=None,
            technique_configs={"llm_judge": {"rubric": "Is the reply professional?", "min_score": 0.5}},
        )
        assert metrics["llm_judge"]["passed"] is True
        assert metrics["llm_judge"]["score"] == 0.8

    @pytest.mark.asyncio
    async def test_fails_below_threshold(self):
        async def fake_judge(*, system_prompt, user_content, provider_id=None):
            return 0.3, "curt"

        self.registry._invoke_json_judge = fake_judge
        metrics = await self.registry.evaluate(
            ["llm_judge"],
            inputs={},
            outputs="No.",
            reference_outputs=None,
            technique_configs={"llm_judge": {"rubric": "Is the reply professional?", "min_score": 0.5}},
        )
        assert metrics["llm_judge"]["passed"] is False

    @pytest.mark.asyncio
    async def test_source_field_feeds_kb_content_to_judge(self):
        captured = {}

        async def fake_judge(*, system_prompt, user_content, provider_id=None):
            captured["user_content"] = user_content
            return 1.0, "grounded"

        self.registry._invoke_json_judge = fake_judge
        metrics = await self.registry.evaluate(
            ["llm_judge"],
            inputs={},
            outputs="Sample answer.",
            reference_outputs=None,
            execution_trace=_agent_trace(),
            technique_configs={
                "llm_judge": {
                    "rubric": "Fail if the answer contains claims not supported by SOURCE.",
                    "source_field": "trace.retrievals",
                }
            },
        )
        assert metrics["llm_judge"]["passed"] is True
        assert "SOURCE:" in captured["user_content"]
        assert "Sample retrieved content" in captured["user_content"]

    @pytest.mark.asyncio
    async def test_no_source_block_when_unconfigured(self):
        captured = {}

        async def fake_judge(*, system_prompt, user_content, provider_id=None):
            captured["user_content"] = user_content
            return 1.0, "fine"

        self.registry._invoke_json_judge = fake_judge
        await self.registry.evaluate(
            ["llm_judge"],
            inputs={},
            outputs="Hello",
            reference_outputs=None,
            execution_trace=_agent_trace(),
            technique_configs={"llm_judge": {"rubric": "Is the reply polite?"}},
        )
        assert "SOURCE:" not in captured["user_content"]

    @pytest.mark.asyncio
    async def test_unresolved_source_field_adds_no_source(self):
        captured = {}

        async def fake_judge(*, system_prompt, user_content, provider_id=None):
            captured["user_content"] = user_content
            return 1.0, "ok"

        self.registry._invoke_json_judge = fake_judge
        await self.registry.evaluate(
            ["llm_judge"],
            inputs={},
            outputs="Hello",
            reference_outputs=None,
            execution_trace=_agent_trace(),
            technique_configs={
                "llm_judge": {"rubric": "Grounded?", "source_field": "trace.session.does_not_exist"}
            },
        )
        assert "SOURCE:" not in captured["user_content"]
        assert "does_not_exist" not in captured["user_content"]
