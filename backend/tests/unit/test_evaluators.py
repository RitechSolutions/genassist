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
        "token_usage": {},
        "cost_usd": None,
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
        "token_usage": {},
        "cost_usd": None,
    }


class TestToolUsageMultiAgent:
    def setup_method(self):
        self.registry = SimpleEvaluatorRegistry()

    async def _tool_used(self, config):
        metrics = await self.registry.evaluate(
            ["tool_used"],
            inputs={},
            outputs="",
            reference_outputs=None,
            execution_trace=_multi_agent_trace(),
            technique_configs={"tool_used": config},
        )
        return metrics["tool_used"]

    @pytest.mark.asyncio
    async def test_tool_scoped_to_owning_agent_passes(self):
        result = await self._tool_used({"tool": "read_homepage", "node": "Analyst"})
        assert result["passed"] is True

    @pytest.mark.asyncio
    async def test_tool_scoped_to_other_agent_fails(self):
        result = await self._tool_used({"tool": "read_homepage", "node": "Strategist"})
        assert result["passed"] is False
        assert "by node" in (result["comment"] or "")

    @pytest.mark.asyncio
    async def test_each_agent_matches_its_own_tool(self):
        analyst = await self._tool_used({"tool": "read_homepage", "node": "Analyst"})
        strategist = await self._tool_used({"tool": "opportunity_playbook", "node": "Strategist"})
        assert analyst["passed"] is True
        assert strategist["passed"] is True

    @pytest.mark.asyncio
    async def test_forbidden_tool_not_called_by_any_agent_passes(self):
        result = await self._tool_used({"tool": "escalate", "should_call": False})
        assert result["passed"] is True

    @pytest.mark.asyncio
    async def test_forbidden_tool_scoped_to_agent_that_did_not_call_it_passes(self):
        result = await self._tool_used(
            {"tool": "read_homepage", "should_call": False, "node": "Strategist"}
        )
        assert result["passed"] is True

    @pytest.mark.asyncio
    async def test_expected_args_and_result_together(self):
        result = await self._tool_used(
            {
                "tool": "read_homepage",
                "node": "Analyst",
                "expected_args": {"url": "https://x.com"},
                "result_not_empty": True,
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

    @pytest.mark.asyncio
    async def test_tool_used_passes_for_expected_tool(self):
        metrics = await self.registry.evaluate(
            ["tool_used"],
            inputs={},
            outputs="",
            reference_outputs=None,
            execution_trace=_agent_trace(tool_name="lookup_tool"),
            technique_configs={"tool_used": {"tool": "lookup_tool"}},
        )
        assert metrics["tool_used"]["passed"] is True

    @pytest.mark.asyncio
    async def test_tool_used_fails_for_missing_tool(self):
        metrics = await self.registry.evaluate(
            ["tool_used"],
            inputs={},
            outputs="",
            reference_outputs=None,
            execution_trace=_agent_trace(tool_name="lookup_tool"),
            technique_configs={"tool_used": {"tool": "other_tool"}},
        )
        assert metrics["tool_used"]["passed"] is False

    @pytest.mark.asyncio
    async def test_tool_used_should_call_false_fails_when_tool_was_called(self):
        metrics = await self.registry.evaluate(
            ["tool_used"],
            inputs={},
            outputs="",
            reference_outputs=None,
            execution_trace=_agent_trace(tool_name="lookup_tool"),
            technique_configs={"tool_used": {"tool": "lookup_tool", "should_call": False}},
        )
        assert metrics["tool_used"]["passed"] is False

    @pytest.mark.asyncio
    async def test_tool_used_should_call_false_passes_when_tool_was_not_called(self):
        metrics = await self.registry.evaluate(
            ["tool_used"],
            inputs={},
            outputs="",
            reference_outputs=None,
            execution_trace=_agent_trace(tool_name="lookup_tool"),
            technique_configs={"tool_used": {"tool": "other_tool", "should_call": False}},
        )
        assert metrics["tool_used"]["passed"] is True

    @pytest.mark.asyncio
    async def test_tool_used_with_expected_args(self):
        metrics = await self.registry.evaluate(
            ["tool_used"],
            inputs={},
            outputs="",
            reference_outputs=None,
            execution_trace=_agent_trace(tool_name="notify_tool", tool_args={"priority": "high"}),
            technique_configs={
                "tool_used": {"tool": "notify_tool", "expected_args": {"priority": "high"}}
            },
        )
        assert metrics["tool_used"]["passed"] is True

    @pytest.mark.asyncio
    async def test_tool_used_fails_on_wrong_args(self):
        metrics = await self.registry.evaluate(
            ["tool_used"],
            inputs={},
            outputs="",
            reference_outputs=None,
            execution_trace=_agent_trace(tool_name="notify_tool", tool_args={"priority": "low"}),
            technique_configs={
                "tool_used": {"tool": "notify_tool", "expected_args": {"priority": "high"}}
            },
        )
        assert metrics["tool_used"]["passed"] is False

    @pytest.mark.asyncio
    async def test_tool_used_scoped_to_node_id_passes(self):
        metrics = await self.registry.evaluate(
            ["tool_used"],
            inputs={},
            outputs="",
            reference_outputs=None,
            execution_trace=_agent_trace(tool_name="lookup_tool"),
            technique_configs={"tool_used": {"tool": "lookup_tool", "node": "agent1"}},
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
        )
        assert metrics["tool_used"]["passed"] is True

    @pytest.mark.asyncio
    async def test_tool_used_scoped_to_other_node_fails(self):
        metrics = await self.registry.evaluate(
            ["tool_used"],
            inputs={},
            outputs="",
            reference_outputs=None,
            execution_trace=_agent_trace(tool_name="lookup_tool"),
            technique_configs={"tool_used": {"tool": "lookup_tool", "node": "kb1"}},
        )
        assert metrics["tool_used"]["passed"] is False
        assert "by node" in (metrics["tool_used"]["comment"] or "")

    @pytest.mark.asyncio
    async def test_tool_used_result_not_empty_passes_with_real_result(self):
        metrics = await self.registry.evaluate(
            ["tool_used"],
            inputs={},
            outputs="",
            reference_outputs=None,
            execution_trace=_agent_trace(tool_name="lookup_tool", tool_result="useful content"),
            technique_configs={"tool_used": {"tool": "lookup_tool", "result_not_empty": True}},
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
        )
        failing = await self.registry.evaluate(
            ["tool_used"],
            inputs={},
            outputs="",
            reference_outputs=None,
            execution_trace=trace,
            technique_configs={"tool_used": {"tool": "lookup_tool", "result_contains": "vacation days"}},
        )
        assert passing["tool_used"]["passed"] is True
        assert failing["tool_used"]["passed"] is False

    @pytest.mark.asyncio
    async def test_tool_used_should_call_false_scoped_to_other_node_passes(self):
        metrics = await self.registry.evaluate(
            ["tool_used"],
            inputs={},
            outputs="",
            reference_outputs=None,
            execution_trace=_agent_trace(tool_name="lookup_tool"),
            technique_configs={
                "tool_used": {"tool": "lookup_tool", "node": "kb1", "should_call": False}
            },
        )
        assert metrics["tool_used"]["passed"] is True

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
