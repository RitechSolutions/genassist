"""Unit tests for trace-aware grading (process evaluation)."""

from types import SimpleNamespace

import pytest

import app.services.test_suite as eval_mod
from app.constants import DEFAULT_NLI_MODEL
from app.services.evaluation_nli import (
    EvaluationNLIModel,
    NLIClaimResult,
)
from app.services.test_suite import (
    SimpleEvaluatorRegistry,
    _build_grading_context,
    _is_waiting_for_human,
    _parse_judge_json,
)


class _FakeEmbedder:
    """Embedder stub returning fixed vectors, for provenance scoring tests."""

    def __init__(self, answer_vec, context_vec):
        self.answer_vec = answer_vec
        self.context_vec = context_vec

    async def initialize(self):
        return True

    async def embed_texts(self, texts):  # noqa: ARG002 - order is [answer, context]
        return [self.answer_vec, self.context_vec]


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


class TestHumanInputPauseDetection:
    def test_detects_awaiting_input_output(self):
        assert _is_waiting_for_human(
            {"status": "awaiting_input", "form_schema": {"fields": []}}
        )

    @pytest.mark.parametrize(
        "output",
        [
            None,
            "awaiting_input",
            {},
            {"status": "completed"},
            {"status": "failed"},
        ],
    )
    def test_does_not_misclassify_normal_outputs(self, output):
        assert _is_waiting_for_human(output) is False


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

    def test_retrievals_include_kb_tool_results(self):
        """Retrieval done via an agent tool (not a KB node) still counts as retrieved context."""
        trace = {
            "state": {
                "nodeExecutionStatus": {
                    "agent1": {
                        "type": "agentNode",
                        "name": "Agent",
                        "output": {"tools_used": []},
                        "status": "success",
                    }
                }
            },
            "tool_events": [
                {
                    "tool_id": "kb1",
                    "tool_name": "knowledge_base_for_regions",
                    "result": "Found: refunds within 30 days",
                    "status": "succeeded",
                },
                {
                    "tool_id": "t2",
                    "tool_name": "ticket_creation",
                    "result": "ticket #123 created",
                    "status": "succeeded",
                },
            ],
        }
        ctx = _build_grading_context(trace)
        joined = str(ctx["retrievals"])
        assert "refunds within 30 days" in joined
        assert "ticket #123" not in joined  # a non-retrieval tool is excluded

    def _kb_tool_trace(self, events):
        return {"state": {"nodeExecutionStatus": {}}, "tool_events": events}

    def test_retrieval_ignores_unsuccessful_calls(self):
        """A paused or failed retrieval carries no usable context and is skipped."""
        trace = self._kb_tool_trace([
            {"tool_id": "kb1", "tool_name": "knowledge_base", "result": "paused text", "status": "paused"},
            {"tool_id": "kb1", "tool_name": "knowledge_base", "result": "failed text", "status": "failed"},
        ])
        assert _build_grading_context(trace)["retrievals"] == []

    def test_retrieval_dedupes_repeated_content(self):
        """The same lookup made twice contributes one retrieval; a distinct lookup is kept."""
        trace = self._kb_tool_trace([
            {"tool_id": "kb1", "tool_name": "knowledge_base", "result": "policy A", "status": "succeeded"},
            {"tool_id": "kb1", "tool_name": "knowledge_base", "result": "policy A", "status": "succeeded"},
            {"tool_id": "kb1", "tool_name": "knowledge_base", "result": "policy B", "status": "succeeded"},
        ])
        retrievals = _build_grading_context(trace)["retrievals"]
        assert len(retrievals) == 2

    def test_retrieval_skips_no_result_sentinels(self):
        """A 'no results found' sentinel is not treated as retrieved context."""
        trace = self._kb_tool_trace([
            {"tool_id": "kb1", "tool_name": "knowledge_base", "result": "No relevant information found.", "status": "succeeded"},
            {"tool_id": "kb1", "tool_name": "knowledge_base", "result": [], "status": "succeeded"},
        ])
        assert _build_grading_context(trace)["retrievals"] == []

    def test_retrieval_recognizes_knowledge_tool_node_by_type(self):
        """A tool backed by a knowledgeToolNode counts as retrieval even if unnamed."""
        trace = {
            "state": {
                "nodeExecutionStatus": {
                    "kt1": {"type": "knowledgeToolNode", "name": "Docs", "status": "success"}
                }
            },
            "tool_events": [
                {"tool_id": "kt1", "tool_name": "docs", "result": "Grounding passage.", "status": "succeeded"}
            ],
        }
        assert "Grounding passage." in str(_build_grading_context(trace)["retrievals"])

    def _kb_node_trace(self, output, status="success", error=None):
        return {
            "state": {
                "nodeExecutionStatus": {
                    "kb": {
                        "type": "knowledgeBaseNode",
                        "name": "KB",
                        "output": output,
                        "status": status,
                        "error": error,
                    }
                }
            }
        }

    def test_kb_node_result_skips_sentinel(self):
        """A KB node returning a no-result sentinel is not grounding context."""
        trace = self._kb_node_trace("No relevant information found.")
        assert _build_grading_context(trace)["retrievals"] == []

    def test_kb_node_result_skips_failed_node(self):
        """A KB node that failed is not treated as valid retrieved context."""
        trace = self._kb_node_trace("some passage", status="failed")
        assert _build_grading_context(trace)["retrievals"] == []

    def test_kb_node_and_tool_dedupe_identical_content(self):
        """The same passage surfaced by a KB node and a KB tool is counted once."""
        trace = {
            "state": {
                "nodeExecutionStatus": {
                    "kb": {"type": "knowledgeBaseNode", "name": "KB", "output": "shared passage", "status": "success"}
                }
            },
            "tool_events": [
                {"tool_id": "kbtool", "tool_name": "knowledge_base", "result": "shared passage", "status": "succeeded"}
            ],
        }
        assert len(_build_grading_context(trace)["retrievals"]) == 1


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
        m = metrics["field_equals"]
        assert m["expected"] == "high"
        assert m["actual"] == "low"

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

    @pytest.mark.asyncio
    async def test_no_errors_comment_names_failing_node(self):
        trace = _sample_trace(node_error="ThreadScopedRAG: NoneType has no len()")
        metrics = await self.registry.evaluate(
            ["no_errors"],
            inputs={},
            outputs="ok",
            reference_outputs=None,
            execution_trace=trace,
        )
        m = metrics["no_errors"]
        assert m["passed"] is False
        assert "Knowledge Query" in m["comment"]
        assert "NoneType has no len()" in m["comment"]

    @pytest.mark.asyncio
    async def test_no_errors_comment_includes_state_level_errors(self):
        trace = _sample_trace()
        trace["state"]["errors"] = ["upstream provider unavailable"]
        metrics = await self.registry.evaluate(
            ["no_errors"],
            inputs={},
            outputs="ok",
            reference_outputs=None,
            execution_trace=trace,
        )
        m = metrics["no_errors"]
        assert m["passed"] is False
        assert "upstream provider unavailable" in m["comment"]

    @pytest.mark.asyncio
    async def test_no_errors_renders_engine_error_dicts_readably(self):
        """The engine's canonical {'message','type','timestamp'} error dicts show
        only the message, with node ids swapped for their display labels."""
        trace = _sample_trace()
        trace["state"]["errors"] = [
            {
                "message": "Node n2: retrieval failed",
                "type": "node_execution",
                "timestamp": "2026-01-01T00:00:00+00:00",
            }
        ]
        metrics = await self.registry.evaluate(
            ["no_errors"],
            inputs={},
            outputs="ok",
            reference_outputs=None,
            execution_trace=trace,
        )
        m = metrics["no_errors"]
        assert m["passed"] is False
        assert "Node Knowledge Query: retrieval failed" in m["comment"]
        assert "timestamp" not in m["comment"]
        assert "{" not in m["comment"]

    @pytest.mark.asyncio
    async def test_json_match_failure_names_differing_fields(self):
        metrics = await self.registry.evaluate(
            ["json_match"],
            inputs={},
            outputs={"amount": 450, "notes": "extra"},
            reference_outputs={"amount": 500, "currency": "EUR"},
        )
        m = metrics["json_match"]
        assert m["passed"] is False
        comment = m["comment"]
        assert "'amount'" in comment
        assert "500" in comment and "450" in comment
        assert "missing field 'currency'" in comment
        assert "unexpected field 'notes'" in comment

    @pytest.mark.asyncio
    async def test_json_match_pass_has_no_comment(self):
        metrics = await self.registry.evaluate(
            ["json_match"],
            inputs={},
            outputs={"amount": 500},
            reference_outputs={"amount": 500},
        )
        assert metrics["json_match"]["passed"] is True
        assert metrics["json_match"]["comment"] is None


class TestHumanInputPauseEvaluation:
    @pytest.mark.asyncio
    async def test_output_checks_are_not_evaluated_but_process_checks_continue(self):
        registry = SimpleEvaluatorRegistry()
        paused_output = {
            "status": "awaiting_input",
            "form_schema": {"fields": [{"name": "employee_id"}]},
        }
        trace = {
            "output": paused_output,
            "state": {
                "errors": [],
                "nodeExecutionStatus": {
                    "router": {
                        "type": "routerNode",
                        "name": "Request Router",
                        "status": "success",
                        "output": {"route": "needs_employee"},
                    },
                    "action": {
                        "type": "apiToolNode",
                        "name": "Prepare Request",
                        "status": "success",
                        "output": {"prepared": True},
                    },
                },
            },
        }
        output_checks = [
            "exact_match",
            "contains",
            "not_contains",
            "json_match",
            "field_equals",
            "nli_eval",
            "provenance_eval",
            "llm_judge",
        ]
        metrics = await registry.evaluate(
            [*output_checks, "no_errors", "route_taken", "action_taken"],
            inputs={"message": "Check my allowance"},
            outputs=paused_output,
            reference_outputs={"value": "Your allowance is £100."},
            execution_trace=trace,
            technique_configs={
                "not_contains": {"text": "forbidden"},
                "route_taken": {
                    "router": "router",
                    "expected": "needs_employee",
                },
                "action_taken": {
                    "node": "action",
                    "should_fire": True,
                },
                "llm_judge": {"rubric": "Be helpful."},
            },
        )

        for technique in output_checks:
            assert metrics[technique]["score"] is None
            assert metrics[technique]["passed"] is False
            assert metrics[technique]["not_evaluated"] is True
            assert metrics[technique]["comment"] == (
                "Not evaluated — waiting for human input."
            )

        assert metrics["no_errors"]["passed"] is True
        assert metrics["route_taken"]["passed"] is True
        assert metrics["action_taken"]["passed"] is True

    @pytest.mark.asyncio
    async def test_field_equals_can_still_check_intermediate_state(self):
        registry = SimpleEvaluatorRegistry()
        metrics = await registry.evaluate(
            ["field_equals"],
            inputs={},
            outputs={"status": "awaiting_input"},
            reference_outputs={"value": "low"},
            execution_trace=_sample_trace(risk_level="low"),
            technique_configs={
                "field_equals": {"field": "trace.session.risk_level"}
            },
        )

        assert metrics["field_equals"]["passed"] is True
        assert metrics["field_equals"].get("not_evaluated") is not True


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


def _two_router_trace(*, first_route="true", second_route="support"):
    """Trace with two routers, for multi-rule route_taken assertions."""
    return {
        "output": "Sample response.",
        "state": {
            "input": {"message": "Sample user question?"},
            "errors": [],
            "nodeExecutionStatus": {
                "router1": {
                    "name": "Sample Router",
                    "type": "routerNode",
                    "input": {},
                    "output": {"route": first_route, "next_nodes": []},
                    "status": "success",
                    "error": None,
                },
                "router2": {
                    "name": "Second Router",
                    "type": "routerNode",
                    "input": {},
                    "output": {"route": second_route, "next_nodes": []},
                    "status": "success",
                    "error": None,
                },
            },
        },
        "tool_events": [],
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
        # other_tool is available to agent1 but never called; the scoped failure
        # names the agent by its display label, not its node id.
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
        comment = metrics["tool_used"]["comment"] or ""
        assert "by agent 'Sample Agent'" in comment
        assert "agent1" not in comment

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

    @pytest.mark.asyncio
    async def test_route_taken_multiple_rules_reports_each(self):
        trace = _two_router_trace(first_route="true", second_route="billing")
        metrics = await self.registry.evaluate(
            ["route_taken"],
            inputs={},
            outputs="",
            reference_outputs=None,
            execution_trace=trace,
            technique_configs={
                "route_taken": {
                    "rules": [
                        {"router": "router1", "expected": "true"},
                        {"router": "router2", "expected": "support"},
                    ]
                }
            },
        )
        m = metrics["route_taken"]
        assert m["passed"] is False
        assert m["score"] == 0.5
        assert len(m["details"]) == 2
        assert m["details"][0]["passed"] is True
        assert m["details"][1]["passed"] is False
        assert "1 of 2" in m["comment"]
        assert "Second Router" in m["comment"]

    @pytest.mark.asyncio
    async def test_route_taken_multiple_rules_all_pass(self):
        trace = _two_router_trace(first_route="true", second_route="support")
        metrics = await self.registry.evaluate(
            ["route_taken"],
            inputs={},
            outputs="",
            reference_outputs=None,
            execution_trace=trace,
            technique_configs={
                "route_taken": {
                    "rules": [
                        {"router": "router1", "expected": "true"},
                        {"router": "router2", "expected": "support"},
                    ]
                }
            },
        )
        m = metrics["route_taken"]
        assert m["passed"] is True
        assert m["score"] == 1.0

    @pytest.mark.asyncio
    async def test_route_taken_missing_router_names_it_from_workflow(self):
        """A rule whose router never ran resolves its display name from the graph,
        never showing the raw node id."""
        metrics = await self.registry.evaluate(
            ["route_taken"],
            inputs={},
            outputs="",
            reference_outputs=None,
            execution_trace=_agent_trace(route="true"),
            technique_configs={
                "route_taken": {
                    "rules": [
                        {
                            "router": "8f2a4b6c-1d2e-4f5a-9b8c-7d6e5f4a3b2c",
                            "expected": "true",
                        }
                    ]
                }
            },
            workflow={
                "id": "wf1",
                "nodes": [
                    {
                        "id": "8f2a4b6c-1d2e-4f5a-9b8c-7d6e5f4a3b2c",
                        "type": "routerNode",
                        "data": {"name": "Escalation Router"},
                    }
                ],
                "edges": [],
            },
        )
        m = metrics["route_taken"]
        assert m["passed"] is False
        assert "Escalation Router" in m["comment"]
        assert "8f2a4b6c" not in m["comment"]

    @pytest.mark.asyncio
    async def test_route_taken_unknown_router_id_never_prints_uuid(self):
        metrics = await self.registry.evaluate(
            ["route_taken"],
            inputs={},
            outputs="",
            reference_outputs=None,
            execution_trace=_agent_trace(route="true"),
            technique_configs={
                "route_taken": {
                    "rules": [
                        {
                            "router": "8f2a4b6c-1d2e-4f5a-9b8c-7d6e5f4a3b2c",
                            "expected": "true",
                        }
                    ]
                }
            },
        )
        m = metrics["route_taken"]
        assert m["passed"] is False
        assert "8f2a4b6c" not in m["comment"]
        assert "unknown node" in m["comment"]

    @pytest.mark.asyncio
    async def test_action_taken_multiple_rules(self):
        """One node must fire (it did) and another must not (it did) — half pass."""
        metrics = await self.registry.evaluate(
            ["action_taken"],
            inputs={},
            outputs="",
            reference_outputs=None,
            execution_trace=_agent_trace(action_status="success"),
            technique_configs={
                "action_taken": {
                    "rules": [
                        {"node": "action1", "should_fire": True},
                        {"node": "action1", "should_fire": False},
                    ]
                }
            },
        )
        m = metrics["action_taken"]
        assert m["passed"] is False
        assert m["score"] == 0.5
        assert len(m["details"]) == 2
        assert "Sample Action Node" in m["comment"]

    @pytest.mark.asyncio
    async def test_action_taken_comment_uses_label_not_id(self):
        metrics = await self.registry.evaluate(
            ["action_taken"],
            inputs={},
            outputs="",
            reference_outputs=None,
            execution_trace=_agent_trace(action_status="failed"),
            technique_configs={"action_taken": {"node": "action1"}},
        )
        m = metrics["action_taken"]
        assert m["passed"] is False
        assert "Sample Action Node" in m["comment"]
        assert "'action1'" not in m["comment"]

    @pytest.mark.asyncio
    async def test_action_taken_names_the_node_that_fired(self):
        """A node_type rule matching several nodes must blame the node that actually
        completed, not whichever candidate happens to come first in the trace."""
        trace = {
            "output": "out",
            "state": {
                "input": {},
                "errors": [],
                "nodeExecutionStatus": {
                    "mail_a": {
                        "name": "Mail A",
                        "type": "emailNode",
                        "output": {},
                        "status": "failed",
                        "error": "smtp down",
                    },
                    "mail_b": {
                        "name": "Mail B",
                        "type": "emailNode",
                        "output": {},
                        "status": "success",
                        "error": None,
                    },
                },
            },
            "tool_events": [],
        }
        metrics = await self.registry.evaluate(
            ["action_taken"],
            inputs={},
            outputs="",
            reference_outputs=None,
            execution_trace=trace,
            technique_configs={"action_taken": {"node_type": "emailNode", "should_fire": False}},
        )
        m = metrics["action_taken"]
        assert m["passed"] is False
        assert "Mail B" in m["comment"]
        assert "Mail A" not in m["comment"]

    @pytest.mark.asyncio
    async def test_route_taken_actual_value_stays_plain(self):
        metrics = await self.registry.evaluate(
            ["route_taken"],
            inputs={},
            outputs="",
            reference_outputs=None,
            execution_trace=_agent_trace(route="false"),
            technique_configs={"route_taken": {"expected": "true"}},
        )
        m = metrics["route_taken"]
        assert m["passed"] is False
        assert m["actual"] == "false"
        assert "'false'" in m["comment"]

    @pytest.mark.asyncio
    async def test_tool_used_forbidden_comment_uses_labels(self):
        metrics = await self.registry.evaluate(
            ["tool_used"],
            inputs={},
            outputs="",
            reference_outputs=None,
            execution_trace=_agent_trace(tool_name="lookup_tool"),
            technique_configs={
                "tool_used": {
                    "rules": [
                        {"id": "r1", "tool_ids": ["node_lookup_tool"], "operator": "none"}
                    ]
                }
            },
            workflow=_agent_workflow(),
        )
        m = metrics["tool_used"]
        assert m["passed"] is False
        assert "Lookup Tool" in m["comment"]
        assert "node_lookup_tool" not in m["comment"]


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
        async def fake_judge(*, system_prompt, user_content, provider_id=None, **_):
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
        async def fake_judge(*, system_prompt, user_content, provider_id=None, **_):
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
    async def test_multiple_rules_report_each(self):
        """Two rubrics grade independently; the metric passes only when all do."""
        async def fake_judge(*, system_prompt, user_content, provider_id=None, **_):
            if "polite" in system_prompt.lower():
                return 0.9, "courteous"
            return 0.2, "misses half the question"

        self.registry._invoke_json_judge = fake_judge
        metrics = await self.registry.evaluate(
            ["llm_judge"],
            inputs={"message": "How do I reset my password and my email?"},
            outputs="Click reset.",
            reference_outputs=None,
            technique_configs={
                "llm_judge": {
                    "rules": [
                        {"label": "Politeness", "rubric": "Is the reply polite?", "min_score": 0.5},
                        {"label": "Completeness", "rubric": "Does it answer everything?", "min_score": 0.5},
                    ]
                }
            },
        )
        m = metrics["llm_judge"]
        assert m["passed"] is False
        assert m["score"] == 0.5
        assert len(m["details"]) == 2
        assert "1 of 2" in m["comment"]
        assert "Completeness" in m["comment"]
        assert m["details"][0]["passed"] is True
        assert m["details"][1]["passed"] is False

    @pytest.mark.asyncio
    async def test_multiple_rules_skip_rule_with_unavailable_source(self):
        """A rule whose grounding source is missing is excluded, not failed."""
        async def fake_judge(*, system_prompt, user_content, provider_id=None, **_):
            return 0.8, "fine"

        self.registry._invoke_json_judge = fake_judge
        metrics = await self.registry.evaluate(
            ["llm_judge"],
            inputs={},
            outputs="Some answer.",
            reference_outputs=None,
            execution_trace={},
            technique_configs={
                "llm_judge": {
                    "rules": [
                        {"label": "Tone", "rubric": "Polite?", "min_score": 0.5, "source_type": "none"},
                        {
                            "label": "Relevance",
                            "rubric": "Sources relevant?",
                            "min_score": 0.5,
                            "source_type": "kb_retrievals",
                        },
                    ]
                }
            },
        )
        m = metrics["llm_judge"]
        assert m["passed"] is True
        assert m["score"] == 1.0
        assert "1 not evaluated" in m["comment"]
        assert m["details"][1]["not_evaluated"] is True

    @pytest.mark.asyncio
    async def test_multiple_rules_error_surfaces_as_evaluator_error(self):
        async def fake_judge(*, system_prompt, user_content, provider_id=None, **_):
            if "polite" in system_prompt.lower():
                return 0.9, "fine"
            return None, "malformed judge output"

        self.registry._invoke_json_judge = fake_judge
        metrics = await self.registry.evaluate(
            ["llm_judge"],
            inputs={},
            outputs="Answer.",
            reference_outputs=None,
            technique_configs={
                "llm_judge": {
                    "rules": [
                        {"label": "Tone", "rubric": "Is it polite?", "min_score": 0.5},
                        {"label": "Broken", "rubric": "Whatever.", "min_score": 0.5},
                    ]
                }
            },
        )
        m = metrics["llm_judge"]
        assert m.get("error") is True
        assert m["passed"] is False
        assert m["score"] is None
        assert "Broken" in m["comment"]

    @pytest.mark.asyncio
    async def test_source_field_feeds_kb_content_to_judge(self):
        captured = {}

        async def fake_judge(*, system_prompt, user_content, provider_id=None, **_):
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

        async def fake_judge(*, system_prompt, user_content, provider_id=None, **_):
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
    async def test_unresolved_selected_source_is_not_evaluated(self):
        called = False

        async def fake_judge(*, system_prompt, user_content, provider_id=None, **_):
            nonlocal called
            called = True
            return 1.0, "ok"

        self.registry._invoke_json_judge = fake_judge
        metrics = await self.registry.evaluate(
            ["llm_judge"],
            inputs={},
            outputs="Hello",
            reference_outputs=None,
            execution_trace=_agent_trace(),
            technique_configs={
                "llm_judge": {"rubric": "Grounded?", "source_field": "trace.session.does_not_exist"}
            },
        )
        assert metrics["llm_judge"].get("not_evaluated") is True
        assert metrics["llm_judge"]["score"] is None
        assert called is False

    @pytest.mark.asyncio
    async def test_explicit_kb_source_preset_feeds_judge(self):
        captured = {}

        async def fake_judge(*, system_prompt, user_content, provider_id=None, **_):
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
                    "rubric": "Use the supplied evidence.",
                    "source_type": "kb_retrievals",
                }
            },
        )
        assert metrics["llm_judge"]["passed"] is True
        assert "Sample retrieved content" in captured["user_content"]

    @pytest.mark.asyncio
    async def test_auto_feeds_user_question_from_inputs(self):
        captured = {}

        async def fake_judge(*, system_prompt, user_content, provider_id=None, **_):
            captured["user_content"] = user_content
            return 1.0, "ok"

        self.registry._invoke_json_judge = fake_judge
        await self.registry.evaluate(
            ["llm_judge"],
            inputs={"message": "How do I pay for parking?"},
            outputs="Tap the app.",
            reference_outputs=None,
            technique_configs={"llm_judge": {"rubric": "Is the reply relevant?"}},
        )
        assert "QUESTION:" in captured["user_content"]
        assert "How do I pay for parking?" in captured["user_content"]

    @pytest.mark.asyncio
    async def test_malformed_judge_output_is_evaluator_error(self):
        async def fake_judge(*, system_prompt, user_content, provider_id=None, **_):
            return None, "LLM judge response could not be parsed"

        self.registry._invoke_json_judge = fake_judge
        metrics = await self.registry.evaluate(
            ["llm_judge"],
            inputs={},
            outputs="Hello",
            reference_outputs=None,
            technique_configs={"llm_judge": {"rubric": "Is the reply polite?"}},
        )
        assert metrics["llm_judge"]["error"] is True
        assert metrics["llm_judge"]["passed"] is False
        assert metrics["llm_judge"]["score"] is None


class TestParseJudgeJson:
    def test_valid_score_and_reason(self):
        score, reason = _parse_judge_json('{"score": 0.8, "reason": "good"}')
        assert score == 0.8
        assert reason == "good"

    def test_missing_score_is_none(self):
        score, reason = _parse_judge_json('{"reason": "no score given"}')
        assert score is None
        assert "score" in reason.lower()

    def test_non_dict_is_none(self):
        score, _ = _parse_judge_json("[1, 2, 3]")
        assert score is None

    def test_unparseable_is_none(self):
        score, _ = _parse_judge_json("not json at all")
        assert score is None

    def test_score_is_clamped(self):
        assert _parse_judge_json('{"score": 5}')[0] == 1.0
        assert _parse_judge_json('{"score": -2}')[0] == 0.0


class TestSemanticEvaluators:
    """Source-aware NLI and Provenance: skip vs fail, model reporting, real embeddings."""

    def setup_method(self):
        self.registry = SimpleEvaluatorRegistry()

    @pytest.mark.asyncio
    async def test_nli_skips_when_no_evidence(self):
        metrics = await self.registry.evaluate(
            ["nli_eval"],
            inputs={},
            outputs="The sky is blue.",
            reference_outputs=None,
            execution_trace={},  # no retrievals available
            technique_configs={"nli_eval": {"evidence_source": "kb_retrievals"}},
        )
        m = metrics["nli_eval"]
        assert m.get("not_evaluated") is True
        assert m["passed"] is False

    @pytest.mark.asyncio
    async def test_nli_uses_model_and_reports_name(self, monkeypatch):
        monkeypatch.setattr(
            eval_mod.evaluation_nli_model,
            "score_evidence",
            lambda answer, evidence, model_name=None: SimpleNamespace(
                entail_score=0.9,
                contradiction_score=0.01,
                verdict="entails",
                model_name="roberta-nli",
                chunks_evaluated=2,
                evidence_truncated=False,
            ),
        )
        metrics = await self.registry.evaluate(
            ["nli_eval"],
            inputs={},
            outputs="Risk is low.",
            reference_outputs="the contract risk is low",
            execution_trace={},
            technique_configs={"nli_eval": {"evidence_source": "expected_output"}},
        )
        m = metrics["nli_eval"]
        assert m["passed"] is True
        assert "model=roberta-nli" in m["comment"]
        assert "Evidence chunks checked: 2" in m["comment"]

    @pytest.mark.asyncio
    async def test_nli_configured_threshold_directly_controls_passing(
        self, monkeypatch
    ):
        monkeypatch.setattr(
            eval_mod.evaluation_nli_model,
            "score_evidence",
            lambda answer, evidence, model_name=None: SimpleNamespace(
                entail_score=0.45,
                contradiction_score=0.1,
                verdict="unknown",
                model_name="roberta-nli",
                chunks_evaluated=1,
                evidence_truncated=False,
            ),
        )

        low_threshold = await self.registry.evaluate(
            ["nli_eval"],
            inputs={},
            outputs="New answer.",
            reference_outputs="Reference.",
            execution_trace={},
            technique_configs={
                "nli_eval": {
                    "evidence_source": "expected_output",
                    "min_entail_score": 0.4,
                }
            },
        )
        high_threshold = await self.registry.evaluate(
            ["nli_eval"],
            inputs={},
            outputs="New answer.",
            reference_outputs="Reference.",
            execution_trace={},
            technique_configs={
                "nli_eval": {
                    "evidence_source": "expected_output",
                    "min_entail_score": 0.5,
                }
            },
        )

        assert low_threshold["nli_eval"]["passed"] is True
        assert high_threshold["nli_eval"]["passed"] is False

    @pytest.mark.asyncio
    async def test_nli_contradiction_option_blocks_a_strong_contradiction(
        self, monkeypatch
    ):
        monkeypatch.setattr(
            eval_mod.evaluation_nli_model,
            "score_evidence",
            lambda answer, evidence, model_name=None: SimpleNamespace(
                entail_score=0.7,
                contradiction_score=0.8,
                verdict="entails",
                model_name="roberta-nli",
                chunks_evaluated=2,
                evidence_truncated=False,
            ),
        )
        base_config = {
            "evidence_source": "expected_output",
            "min_entail_score": 0.5,
        }

        allowed = await self.registry.evaluate(
            ["nli_eval"],
            inputs={},
            outputs="New answer.",
            reference_outputs="Reference.",
            execution_trace={},
            technique_configs={
                "nli_eval": {**base_config, "fail_on_contradiction": False}
            },
        )
        blocked = await self.registry.evaluate(
            ["nli_eval"],
            inputs={},
            outputs="New answer.",
            reference_outputs="Reference.",
            execution_trace={},
            technique_configs={
                "nli_eval": {**base_config, "fail_on_contradiction": True}
            },
        )

        assert allowed["nli_eval"]["passed"] is True
        assert blocked["nli_eval"]["passed"] is False

    @pytest.mark.asyncio
    async def test_nli_fails_when_a_later_answer_section_is_unsupported(
        self, monkeypatch
    ):
        monkeypatch.setattr(
            eval_mod.evaluation_nli_model,
            "score_evidence",
            lambda answer, evidence, model_name=None: SimpleNamespace(
                entail_score=0.2,
                contradiction_score=0.1,
                verdict="unknown",
                model_name="roberta-nli",
                chunks_evaluated=3,
                evidence_truncated=False,
                claims_evaluated=2,
                total_claims=2,
                pairs_evaluated=6,
                coverage_complete=True,
                claim_results=(
                    NLIClaimResult(
                        text="The handbook allows annual leave.",
                        entail_score=0.9,
                        contradiction_score=0.01,
                        verdict="entails",
                    ),
                    NLIClaimResult(
                        text="Employees also receive unlimited paid leave.",
                        entail_score=0.2,
                        contradiction_score=0.1,
                        verdict="unknown",
                    ),
                ),
            ),
        )

        metrics = await self.registry.evaluate(
            ["nli_eval"],
            inputs={},
            outputs="A supported claim followed by an unsupported claim.",
            reference_outputs="Handbook evidence.",
            execution_trace={},
            technique_configs={
                "nli_eval": {
                    "evidence_source": "expected_output",
                    "min_entail_score": 0.5,
                }
            },
        )

        result = metrics["nli_eval"]
        assert result["passed"] is False
        assert result["claims_checked"] == 2
        assert result["supported_claims"] == 1
        assert result["unsupported_claims"] == [
            "Employees also receive unlimited paid leave."
        ]
        assert "1/2 answer sections supported" in result["comment"]

    @pytest.mark.asyncio
    async def test_nli_does_not_score_an_answer_above_the_safe_claim_limit(
        self, monkeypatch
    ):
        monkeypatch.setattr(
            eval_mod.evaluation_nli_model,
            "score_evidence",
            lambda answer, evidence, model_name=None: SimpleNamespace(
                entail_score=0.0,
                contradiction_score=0.0,
                verdict="unknown",
                model_name=None,
                chunks_evaluated=0,
                evidence_truncated=False,
                claims_evaluated=0,
                total_claims=9,
                pairs_evaluated=0,
                coverage_complete=False,
                claim_results=(),
            ),
        )

        metrics = await self.registry.evaluate(
            ["nli_eval"],
            inputs={},
            outputs="A very long answer.",
            reference_outputs="Evidence.",
            execution_trace={},
            technique_configs={"nli_eval": {"evidence_source": "expected_output"}},
        )

        result = metrics["nli_eval"]
        assert result.get("not_evaluated") is True
        assert result.get("error") is not True
        assert "9 claim groups" in result["comment"]

    @pytest.mark.asyncio
    async def test_nli_legacy_config_without_source_uses_expected_output(self, monkeypatch):
        captured = {}

        def fake_score(answer, evidence, model_name=None):
            captured["evidence"] = evidence
            return SimpleNamespace(
                entail_score=0.9,
                contradiction_score=0.01,
                verdict="entails",
                model_name="roberta-nli",
                chunks_evaluated=1,
                evidence_truncated=False,
            )

        monkeypatch.setattr(
            eval_mod.evaluation_nli_model,
            "score_evidence",
            fake_score,
        )
        metrics = await self.registry.evaluate(
            ["nli_eval"],
            inputs={},
            outputs="New answer.",
            reference_outputs="Imported reference answer.",
            execution_trace={},
            technique_configs={"nli_eval": {}},
        )
        assert metrics["nli_eval"]["passed"] is True
        assert captured["evidence"] == "Imported reference answer."

    @pytest.mark.asyncio
    async def test_nli_unresolved_legacy_field_is_not_evaluated(self, monkeypatch):
        called = False

        def fake_score(answer, evidence, model_name=None):
            nonlocal called
            called = True
            return SimpleNamespace(
                entail_score=1.0,
                contradiction_score=0.0,
                verdict="entails",
                model_name="roberta-nli",
                chunks_evaluated=1,
                evidence_truncated=False,
            )

        monkeypatch.setattr(
            eval_mod.evaluation_nli_model,
            "score_evidence",
            fake_score,
        )
        metrics = await self.registry.evaluate(
            ["nli_eval"],
            inputs={},
            outputs="New answer.",
            reference_outputs="Reference.",
            execution_trace={},
            technique_configs={"nli_eval": {"evidence_field": "trace.missing.value"}},
        )
        assert metrics["nli_eval"].get("not_evaluated") is True
        assert called is False

    @pytest.mark.asyncio
    async def test_nli_errors_when_model_unavailable(self, monkeypatch):
        monkeypatch.setattr(
            eval_mod.evaluation_nli_model,
            "score_evidence",
            lambda answer, evidence, model_name=None: SimpleNamespace(
                entail_score=0.3,
                contradiction_score=0.0,
                verdict="unknown",
                model_name=None,
                chunks_evaluated=0,
                evidence_truncated=False,
            ),
        )
        metrics = await self.registry.evaluate(
            ["nli_eval"],
            inputs={},
            outputs="X.",
            reference_outputs="the contract risk is low",
            execution_trace={},
            technique_configs={"nli_eval": {"evidence_source": "expected_output"}},
        )
        m = metrics["nli_eval"]
        assert m.get("error") is True
        assert m["passed"] is False

    def test_nli_checks_support_beyond_the_first_token_window(self):
        import torch

        class FakeTokenizer:
            def __init__(self):
                self._token_to_id = {}
                self._id_to_token = {}

            def encode(
                self,
                text,
                add_special_tokens=False,
                truncation=False,
                max_length=None,
            ):
                del add_special_tokens
                tokens = text.split()
                if truncation and max_length is not None:
                    tokens = tokens[:max_length]
                ids = []
                for token in tokens:
                    if token not in self._token_to_id:
                        token_id = len(self._token_to_id) + 1
                        self._token_to_id[token] = token_id
                        self._id_to_token[token_id] = token
                    ids.append(self._token_to_id[token])
                return ids

            def decode(self, token_ids, skip_special_tokens=True):
                del skip_special_tokens
                return " ".join(self._id_to_token[token_id] for token_id in token_ids)

            @staticmethod
            def num_special_tokens_to_add(pair=True):
                del pair
                return 3

            @staticmethod
            def __call__(
                evidence_chunks,
                answers,
                return_tensors,
                padding,
                truncation,
                max_length,
            ):
                del answers, return_tensors, padding, truncation, max_length
                markers = [
                    [1 if "late-support" in chunk else 0]
                    for chunk in evidence_chunks
                ]
                return {"input_ids": torch.tensor(markers)}

        class FakeModel:
            config = SimpleNamespace(
                id2label={0: "contradiction", 1: "neutral", 2: "entailment"}
            )

            @staticmethod
            def __call__(input_ids):
                logits = [
                    [0.0, 0.0, 6.0] if row[0].item() else [0.0, 6.0, 0.0]
                    for row in input_ids
                ]
                return SimpleNamespace(logits=torch.tensor(logits))

        model = EvaluationNLIModel()
        model._tokenizer = FakeTokenizer()
        model._model = FakeModel()
        model._loaded_model_name = DEFAULT_NLI_MODEL
        evidence = " ".join(["filler"] * 400 + ["late-support"] + ["tail"] * 30)

        result = model.score_evidence(
            "The policy is supported.",
            evidence,
            DEFAULT_NLI_MODEL,
        )

        assert result.verdict == "entails"
        assert result.entail_score > 0.9
        assert result.chunks_evaluated > 1

    def test_nli_evaluation_short_circuits_empty_evidence(self, monkeypatch):
        model = EvaluationNLIModel()

        def unexpected_model_load(model_name):
            del model_name
            pytest.fail("The model should not load for empty evidence.")

        monkeypatch.setattr(model, "_lazy_init", unexpected_model_load)

        result = model.score_evidence("An answer.", "")
        assert result.entail_score == 0.0
        assert result.contradiction_score == 0.0
        assert result.verdict == "unknown"
        assert result.model_name is None

    def test_nli_claim_groups_include_the_end_of_a_long_answer(self):
        class Tokenizer:
            def __init__(self):
                self._token_to_id = {}
                self._id_to_token = {}

            def encode(self, text, add_special_tokens=False):
                del add_special_tokens
                ids = []
                for token in text.split():
                    if token not in self._token_to_id:
                        token_id = len(self._token_to_id) + 1
                        self._token_to_id[token] = token_id
                        self._id_to_token[token_id] = token
                    ids.append(self._token_to_id[token])
                return ids

            def decode(self, token_ids, skip_special_tokens=True):
                del skip_special_tokens
                return " ".join(self._id_to_token[token_id] for token_id in token_ids)

        model = EvaluationNLIModel()
        model._tokenizer = Tokenizer()
        answer = " ".join(["opening"] * 110 + ["late-answer-claim"])

        claim_chunks, total_claims = model._answer_claim_token_ids(answer)
        final_claim = model._tokenizer.decode(claim_chunks[-1])

        assert total_claims == 2
        assert "late-answer-claim" in final_claim

        model._model = object()
        model._loaded_model_name = DEFAULT_NLI_MODEL
        oversized_answer = " ".join(
            f"claim-token-{index}" for index in range(9 * 96)
        )
        oversized_result = model.score_evidence(
            oversized_answer,
            "Evidence.",
            DEFAULT_NLI_MODEL,
        )

        assert oversized_result.coverage_complete is False
        assert oversized_result.total_claims == 9

    def test_nli_bounds_huge_evidence_while_still_including_its_end(self):
        chunks, was_bounded = EvaluationNLIModel._chunk_token_ids(
            list(range(10_000)),
            window_size=100,
            overlap=20,
            max_chunks=4,
        )

        assert was_bounded is True
        assert len(chunks) == 4
        assert 9_999 in chunks[-1]

    @pytest.mark.asyncio
    async def test_nli_timeout_is_metric_error_and_other_methods_continue(
        self,
        monkeypatch,
    ):
        """A slow NLI model is isolated as one readable evaluator error."""
        import threading

        def _result():
            return SimpleNamespace(
                entail_score=0.9,
                contradiction_score=0.0,
                verdict="entails",
                model_name="m",
                chunks_evaluated=1,
                evidence_truncated=False,
                claims_evaluated=1,
                total_claims=1,
                coverage_complete=True,
                claim_results=(),
            )

        release_slow_call = threading.Event()

        def slow_score_evidence(answer, evidence, model_name=None):
            del answer, evidence, model_name
            release_slow_call.wait(timeout=2.0)
            return _result()

        monkeypatch.setattr(eval_mod, "NLI_EVALUATION_TIMEOUT_SECONDS", 0.05)
        monkeypatch.setattr(
            eval_mod.evaluation_nli_model,
            "score_evidence",
            slow_score_evidence,
        )
        try:
            metrics = await self.registry.evaluate(
                ["nli_eval", "no_errors"],
                inputs={},
                outputs="Answer.",
                reference_outputs="evidence",
                execution_trace={},
                technique_configs={
                    "nli_eval": {"evidence_source": "expected_output"}
                },
            )
        finally:
            # asyncio.to_thread cannot stop the running function. Let this test's
            # straggler finish immediately after the timeout assertion path.
            release_slow_call.set()

        nli_result = metrics["nli_eval"]
        assert nli_result["score"] is None
        assert nli_result["passed"] is False
        assert nli_result["error"] is True
        assert nli_result["comment"] == (
            "NLI evaluation error: the model did not respond "
            "within the allowed time."
        )
        assert metrics["no_errors"]["passed"] is True

    @pytest.mark.asyncio
    async def test_provenance_skips_when_no_context(self):
        metrics = await self.registry.evaluate(
            ["provenance_eval"],
            inputs={},
            outputs="Answer text.",
            reference_outputs=None,
            execution_trace={},
            technique_configs={"provenance_eval": {}},
        )
        assert metrics["provenance_eval"].get("not_evaluated") is True

    @pytest.mark.asyncio
    async def test_provenance_mode_less_config_defaults_to_embeddings(self):
        """A config saved before the mode field existed grades with embeddings,
        never the removed word-overlap heuristic."""
        async def fake_embed(answer, context, config):
            return 0.9

        self.registry._embedding_provenance_score = fake_embed
        metrics = await self.registry.evaluate(
            ["provenance_eval"],
            inputs={},
            outputs="the contract risk is low",
            reference_outputs="the contract risk is low",
            execution_trace={},
            technique_configs={
                "provenance_eval": {"context_source": "expected_output", "min_score": 0.5}
            },
        )
        m = metrics["provenance_eval"]
        assert m.get("not_evaluated") is not True
        assert m["passed"] is True
        assert "embedding" in m["comment"].lower()

    @pytest.mark.asyncio
    async def test_provenance_legacy_config_without_source_uses_expected_output(self):
        async def fake_embed(answer, context, config):
            return 0.9

        self.registry._embedding_provenance_score = fake_embed
        metrics = await self.registry.evaluate(
            ["provenance_eval"],
            inputs={},
            outputs="the contract risk is low",
            reference_outputs="the contract risk is low",
            execution_trace={},
            technique_configs={"provenance_eval": {"min_score": 0.5}},
        )
        assert metrics["provenance_eval"]["passed"] is True

    @pytest.mark.asyncio
    async def test_provenance_embeddings_uses_real_provider(self, monkeypatch):
        async def fake_embed(answer, context, config):
            return 0.95

        self.registry._embedding_provenance_score = fake_embed
        metrics = await self.registry.evaluate(
            ["provenance_eval"],
            inputs={},
            outputs="grounded answer",
            reference_outputs="some grounding context",
            execution_trace={},
            technique_configs={
                "provenance_eval": {
                    "context_source": "expected_output",
                    "provenance_mode": "embeddings",
                    "min_score": 0.8,
                }
            },
        )
        m = metrics["provenance_eval"]
        assert m["passed"] is True
        assert "embedding" in m["comment"].lower()
        assert m["threshold"] == 0.8

    @pytest.mark.asyncio
    async def test_provenance_embeddings_errors_when_unavailable(self):
        async def boom(answer, context, config):
            raise RuntimeError("no embedding provider")

        self.registry._embedding_provenance_score = boom
        metrics = await self.registry.evaluate(
            ["provenance_eval"],
            inputs={},
            outputs="grounded answer",
            reference_outputs="some grounding context",
            execution_trace={},
            technique_configs={
                "provenance_eval": {
                    "context_source": "expected_output",
                    "provenance_mode": "embeddings",
                }
            },
        )
        m = metrics["provenance_eval"]
        assert m.get("error") is True
        assert m["passed"] is False

    @pytest.mark.asyncio
    async def test_provenance_embeddings_clamps_unrelated_to_zero(self):
        """Orthogonal vectors (cosine 0) score 0 and fail — not 0.5 as the old remap gave."""
        async def fake_get(config):
            return _FakeEmbedder([1.0, 0.0], [0.0, 1.0])

        self.registry._get_embedder = fake_get
        metrics = await self.registry.evaluate(
            ["provenance_eval"],
            inputs={},
            outputs="unrelated answer",
            reference_outputs="different context",
            execution_trace={},
            technique_configs={
                "provenance_eval": {
                    "context_source": "expected_output",
                    "provenance_mode": "embeddings",
                    "min_score": 0.5,
                }
            },
        )
        m = metrics["provenance_eval"]
        assert m["score"] == 0.0
        assert m["passed"] is False

    @pytest.mark.asyncio
    async def test_provenance_embeddings_scores_identical_as_one(self):
        async def fake_get(config):
            return _FakeEmbedder([1.0, 0.0], [1.0, 0.0])

        self.registry._get_embedder = fake_get
        metrics = await self.registry.evaluate(
            ["provenance_eval"],
            inputs={},
            outputs="grounded answer",
            reference_outputs="grounded answer",
            execution_trace={},
            technique_configs={
                "provenance_eval": {
                    "context_source": "expected_output",
                    "provenance_mode": "embeddings",
                    "min_score": 0.8,
                }
            },
        )
        assert metrics["provenance_eval"]["score"] == 1.0
        assert metrics["provenance_eval"]["passed"] is True

    @pytest.mark.asyncio
    async def test_provenance_rejects_out_of_range_threshold(self):
        async def fake_get(config):
            return _FakeEmbedder([1.0, 0.0], [1.0, 0.0])

        self.registry._get_embedder = fake_get
        metrics = await self.registry.evaluate(
            ["provenance_eval"],
            inputs={},
            outputs="grounded answer",
            reference_outputs="grounded answer",
            execution_trace={},
            technique_configs={
                "provenance_eval": {
                    "context_source": "expected_output",
                    "provenance_mode": "embeddings",
                    "min_score": 5,
                }
            },
        )
        assert metrics["provenance_eval"].get("error") is True

    @pytest.mark.asyncio
    async def test_embedder_is_cached_across_calls(self, monkeypatch):
        import app.modules.data.providers.vector.embedding.base as emb_base

        builds = {"n": 0}

        class _FakeCfg:
            def __init__(self, **kwargs):
                pass

            def get(self):
                builds["n"] += 1
                return _FakeEmbedder([1.0, 0.0], [1.0, 0.0])

        monkeypatch.setattr(emb_base, "EmbeddingConfig", _FakeCfg)
        config = {"embedding_type": "huggingface", "embedding_model_name": "all-MiniLM-L6-v2"}
        first = await self.registry._get_embedder(config)
        second = await self.registry._get_embedder(config)
        assert first is second
        assert builds["n"] == 1


class TestNliSinglePairScore:
    """score() stays single-pair for GuardrailNliNode, decoupled from the claim-based
    score_evidence() the evaluator uses."""

    def _model_with(self, logits_row):
        import torch
        from types import SimpleNamespace
        from app.modules.workflow.engine.nodes.local_nli_model import LocalNLIModel

        class FakeTokenizer:
            def __call__(self, evidence, answer, **kwargs):  # noqa: ARG002
                return {"input_ids": torch.tensor([[0]])}

        class FakeModel:
            config = SimpleNamespace(
                id2label={0: "contradiction", 1: "neutral", 2: "entailment"}
            )

            def __call__(self, input_ids):  # noqa: ARG002
                return SimpleNamespace(logits=torch.tensor([logits_row]))

        model = LocalNLIModel()
        model._tokenizer = FakeTokenizer()
        model._model = FakeModel()
        model._loaded_model_name = DEFAULT_NLI_MODEL
        return model

    def test_score_returns_entailment_in_one_pass(self):
        _, _, verdict = self._model_with([0.0, 0.0, 6.0]).score("Answer.", "Evidence.")
        assert verdict == "entails"

    def test_score_returns_contradiction(self):
        entail, contra, verdict = self._model_with([6.0, 0.0, 0.0]).score("A.", "B.")
        assert verdict == "contradicts"
        assert contra > entail

    def test_score_ignores_the_claim_cap(self):
        # >8 sentences would make score_evidence() bail with coverage_complete=False
        # (0, 0, "unknown"). score() must score the whole answer regardless.
        many = " ".join(f"Claim number {i}." for i in range(20))
        _, _, verdict = self._model_with([0.0, 0.0, 6.0]).score(many, "Evidence.")
        assert verdict == "entails"

class TestGuardrailNliNode:
    """The production guardrail node: contradiction drives fallback/blocking."""

    def _node(self):
        from app.modules.workflow.engine.nodes.guardrail_nli_node import GuardrailNliNode

        node = GuardrailNliNode.__new__(GuardrailNliNode)
        node.node_id = "n1"
        node.set_node_input = lambda *a, **k: None
        return node

    def _patch_score(self, monkeypatch, result):
        from app.modules.workflow.engine.nodes.local_nli_model import local_nli_model

        monkeypatch.setattr(
            local_nli_model, "score", lambda answer, evidence, model_name=None: result
        )

    @pytest.mark.asyncio
    async def test_contradiction_swaps_in_fallback_answer(self, monkeypatch):
        self._patch_score(monkeypatch, (0.1, 0.9, "contradicts"))
        out = await self._node().process({
            "answer_field": "The sky is green.",
            "evidence_field": "The sky is blue.",
            "fail_on_contradiction": True,
            "fallback_answer_enabled": True,
            "fallback_answer": "I'm not certain.",
        })
        assert out["answer"] == "I'm not certain."
        assert out["_guardrail_nli"]["fallback_used"] is True

    @pytest.mark.asyncio
    async def test_contradiction_blocks_when_no_fallback(self, monkeypatch):
        self._patch_score(monkeypatch, (0.1, 0.9, "contradicts"))
        out = await self._node().process({
            "answer_field": "X",
            "evidence_field": "Y",
            "fail_on_contradiction": True,
        })
        assert out.get("blocked") is True
        assert out["verdict"] == "nli_contradiction"

    @pytest.mark.asyncio
    async def test_entailment_passes_through(self, monkeypatch):
        self._patch_score(monkeypatch, (0.95, 0.01, "entails"))
        out = await self._node().process({"answer_field": "A", "evidence_field": "B"})
        assert out["answer"] == "A"
        assert out.get("blocked") is None
        assert out["_guardrail_nli"]["verdict"] == "entails"


class TestPromptCachingDiagnosticsAreInvisibleToGrading:
    def test_the_collection_does_not_change_the_grading_context(self):
        trace = _sample_trace()
        annotated = {
            **trace,
            "state": {
                **trace["state"],
                "promptCachingDiagnostics": {"child": {"requested": True, "applied": False}},
            },
        }

        assert _build_grading_context(annotated) == _build_grading_context(trace)
