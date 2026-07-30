import asyncio
import logging
import json
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple
from uuid import UUID, uuid4

from injector import inject
from langchain_core.messages import HumanMessage, SystemMessage

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.dependencies.injector import injector
from app.db.models.test_suite import (
    TestSuiteModel,
    TestCaseModel,
    TestRunModel,
    TestResultModel,
    TestEvaluationModel,
    TestToolRuleResultModel,
)
from app.services.evaluation_nli import (
    NLI_MAX_ANSWER_CLAIMS,
    evaluation_nli_model,
)
from app.modules.workflow.engine.workflow_engine import (
    MemoryPersistenceError,
    WorkflowEngine,
)
from app.modules.workflow.llm.provider import LLMProvider
from app.modules.workflow.usage_context import WorkflowUsageContext
from app.core.utils.transcript_utils import extract_qa_pairs
from app.core.utils.uuid_utils import coerce_uuid
from app.repositories.conversations import ConversationRepository
from app.repositories.test_suite import (
    TestSuiteRepository,
    TestCaseRepository,
    TestRunRepository,
    TestResultRepository,
    TestEvaluationRepository,
    TestToolRuleResultRepository,
)
from app.schemas.test_suite import (
    ImportCasesFromConversationRequest,
    PaginatedEvaluations,
    StartedEvaluationRun,
    TestCaseCreate,
    TestCaseInDB,
    TestCaseUpdate,
    TestEvaluation,
    TestEvaluationCreate,
    TestEvaluationUpdate,
    TestEvaluationInDB,
    TestRun,
    TestRunCreate,
    TestRunInDB,
    TestResultInDB,
    TestToolRuleResult,
    TestSuiteCreate,
    TestSuiteUpdate,
    TestSuiteInDB,
    EvaluationToolCatalog,
    WorkflowEvaluationSummary,
)
from app.schemas.workflow import WorkflowInDB
from app.services.workflow import WorkflowService
from app.core.tenant_scope import get_tenant_context
from app.modules.websockets.socket_connection_manager import SocketConnectionManager
from app.services.realtime_notifications import emit_notification, notification_payload


logger = logging.getLogger(__name__)


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    # Unwrap single-key string wrapper dicts produced by both the frontend
    # (expected_output fallback) and the execution engine (actual_output).
    # Supported keys: "value" (execution wrapper) and "text" (legacy frontend wrapper).
    if isinstance(value, dict):
        for key in ("value", "text"):
            if list(value.keys()) == [key] and isinstance(value[key], str):
                return value[key].strip()
    return str(value).strip()


def _truncate_output(output: Any, max_length: int = 64000) -> Any:
    """
    Keep full workflow outputs for inspection; only truncate extremely large
    strings to protect the database from pathological cases.
    """
    if isinstance(output, str) and len(output) > max_length:
        return output[: max_length - 3] + "..."
    return output


# Reserved key holding run-level counts alongside the per-technique metrics.
RUN_TOTALS_KEY = "_totals"

# Tool Usage is graded per scope from collected tool events, not per case.
TOOL_USED_TECHNIQUE = "tool_used"

# Checks that cannot honestly run until the workflow has produced its final answer.
_FINAL_OUTPUT_TECHNIQUES = frozenset(
    {
        "exact_match",
        "contains",
        "not_contains",
        "json_match",
        "nli_eval",
        "provenance_eval",
        "llm_judge",
    }
)

# Upper bounds so one hung case or evaluator cannot keep a run in "running".
CASE_EXECUTION_TIMEOUT_SECONDS = 20 * 60
EVALUATOR_TIMEOUT_SECONDS = 5 * 60
NLI_EVALUATION_TIMEOUT_SECONDS = 2 * 60


class ResultStatus:
    """Why a case did or did not produce metrics."""

    SCORED = "scored"
    EXECUTION_FAILED = "execution_failed"
    SCORING_FAILED = "scoring_failed"
    SKIPPED = "skipped"


def _failure_reason(state: Any) -> str:
    """Read the failure off the state's error list; ``output`` is empty on failure."""
    errors = getattr(state, "errors", None) or []
    if errors:
        last = errors[-1]
        message = last.get("message") if isinstance(last, dict) else str(last)
        if message:
            return str(message)
    return "Workflow execution failed"


def _is_waiting_for_human(output: Any) -> bool:
    """True when workflow execution paused to collect human input."""
    return isinstance(output, dict) and output.get("status") == "awaiting_input"


def _requires_final_output(technique: str, config: Dict[str, Any]) -> bool:
    """Whether a check needs the final answer rather than intermediate run state."""
    if technique in _FINAL_OUTPUT_TECHNIQUES:
        return True
    if technique != "field_equals":
        return False

    field = config.get("field")
    if not field:
        return True
    return (
        field == "outputs"
        or field.startswith("outputs.")
        or field == "trace.output"
        or field.startswith("trace.output.")
    )


def _group_cases_into_conversations(
    cases: List["TestCaseInDB"],
) -> List[List["TestCaseInDB"]]:
    """
    Group cases by source conversation and order each group by turn index.

    Cases without a source conversation are independent single-turn conversations,
    so they are keyed by their own id rather than collapsing into one group.
    """
    conversations: Dict[Any, List["TestCaseInDB"]] = {}
    for case in cases:
        key = case.source_conversation_id or case.id
        conversations.setdefault(key, []).append(case)

    for group in conversations.values():
        group.sort(key=lambda case: (case.turn_index or 0, case.created_at))

    return list(conversations.values())


def _read_path(data: Any, path: str) -> Any:
    if not path:
        return None
    current = data
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current


def _resolve_selector_value(
    selector: Any,
    *,
    payload: Dict[str, Any],
    default: Any,
) -> Any:
    if selector is None:
        return default
    if isinstance(selector, str):
        value = _read_path(payload, selector)
        if value is not None:
            return value
        return selector
    return selector


# Stable source presets grounding evaluators can compare against, decoupling the
# UI ("Knowledge-base passages retrieved during the run") from the trace shape.
GRADING_SOURCE_TYPES = (
    "none",
    "expected_output",
    "output",
    "kb_retrievals",
    "conversation_context",
    "tool_events",
)


def _source_text(source_type: str, payload: Dict[str, Any]) -> str:
    """Render a named grading source from the payload as bounded text."""
    trace = payload.get("trace") if isinstance(payload.get("trace"), dict) else {}
    if source_type == "none":
        return ""
    if source_type == "expected_output":
        return _normalize_text(payload.get("reference_outputs"))
    if source_type == "output":
        return _normalize_text(payload.get("outputs"))
    if source_type == "kb_retrievals":
        return _serialize_judge_source(trace.get("retrievals"))
    if source_type == "conversation_context":
        return _serialize_judge_source(trace.get("session"))
    if source_type == "tool_events":
        return _serialize_judge_source(trace.get("tool_events"))
    return ""


def _resolve_grading_source(
    config: Dict[str, Any],
    *,
    source_key: str,
    legacy_field_key: str,
    payload: Dict[str, Any],
) -> str:
    """Resolve a grounding source to text: explicit source type, else a legacy
    dotted-path field, else the expected output used by legacy evaluations. Empty text means the
    caller should skip (not_evaluated) rather than grade against nothing."""
    source_type = config.get(source_key)
    if source_type:
        return _source_text(source_type, payload)
    legacy = config.get(legacy_field_key)
    if isinstance(legacy, str):
        return _normalize_text(_read_path(payload, legacy))
    return _source_text("expected_output", payload)


def _normalize_tool_call(entry: Dict[str, Any]) -> Dict[str, Any]:
    """Map an agent tool step/record to a stable {name, args, result}."""
    return {
        "name": entry.get("tool_name") or entry.get("tool") or entry.get("name"),
        "args": entry.get("args") or entry.get("tool_input") or entry.get("validated_args") or {},
        "result": entry.get("result"),
    }


def _extract_tool_calls(output: Any) -> List[Dict[str, Any]]:
    """Pull tool calls from an agent node output (tools_used, else tool-like steps)."""
    if not isinstance(output, dict):
        return []
    raw = output.get("tools_used")
    if not isinstance(raw, list) or not raw:
        raw = [
            step
            for step in (output.get("steps") or [])
            if isinstance(step, dict) and (step.get("tool") or step.get("tool_name"))
        ]
    calls = [_normalize_tool_call(e) for e in raw if isinstance(e, dict)]
    return [c for c in calls if c["name"]]


def _extract_retrieval(node_type: Any, output: Any) -> Dict[str, Any] | None:
    """Pull a {query, results} view from knowledge-base / thread-RAG node output."""
    if node_type == "threadRAGNode" and isinstance(output, dict) and "results" in output:
        return {"query": output.get("query"), "results": output.get("results")}
    if node_type == "knowledgeBaseNode":
        if not output or (isinstance(output, dict) and "error" in output):
            return None
        return {"query": None, "results": output}
    if isinstance(output, dict) and "results" in output and "query" in output:
        return {"query": output.get("query"), "results": output.get("results")}
    return None


# Substrings that mark a tool as a knowledge-retrieval tool, so retrieval done
# through an agent tool (not a dedicated KB node) still counts as retrieved context.
_RETRIEVAL_TOOL_HINTS = (
    "knowledge", "kb", "retriev", "rag", "search_doc", "document_search",
    "vector", "semantic", "faq", "lookup",
)
_RETRIEVAL_NODE_TYPES = {
    "knowledgebasenode", "knowledgetoolnode", "threadragnode", "websearchnode",
}


def _is_retrieval_tool(event: Dict[str, Any], nodes: Dict[str, Any]) -> bool:
    """True when a tool event represents knowledge retrieval (KB-backed or named like one)."""
    node = nodes.get(event.get("tool_id")) if isinstance(nodes, dict) else None
    node_type = node.get("type") if isinstance(node, dict) else None
    if isinstance(node_type, str) and node_type.lower() in _RETRIEVAL_NODE_TYPES:
        return True
    name = _normalize_text(event.get("tool_name")).lower()
    return any(hint in name for hint in _RETRIEVAL_TOOL_HINTS)


def _names_equal(first: Any, second: Any) -> bool:
    return _normalize_text(first).lower() == _normalize_text(second).lower()


def _parse_judge_json(raw_content: Any) -> tuple[float | None, str | None]:
    """Parse a judge's ``{score, reason}`` reply; a missing/invalid score yields no score."""
    try:
        parsed = json.loads(raw_content)
        if not isinstance(parsed, dict):
            return None, "LLM judge response was not a JSON object"
        # A missing score is a malformed judgment, not a real 0.0 — surface it as
        # an error rather than silently failing the answer.
        if parsed.get("score") is None:
            return None, "LLM judge response did not include a score"
        score = max(0.0, min(1.0, float(parsed["score"])))
        reason = str(parsed.get("reason", "")).strip() or None
        return score, reason
    except (ValueError, TypeError, json.JSONDecodeError):
        return None, "LLM judge response could not be parsed"


def _serialize_judge_source(value: Any, max_length: int = 16000) -> str:
    """Render a judge SOURCE (e.g. trace retrievals) as bounded text; empty when there is none."""
    if not value:
        return ""
    text = value if isinstance(value, str) else json.dumps(value, default=str)
    return text[:max_length].strip()


def _args_superset_match(args: Any, expected: Dict[str, Any]) -> bool:
    """True when every expected key/value is present in the actual tool args."""
    if not isinstance(args, dict):
        return False
    return all(_normalize_text(args.get(key)) == _normalize_text(value) for key, value in expected.items())


# No-result phrases emitted by the platform's retrieval layers (doc.py, knowledge_tool_node.py).
_EMPTY_RESULT_PREFIXES = ("no results found", "no relevant information found")


def _tool_result_satisfies(call: Dict[str, Any], require_not_empty: bool, required_text: str) -> bool:
    """True when the tool call's result meets the configured content assertions."""
    raw_result = call.get("result")
    result_text = _normalize_text(raw_result)
    is_structurally_empty = isinstance(raw_result, (list, dict)) and not raw_result
    is_no_result_sentinel = result_text.lower().startswith(_EMPTY_RESULT_PREFIXES)
    is_empty = not result_text or is_structurally_empty or is_no_result_sentinel
    if require_not_empty and is_empty:
        return False
    if required_text and required_text not in result_text:
        return False
    return True


def _node_matches_selector(node: Dict[str, Any], selector: Any) -> bool:
    """Match a trace node by exact id or case-insensitive display label."""
    return node.get("id") == selector or _names_equal(node.get("label"), selector)


def _is_empty_retrieval_result(result: Any) -> bool:
    """True when a retrieval result carries no usable content (empty or a no-result sentinel)."""
    return not _tool_result_satisfies({"result": result}, require_not_empty=True, required_text="")


def _retrieval_content_key(value: Any) -> str:
    """Normalized fingerprint of retrieved content, so identical results dedupe by text."""
    text = value if isinstance(value, str) else json.dumps(value, default=str, sort_keys=True)
    return _normalize_text(text).lower()


def _append_retrieval(
    retrievals: List[Any],
    seen_content: set,
    *,
    node: Any,
    label: Any,
    query: Any,
    results: Any,
) -> None:
    """Add a retrieval unless its content is empty, a no-result sentinel, or a duplicate."""
    if _is_empty_retrieval_result(results):
        return
    content_key = _retrieval_content_key(results)
    if content_key in seen_content:
        return
    retrievals.append({"node": node, "label": label, "query": query, "results": results})
    seen_content.add(content_key)


def _build_grading_context(execution_trace: Any) -> Dict[str, Any]:
    """Stable, workflow-agnostic view of a run for evaluators to grade against."""
    trace = execution_trace if isinstance(execution_trace, dict) else {}
    state = trace.get("state") if isinstance(trace.get("state"), dict) else {}
    node_status = state.get("nodeExecutionStatus")
    node_status = node_status if isinstance(node_status, dict) else {}

    nodes: Dict[str, Any] = {}
    nodes_by_type: Dict[str, List[Any]] = {}
    nodes_by_label: Dict[str, List[Any]] = {}
    for node_id, info in node_status.items():
        if not isinstance(info, dict):
            continue
        entry = {
            "id": node_id,
            "type": info.get("type"),
            "label": info.get("name"),
            "input": info.get("input"),
            "output": info.get("output"),
            "status": info.get("status"),
            "error": info.get("error"),
        }
        nodes[node_id] = entry
        if entry["type"]:
            nodes_by_type.setdefault(entry["type"], []).append(entry)
        if entry["label"]:
            nodes_by_label.setdefault(entry["label"], []).append(entry)

    session = state.get("input") if isinstance(state.get("input"), dict) else {}

    errors: List[Any] = list(state.get("errors") or [])
    tools: List[Any] = []
    retrievals: List[Any] = []
    # Retrieved context is deduped by content across both sources below, and skips
    # empty or no-result payloads, so grounding evaluators never check against nothing.
    seen_content: set = set()
    for entry in nodes.values():
        if entry.get("error"):
            errors.append({"node": entry["id"], "error": entry["error"]})
        for call in _extract_tool_calls(entry["output"]):
            tools.append({"node": entry["id"], **call})
        retrieval = _extract_retrieval(entry["type"], entry["output"])
        node_failed = entry.get("status") == "failed" or bool(entry.get("error"))
        if retrieval is not None and not node_failed:
            _append_retrieval(
                retrievals,
                seen_content,
                node=entry["id"],
                label=entry["label"],
                query=retrieval.get("query"),
                results=retrieval.get("results"),
            )

    # Agents retrieve through tools (e.g. a knowledge-base tool), whose result
    # lands in tool_events rather than a KB node. Fold those in so "retrieved
    # context" reflects what the agent actually looked up; only successful calls count.
    for event in (trace.get("tool_events") or []):
        if not isinstance(event, dict):
            continue
        if event.get("status") != "succeeded":
            continue
        if not _is_retrieval_tool(event, nodes):
            continue
        _append_retrieval(
            retrievals,
            seen_content,
            node=event.get("tool_id"),
            label=event.get("tool_name"),
            query=None,
            results=event.get("result"),
        )

    return {
        "output": trace.get("output"),
        "nodes": nodes,
        "nodes_by_type": nodes_by_type,
        "nodes_by_label": nodes_by_label,
        "session": session,
        "tools": tools,
        "retrievals": retrievals,
        "errors": errors,
        "tokens": trace.get("token_usage") or {},
        "cost": trace.get("cost_usd"),
        # Normalized tool-execution events for the rule-based tool_used evaluator.
        "tool_events": trace.get("tool_events") or [],
    }


def _clean_forbidden_phrases(config: Dict[str, Any]) -> List[str]:
    """Forbidden phrases from config: trimmed, de-duplicated (casefold), legacy ``text`` accepted.

    Only a string or a list of strings is accepted; any other shape yields no phrases.
    """
    raw = config.get("phrases")
    if raw is None:
        raw = config.get("text")
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, list):
        return []
    phrases: List[str] = []
    seen: set[str] = set()
    for entry in raw:
        if not isinstance(entry, str):
            continue
        cleaned = entry.strip()
        key = cleaned.casefold()
        if not cleaned or key in seen:
            continue
        seen.add(key)
        phrases.append(cleaned)
    return phrases


def resolvers_from_agents(agents: List[Dict[str, Any]]):
    """Build ``(resolve_tool_id, resolve_agent_id, agent_ids, all_tool_ids)`` from a
    resolved agent catalogue.

    The catalogue is the single source shared by the catalogue UI, config
    canonicalization and run-time grading, so every tool it lists — including nested
    and MCP tools, and tools never called — resolves the same way everywhere. The
    agent-id set lets callers count only real agents as "executed"; ``all_tool_ids``
    expands a legacy "any tool" config.
    """
    from app.services.tool_catalog import (
        build_agent_index,
        build_tool_index,
        resolve_in_index,
    )

    tool_index = build_tool_index(agents)
    agent_index = build_agent_index(agents)
    agent_ids = {agent["id"] for agent in agents}
    all_tool_ids = sorted({tool["id"] for agent in agents for tool in agent["tools"]})
    return (
        lambda name: resolve_in_index(tool_index, name, "tool"),
        lambda label: resolve_in_index(agent_index, label, "agent"),
        agent_ids,
        all_tool_ids,
    )


def build_tool_usage_resolvers(workflow: Any):
    """Resolvers over a single workflow graph (no nested-workflow expansion).

    Used only by the direct registry evaluator, which has just the graph and no DB
    access. Returns ``(None, None, None, None)`` when no workflow is available; the
    parser then keeps ids/names as given. Nested/MCP-aware paths use the service's
    full catalogue via :func:`resolvers_from_agents` instead.
    """
    from app.services.tool_catalog import resolve_agents

    if workflow is None:
        return None, None, None, None
    return resolvers_from_agents(resolve_agents(workflow))


class SimpleEvaluatorRegistry:
    """
    Lightweight evaluator registry inspired by OpenEvals.

    Each evaluator receives:
        inputs: dict
        outputs: dict | str | None
        reference_outputs: dict | str | None
    and returns:
        { "key": str, "score": bool|float, "passed": bool, "comment": str|None }
    """

    def __init__(self) -> None:
        self._embedder_cache: Dict[str, Any] = {}
        self._evaluators = {
            "exact_match": self._exact_match,
            "contains": self._contains,
            "not_contains": self._not_contains,
            "json_match": self._json_match,
            "field_equals": self._field_equals,
            "no_errors": self._no_errors,
            "tool_used": self._tool_used,
            "route_taken": self._route_taken,
            "action_taken": self._action_taken,
            "nli_eval": self._guardrail_nli,
            "provenance_eval": self._guardrail_provenance,
            "llm_judge": self._llm_judge,
        }

    def available(self) -> List[str]:
        return sorted(self._evaluators.keys())

    def default_techniques(self) -> List[str]:
        """Techniques run when a run specifies none. Excludes checks that need per-run config."""
        return ["exact_match", "contains", "json_match", "field_equals", "no_errors", "nli_eval", "provenance_eval"]

    async def evaluate(
        self,
        techniques: Iterable[str],
        *,
        inputs: Dict[str, Any],
        outputs: Any,
        reference_outputs: Any,
        execution_trace: Any = None,
        technique_configs: Dict[str, Dict[str, Any]] | None = None,
        workflow: Any = None,
    ) -> Dict[str, Dict[str, Any]]:
        results: Dict[str, Dict[str, Any]] = {}
        payload = {
            "inputs": inputs,
            "outputs": outputs,
            "reference_outputs": reference_outputs,
            "trace": _build_grading_context(execution_trace),
            # Workflow graph for legacy name→id resolution via the full tool catalogue.
            "workflow": workflow,
        }
        for key in techniques:
            fn = self._evaluators.get(key)
            if not fn:
                continue
            config = (technique_configs or {}).get(key, {})
            if _is_waiting_for_human(outputs) and _requires_final_output(key, config):
                results[key] = {
                    "key": key,
                    "score": None,
                    "passed": False,
                    "not_evaluated": True,
                    "comment": "Not evaluated — waiting for human input.",
                }
                continue
            try:
                result = await fn(
                    inputs=inputs,
                    outputs=outputs,
                    reference_outputs=reference_outputs,
                    payload=payload,
                    config=config,
                )
                results[result["key"]] = result
            except Exception as exc:  # pylint: disable=broad-except
                # Surface the failure as a failed metric — never drop it, or a broken
                # evaluator would make the run look green. Keep the exception in server
                # logs only; the user-facing comment stays generic to avoid leaking
                # provider/internal details.
                logger.exception("Error running evaluator %s: %s", key, exc)
                # An evaluator crash is our fault, not the agent's — mark it as an
                # error so aggregation excludes it from pass/fail instead of
                # counting a broken evaluator as a failing agent.
                results[key] = {
                    "key": key,
                    "score": None,
                    "passed": False,
                    "error": True,
                    "comment": "Evaluator failed to run. Check server logs for details.",
                }
        return results

    # ---- basic techniques -------------------------------------------------

    async def _exact_match(
        self,
        *,
        inputs: Dict[str, Any],  # noqa: ARG002 - not used by this evaluator
        outputs: Any,
        reference_outputs: Any,
        payload: Dict[str, Any],  # noqa: ARG002 - reserved for unified signature
        config: Dict[str, Any],  # noqa: ARG002 - reserved for unified signature
    ) -> Dict[str, Any]:
        actual = _normalize_text(outputs)
        expected = _normalize_text(reference_outputs)
        passed = bool(actual and expected and actual == expected)
        return {
            "key": "exact_match",
            "score": passed,
            "passed": passed,
            "comment": None if passed else "Outputs differ from expected.",
        }

    async def _contains(
        self,
        *,
        inputs: Dict[str, Any],  # noqa: ARG002 - not used by this evaluator
        outputs: Any,
        reference_outputs: Any,
        payload: Dict[str, Any],  # noqa: ARG002 - reserved for unified signature
        config: Dict[str, Any],  # noqa: ARG002 - reserved for unified signature
    ) -> Dict[str, Any]:
        actual = _normalize_text(outputs)
        expected = _normalize_text(reference_outputs)
        passed = bool(actual and expected and expected.casefold() in actual.casefold())
        return {
            "key": "contains",
            "score": passed,
            "passed": passed,
            "comment": None if passed else "Expected text not found in output.",
        }

    async def _not_contains(
        self,
        *,
        inputs: Dict[str, Any],  # noqa: ARG002 - not used by this evaluator
        outputs: Any,
        reference_outputs: Any,  # noqa: ARG002 - forbidden phrases come from config
        payload: Dict[str, Any],  # noqa: ARG002 - reserved for unified signature
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Pass when none of the configured forbidden phrases appear in the output."""
        phrases = _clean_forbidden_phrases(config)
        if not phrases:
            return {
                "key": "not_contains",
                "score": False,
                "passed": False,
                "comment": "No forbidden phrases configured.",
            }
        actual = _normalize_text(outputs).casefold()
        found = [phrase for phrase in phrases if phrase.casefold() in actual]
        passed = not found
        return {
            "key": "not_contains",
            "score": passed,
            "passed": passed,
            "comment": None if passed else f"Forbidden phrases found in output: {', '.join(found)}.",
        }

    async def _json_match(
        self,
        *,
        inputs: Dict[str, Any],  # noqa: ARG002 - not used by this evaluator
        outputs: Any,
        reference_outputs: Any,
        payload: Dict[str, Any],  # noqa: ARG002 - reserved for unified signature
        config: Dict[str, Any],  # noqa: ARG002 - reserved for unified signature
    ) -> Dict[str, Any]:
        if not isinstance(outputs, dict) or not isinstance(reference_outputs, dict):
            return {
                "key": "json_match",
                "score": False,
                "passed": False,
                "comment": "Expected both output and reference to be JSON objects.",
            }
        passed = outputs == reference_outputs
        return {
            "key": "json_match",
            "score": passed,
            "passed": passed,
            "comment": None if passed else "JSON outputs do not match.",
        }

    async def _field_equals(
        self,
        *,
        inputs: Dict[str, Any],  # noqa: ARG002 - reserved for unified signature
        outputs: Any,
        reference_outputs: Any,
        payload: Dict[str, Any],
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Exact-match a value read from the run (dot-path ``field``) vs expected."""
        field = config.get("field")
        actual_value = _read_path(payload, field) if field else outputs
        expected_value = config.get("expected", reference_outputs)

        actual = _normalize_text(actual_value)
        expected = _normalize_text(expected_value)
        passed = bool(actual and expected and actual == expected)

        return {
            "key": "field_equals",
            "score": passed,
            "passed": passed,
            "expected": expected,
            "actual": actual,
            "comment": (
                None if passed else f"{field or 'outputs'}={actual!r} (expected {expected!r})"
            ),
        }

    async def _no_errors(
        self,
        *,
        inputs: Dict[str, Any],  # noqa: ARG002 - not used by this evaluator
        outputs: Any,  # noqa: ARG002 - reserved for unified signature
        reference_outputs: Any,  # noqa: ARG002 - reserved for unified signature
        payload: Dict[str, Any],
        config: Dict[str, Any],  # noqa: ARG002 - reserved for unified signature
    ) -> Dict[str, Any]:
        """Pass only when the run produced no node/run-level errors."""
        trace = payload.get("trace") or {}
        errors = trace.get("errors") or []
        passed = len(errors) == 0

        return {
            "key": "no_errors",
            "score": passed,
            "passed": passed,
            "comment": None if passed else f"{len(errors)} error(s) during run.",
        }

    # ---- agent process techniques ----------------------------------------

    async def _tool_used(
        self,
        *,
        inputs: Dict[str, Any],  # noqa: ARG002 - reserved for unified signature
        outputs: Any,  # noqa: ARG002 - reserved for unified signature
        reference_outputs: Any,  # noqa: ARG002 - reserved for unified signature
        payload: Dict[str, Any],
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Grade tool usage against a set of rules (all/any/none/only), reading the
        normalized tool events on the trace. The legacy single-tool config is
        converted automatically. Scope slicing across turns is applied by the run
        loop; here every event in the trace is one slice."""
        from app.services.tool_usage_rules import (
            evaluate_rules,
            parse_tool_usage_config,
        )

        trace = payload.get("trace") or {}
        events = trace.get("tool_events") or []

        resolve_tool_id, resolve_agent_id, agent_ids, all_tool_ids = build_tool_usage_resolvers(
            payload.get("workflow")
        )
        executed_nodes = set((trace.get("nodes") or {}).keys())
        # Only real agents count as "executed"; other node types can't use tools.
        executed_agent_ids = executed_nodes & agent_ids if agent_ids is not None else executed_nodes
        try:
            parsed = parse_tool_usage_config(
                config,
                resolve_tool_id=resolve_tool_id,
                resolve_agent_id=resolve_agent_id,
                all_tool_ids=all_tool_ids,
            )
        except Exception as exc:  # pylint: disable=broad-except
            return {"key": "tool_used", "score": 0.0, "passed": False,
                    "comment": f"Invalid tool usage config: {exc}"}

        if not parsed.rules:
            return {"key": "tool_used", "score": 0.0, "passed": False,
                    "comment": "No tool usage rules configured."}

        summary = evaluate_rules(parsed.rules, events, executed_agent_ids)
        coverage = summary["coverage"]
        score = summary["score"]
        results = summary["results"]
        # A single rule reports its own reason; multiple rules get the roll-up.
        if len(results) == 1 and results[0].get("comment"):
            comment = results[0]["comment"]
        else:
            comment = (
                f"{coverage['passed']} of {coverage['total']} rule(s) passed; "
                f"{coverage['not_evaluated']} not evaluated."
            )
        return {
            "key": "tool_used",
            "score": score if score is not None else 0.0,
            "passed": summary["passed"],
            "comment": comment,
            "details": results,
        }

    async def _route_taken(
        self,
        *,
        inputs: Dict[str, Any],  # noqa: ARG002 - reserved for unified signature
        outputs: Any,  # noqa: ARG002 - reserved for unified signature
        reference_outputs: Any,  # noqa: ARG002 - reserved for unified signature
        payload: Dict[str, Any],
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Pass when a router node chose the expected branch."""
        expected = _normalize_text(config.get("expected"))
        if not expected:
            return {
                "key": "route_taken",
                "score": False,
                "passed": False,
                "comment": "No expected route configured.",
            }

        routers = (payload.get("trace") or {}).get("nodes_by_type", {}).get("routerNode", [])
        selector = config.get("router") or config.get("node")
        if selector:
            routers = [r for r in routers if _node_matches_selector(r, selector)]

        routes = [
            _normalize_text((r.get("output") or {}).get("route"))
            for r in routers
            if isinstance(r.get("output"), dict)
        ]
        passed = any(_names_equal(route, expected) for route in routes)
        observed = ", ".join(route for route in routes if route) or "none"

        return {
            "key": "route_taken",
            "score": passed,
            "passed": passed,
            "expected": expected,
            "actual": observed,
            "comment": None if passed else f"Expected route {expected!r}, took {routes or 'none'}.",
        }

    async def _action_taken(
        self,
        *,
        inputs: Dict[str, Any],  # noqa: ARG002 - reserved for unified signature
        outputs: Any,  # noqa: ARG002 - reserved for unified signature
        reference_outputs: Any,  # noqa: ARG002 - reserved for unified signature
        payload: Dict[str, Any],
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Pass when a configured side-effect node (by id/label/type) ran successfully."""
        selector = config.get("node")
        node_type = config.get("node_type")
        if not selector and not node_type:
            return {
                "key": "action_taken",
                "score": False,
                "passed": False,
                "comment": "No action node or node_type configured.",
            }

        nodes = (payload.get("trace") or {}).get("nodes") or {}
        should_fire = bool(config.get("should_fire", True))
        target = selector or node_type

        def is_target(node: Dict[str, Any]) -> bool:
            if selector and not _node_matches_selector(node, selector):
                return False
            if node_type and node.get("type") != node_type:
                return False
            return True

        candidates = [node for node in nodes.values() if is_target(node)]
        fired = any(node.get("status") == "success" and not node.get("error") for node in candidates)
        passed = fired if should_fire else not fired
        errored = any(node.get("error") for node in candidates)

        if passed:
            comment = f"{target!r} did not run in this evaluation." if not candidates else None
        elif should_fire:
            comment = f"Expected {target!r} to fire but it did not."
        else:
            comment = f"Expected {target!r} not to fire but it did."

        if not candidates:
            observed = "did not run"
        elif fired:
            observed = "completed"
        elif errored:
            observed = "ran with an error"
        else:
            observed = "did not complete"
        return {
            "key": "action_taken",
            "score": passed,
            "passed": passed,
            "expected": "must complete" if should_fire else "must not complete",
            "actual": observed,
            "comment": comment,
        }

    async def _guardrail_nli(
        self,
        *,
        inputs: Dict[str, Any],  # noqa: ARG002 - not used directly
        outputs: Any,
        reference_outputs: Any,
        payload: Dict[str, Any],
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        answer = _normalize_text(
            _resolve_selector_value(
                config.get("answer_field"), payload=payload, default=outputs
            )
        )
        evidence = _resolve_grading_source(
            config,
            source_key="evidence_source",
            legacy_field_key="evidence_field",
            payload=payload,
        )

        # No evidence to check against → skip, never a false failure.
        if not answer or not evidence:
            return {
                "key": "nli_eval",
                "score": None,
                "passed": False,
                "not_evaluated": True,
                "comment": "Not evaluated: no answer or evidence source to compare.",
            }

        # Transformer inference is blocking CPU work. Keep it off the event loop,
        # but give NLI its own deadline so one slow model becomes a readable metric
        # error and does not discard the other evaluation results for this case.
        try:
            nli_result = await asyncio.wait_for(
                asyncio.to_thread(
                    evaluation_nli_model.score_evidence,
                    answer,
                    evidence,
                    config.get("nli_model_name"),
                ),
                timeout=NLI_EVALUATION_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            return {
                "key": "nli_eval",
                "score": None,
                "passed": False,
                "error": True,
                "comment": (
                    "NLI evaluation error: the model did not respond "
                    "within the allowed time."
                ),
            }

        # Never silently grade only part of an answer. If the safe claim limit is
        # exceeded, report missing coverage instead of producing a misleading score.
        if not getattr(nli_result, "coverage_complete", True):
            return {
                "key": "nli_eval",
                "score": None,
                "passed": False,
                "not_evaluated": True,
                "comment": (
                    "Not evaluated: the answer requires "
                    f"{nli_result.total_claims} claim groups, above the safe "
                    f"limit of {NLI_MAX_ANSWER_CLAIMS}."
                ),
            }

        # The real NLI model could not run. Surface an error instead of silently
        # grading with the word-overlap heuristic.
        if nli_result.model_name is None:
            raise RuntimeError(
                "NLI model unavailable; refusing to fall back to word overlap."
            )

        min_entail_score = float(config.get("min_entail_score", 0.5))
        if not 0.0 <= min_entail_score <= 1.0:
            raise ValueError("NLI entailment threshold must be between 0 and 1.")
        fail_on_contradiction = bool(config.get("fail_on_contradiction", False))
        claim_results = tuple(getattr(nli_result, "claim_results", ()))
        if claim_results:
            unsupported_claims = [
                claim.text
                for claim in claim_results
                if claim.entail_score < min_entail_score
            ]
            contradicted_claims = [
                claim.text
                for claim in claim_results
                if claim.contradiction_score >= 0.5
            ]
            claims_checked = len(claim_results)
        else:
            # Compatibility for mocked/legacy model results without claim metadata.
            unsupported_claims = (
                [answer] if nli_result.entail_score < min_entail_score else []
            )
            contradicted_claims = (
                [answer] if nli_result.contradiction_score >= 0.5 else []
            )
            claims_checked = max(
                int(getattr(nli_result, "claims_evaluated", 0)),
                1,
            )

        supported_claims = claims_checked - len(unsupported_claims)
        contradiction_blocked = (
            fail_on_contradiction and bool(contradicted_claims)
        )
        passed = not unsupported_claims and not contradiction_blocked

        def _claim_previews(claims: list[str]) -> str:
            previews = []
            for claim in claims[:3]:
                normalized = " ".join(claim.split())
                previews.append(
                    f'"{normalized[:157]}..."'
                    if len(normalized) > 160
                    else f'"{normalized}"'
                )
            if len(claims) > 3:
                previews.append(f"and {len(claims) - 3} more")
            return "; ".join(previews)

        comment_parts = [
            f"{supported_claims}/{claims_checked} answer sections supported."
        ]
        if unsupported_claims:
            comment_parts.append(
                f"Unsupported: {_claim_previews(unsupported_claims)}."
            )
        if contradicted_claims:
            suffix = "" if fail_on_contradiction else " (not configured to fail)"
            comment_parts.append(
                "Strong contradiction observed: "
                f"{_claim_previews(contradicted_claims)}{suffix}."
            )
        comment_parts.append(
            f"Evidence chunks checked: {nli_result.chunks_evaluated}; "
            f"model={nli_result.model_name}."
        )
        if nli_result.evidence_truncated:
            comment_parts.append(
                "The evidence exceeded the safety limit and was evenly sampled."
            )

        return {
            "key": "nli_eval",
            "score": nli_result.entail_score,
            "passed": passed,
            "threshold": min_entail_score,
            "comment": " ".join(comment_parts),
            "claims_checked": claims_checked,
            "supported_claims": supported_claims,
            "unsupported_claims": unsupported_claims,
            "contradicted_claims": contradicted_claims,
            "chunks_checked": nli_result.chunks_evaluated,
            "evidence_bounded": nli_result.evidence_truncated,
            "model": nli_result.model_name,
        }

    async def _guardrail_provenance(
        self,
        *,
        inputs: Dict[str, Any],  # noqa: ARG002 - not used directly
        outputs: Any,
        reference_outputs: Any,
        payload: Dict[str, Any],
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        answer = _normalize_text(
            _resolve_selector_value(
                config.get("answer_field"), payload=payload, default=outputs
            )
        )
        context_text = _resolve_grading_source(
            config,
            source_key="context_source",
            legacy_field_key="context_field",
            payload=payload,
        )

        # No grounding source to verify against → skip, never a false failure.
        if not answer or not context_text:
            return {
                "key": "provenance_eval",
                "score": None,
                "passed": False,
                "not_evaluated": True,
                "comment": "Not evaluated: no answer or grounding source to compare.",
            }

        use_llm_judge = bool(
            config.get("use_llm_judge", False)
            or config.get("provenance_mode") == "llm"
        )
        use_embeddings = config.get("provenance_mode") == "embeddings"

        if use_llm_judge:
            score, reason = await self._run_provenance_judge(
                answer=answer,
                context=context_text,
                provider_id=config.get("llm_provider_id"),
                system_prompt_suffix=config.get("llm_judge_system_prompt_suffix") or "",
            )
            if score is None:
                raise RuntimeError("Provenance LLM judge did not return a score.")
        elif use_embeddings:
            # Real embedding similarity; never silently fall back to word overlap.
            score = await self._embedding_provenance_score(answer, context_text, config)
            reason = "Embedding similarity score"
        else:
            score = self._naive_provenance_score(answer, context_text)
            reason = "Word-overlap score"

        min_score = float(config.get("min_score", 0.5))
        if not 0.0 <= min_score <= 1.0:
            raise ValueError("Provenance threshold must be between 0 and 1.")
        passed = score >= min_score

        return {
            "key": "provenance_eval",
            "score": score,
            "passed": passed,
            "threshold": min_score,
            "comment": f"{reason}; score={score:.3f}; threshold={min_score:.3f}",
        }

    async def _embedding_provenance_score(
        self, answer: str, context: str, config: Dict[str, Any]
    ) -> float:
        """Cosine similarity between answer and context using the configured
        embedding provider. Raises on failure so the caller reports an error
        rather than silently degrading to word overlap."""
        embedder = await self._get_embedder(config)
        answer_vec, context_vec = await embedder.embed_texts([answer, context])
        dot = sum(a * b for a, b in zip(answer_vec, context_vec))
        # Vectors are normalized, so the dot product is cosine similarity. Clamp to
        # [0, 1]: unrelated text (cosine near 0) scores near 0 and fails grounding.
        return max(0.0, min(1.0, dot))

    async def _get_embedder(self, config: Dict[str, Any]):
        """Build (and cache per provider/model) the embedder for provenance scoring."""
        from app.core.config.settings import settings
        from app.modules.data.providers.vector.embedding.base import EmbeddingConfig

        embedding_type = config.get("embedding_type", "huggingface")
        model_name = config.get("embedding_model_name", "all-MiniLM-L6-v2")

        if embedding_type == "openai":
            base_url = config.get("embedding_base_url") or None
            embedding_config = EmbeddingConfig(
                type="openai",
                model_name=model_name,
                api_key=config.get("embedding_api_key") or settings.OPENAI_API_KEY,
                base_url=base_url,
                normalize_embeddings=True,
            )
            cache_key = f"openai:{model_name}:{base_url}"
        elif embedding_type == "bedrock":
            model_id = config.get("embedding_model_id")
            region_name = config.get("embedding_region_name")
            embedding_config = EmbeddingConfig(
                type="bedrock",
                model_name="",
                model_id=model_id,
                region_name=region_name,
                normalize_embeddings=True,
            )
            cache_key = f"bedrock:{model_id}:{region_name}"
        else:
            embedding_config = EmbeddingConfig(
                type="huggingface",
                model_name=model_name,
                normalize_embeddings=True,
            )
            cache_key = f"huggingface:{model_name}"

        cached = self._embedder_cache.get(cache_key)
        if cached is not None:
            return cached

        embedder = embedding_config.get()
        # Embedders return False (not raise) on init failure — never cache a broken one.
        if not await embedder.initialize():
            raise RuntimeError(f"Embedding provider {embedding_type!r} failed to initialize.")
        self._embedder_cache[cache_key] = embedder
        return embedder

    def _naive_provenance_score(self, answer: str, context: str) -> float:
        if not answer or not context:
            return 0.0

        answer_tokens = {token.lower() for token in answer.split() if len(token) > 3}
        context_tokens = {token.lower() for token in context.split() if len(token) > 3}

        if not answer_tokens:
            return 0.0

        overlap = answer_tokens & context_tokens
        return len(overlap) / float(len(answer_tokens))

    async def _run_provenance_judge(
        self,
        *,
        answer: str,
        context: str,
        provider_id: str | None = None,
        system_prompt_suffix: str = "",
    ) -> tuple[float | None, str | None]:
        """Grounding-locked judge used by provenance_eval; distinct from the rubric-based _llm_judge."""
        base_instructions = (
            "You are a strict provenance judge. Given a CONTEXT and an ANSWER, "
            "decide whether the answer is fully supported by the context, "
            "partially supported, or not supported."
        )

        extra_instructions = (
            f"\n\nAdditional instructions:\n{system_prompt_suffix.strip()}"
            if system_prompt_suffix.strip()
            else ""
        )

        json_format_requirement = (
            "\n\nReturn ONLY a compact JSON object in this exact format:\n"
            '{"verdict": "supported|partially_supported|unsupported", '
            '"score": 0.0-1.0, "reason": "short explanation"}\n'
            "Do not include any extra text or explanation."
        )

        system_prompt = base_instructions + extra_instructions + json_format_requirement
        user_content = f"CONTEXT:\n{context}\n\nANSWER:\n{answer}\n"
        return await self._invoke_json_judge(
            system_prompt=system_prompt, user_content=user_content, provider_id=provider_id
        )

    async def _invoke_json_judge(
        self,
        *,
        system_prompt: str,
        user_content: str,
        provider_id: str | None = None,
    ) -> tuple[float | None, str | None]:
        """Run an LLM judge returning compact JSON {score, reason}; shared by grounding + rubric judges."""
        llm_provider = injector.get(LLMProvider)
        llm = await llm_provider.get_model(provider_id)
        response = await llm.ainvoke(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_content),
            ]
        )
        raw_content = getattr(response, "content", "")
        if isinstance(raw_content, list):
            raw_content = " ".join(str(part) for part in raw_content)
        return _parse_judge_json(raw_content)

    async def _llm_judge(
        self,
        *,
        inputs: Dict[str, Any],
        outputs: Any,
        reference_outputs: Any,  # noqa: ARG002 - reserved for unified signature
        payload: Dict[str, Any],
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Grade the answer against a user-supplied rubric (any criteria)."""
        rubric = (config.get("rubric") or config.get("instructions") or "").strip()
        if not rubric:
            return {
                "key": "llm_judge",
                "score": False,
                "passed": False,
                "comment": "No rubric configured for llm_judge.",
            }

        try:
            min_score = float(config.get("min_score", 0.5))
        except (TypeError, ValueError):
            min_score = 0.5

        answer = _resolve_selector_value(config.get("answer_field"), payload=payload, default=outputs)
        # Auto-provide the user's turn as the QUESTION so the wizard only needs a
        # rubric; a configured question_field still overrides it.
        default_question = inputs.get("message") if isinstance(inputs, dict) else ""
        question = _resolve_selector_value(
            config.get("question_field"), payload=payload, default=default_question
        )
        answer_text = _normalize_text(answer)
        question_text = _normalize_text(question)

        # New configs use a stable source preset. Saved legacy configs keep their
        # dotted source_field; an unresolved selected source skips instead of
        # silently degrading into a rubric-only judgment.
        source_type = config.get("source_type")
        source_field = config.get("source_field")
        source_required = False
        if isinstance(source_type, str):
            source_required = source_type != "none"
            source_text = _source_text(source_type, payload)
        elif isinstance(source_field, str) and source_field:
            source_required = True
            source_text = _serialize_judge_source(_read_path(payload, source_field))
        else:
            source_text = ""

        if source_required and not source_text:
            return {
                "key": "llm_judge",
                "score": None,
                "passed": False,
                "not_evaluated": True,
                "comment": "Not evaluated: the selected grounding source was unavailable.",
            }

        system_prompt = (
            f"{rubric}\n\n"
            "Return ONLY a compact JSON object in this exact format:\n"
            '{"score": 0.0-1.0, "reason": "short explanation"}\n'
            "Do not include any extra text or explanation."
        )
        user_parts = []
        if question_text:
            user_parts.append(f"QUESTION:\n{question_text}")
        if source_text:
            user_parts.append(f"SOURCE:\n{source_text}")
        user_parts.append(f"ANSWER:\n{answer_text}")

        score, reason = await self._invoke_json_judge(
            system_prompt=system_prompt,
            user_content="\n\n".join(user_parts),
            provider_id=config.get("llm_provider_id"),
        )
        # A missing score means the judge output was malformed — our evaluator's
        # problem, not the agent's. Report it as an error, not a failing answer.
        if score is None:
            return {
                "key": "llm_judge",
                "score": None,
                "passed": False,
                "error": True,
                "comment": reason or "LLM judge did not return a usable score.",
            }

        passed = score >= min_score
        return {
            "key": "llm_judge",
            "score": score,
            "passed": passed,
            "threshold": min_score,
            "comment": f"{reason or 'no reason'}; threshold={min_score:.2f}",
        }


@inject
class TestSuiteService:
    """
    Business logic for test suites, cases, runs, and results.
    """

    def __init__(
        self,
        suite_repo: TestSuiteRepository,
        case_repo: TestCaseRepository,
        run_repo: TestRunRepository,
        result_repo: TestResultRepository,
        evaluation_repo: TestEvaluationRepository,
        tool_rule_result_repo: TestToolRuleResultRepository,
        workflow_service: WorkflowService,
        conversation_repo: ConversationRepository,
    ) -> None:
        self.suite_repo = suite_repo
        self.case_repo = case_repo
        self.run_repo = run_repo
        self.result_repo = result_repo
        self.evaluation_repo = evaluation_repo
        self.tool_rule_result_repo = tool_rule_result_repo
        self.workflow_service = workflow_service
        self.conversation_repo = conversation_repo
        self.evaluators = SimpleEvaluatorRegistry()

    # ---- Suites -----------------------------------------------------------

    async def create_suite(self, data: TestSuiteCreate) -> TestSuiteInDB:
        orm = TestSuiteModel(**data.model_dump())
        created = await self.suite_repo.create(orm)
        return TestSuiteInDB.model_validate(created, from_attributes=True)

    async def list_suites(self) -> List[TestSuiteInDB]:
        suites = await self.suite_repo.get_all()
        return [TestSuiteInDB.model_validate(s, from_attributes=True) for s in suites]

    async def get_suite(self, suite_id: UUID) -> TestSuiteInDB:
        suite = await self.suite_repo.get_by_id(suite_id)
        if not suite:
            raise AppException(status_code=404, error_key=ErrorKey.NOT_FOUND)
        return TestSuiteInDB.model_validate(suite, from_attributes=True)

    async def update_suite(self, suite_id: UUID, data: TestSuiteUpdate) -> TestSuiteInDB:
        suite = await self.suite_repo.get_by_id(suite_id)
        if not suite:
            raise AppException(status_code=404, error_key=ErrorKey.NOT_FOUND)

        payload = data.model_dump(exclude_unset=True)
        for key, value in payload.items():
            setattr(suite, key, value)
        updated = await self.suite_repo.update(suite)
        return TestSuiteInDB.model_validate(updated, from_attributes=True)

    async def delete_suite(self, suite_id: UUID) -> None:
        suite = await self.suite_repo.get_by_id(suite_id)
        if not suite:
            raise AppException(status_code=404, error_key=ErrorKey.NOT_FOUND)
        evaluations = await self.evaluation_repo.get_all_for_suite(suite_id)
        for evaluation in evaluations:
            await self.run_repo.soft_delete_all_by_ids(list(evaluation.run_ids or []))
            await self.evaluation_repo.soft_delete(evaluation)
        await self.suite_repo.soft_delete(suite)

    # ---- Cases ------------------------------------------------------------

    async def add_case(self, data: TestCaseCreate) -> TestCaseInDB:
        if not data.suite_id:
            raise AppException(
                status_code=400,
                error_key=ErrorKey.MISSING_PARAMETER,
                error_detail="suite_id is required to create a test case",
            )
        suite = await self.suite_repo.get_by_id(data.suite_id)
        if not suite:
            raise AppException(status_code=404, error_key=ErrorKey.NOT_FOUND)
        orm = TestCaseModel(
            suite_id=data.suite_id,
            input_data=data.input_data,
            expected_output=data.expected_output,
            tags=data.tags,
            weight=data.weight,
            source_conversation_id=data.source_conversation_id,
            turn_index=data.turn_index,
        )
        created = await self.case_repo.create(orm)
        return TestCaseInDB.model_validate(created, from_attributes=True)

    async def list_cases_for_suite(self, suite_id: UUID) -> List[TestCaseInDB]:
        rows = await self.case_repo.get_all_for_suite(suite_id)
        return [TestCaseInDB.model_validate(c, from_attributes=True) for c in rows]

    async def update_case(self, case_id: UUID, data: TestCaseUpdate) -> TestCaseInDB:
        case = await self.case_repo.get_by_id(case_id)
        if not case:
            raise AppException(status_code=404, error_key=ErrorKey.NOT_FOUND)
        payload = data.model_dump(exclude_unset=True)
        for key, value in payload.items():
            setattr(case, key, value)
        updated = await self.case_repo.update(case)
        return TestCaseInDB.model_validate(updated, from_attributes=True)

    async def delete_case(self, case_id: UUID) -> None:
        case = await self.case_repo.get_by_id(case_id)
        if not case:
            raise AppException(status_code=404, error_key=ErrorKey.NOT_FOUND)
        await self.case_repo.delete(case)

    async def import_cases_from_conversation(
        self, suite_id: UUID, conversation_id: UUID, replace: bool = False
    ) -> List[TestCaseInDB]:
        suite = await self.suite_repo.get_by_id(suite_id)
        if not suite:
            raise AppException(status_code=404, error_key=ErrorKey.NOT_FOUND)

        conversation = await self.conversation_repo.fetch_conversation_by_id(
            conversation_id, include_messages=True
        )
        if not conversation:
            raise AppException(status_code=404, error_key=ErrorKey.NOT_FOUND)

        turns = extract_qa_pairs(conversation.messages)
        if not turns:
            raise AppException(
                status_code=400,
                error_key=ErrorKey.TRANSCRIPT_EMPTY,
                error_detail="Conversation has no question/answer turns to import",
            )

        # Replacing the suite wipes every conversation; otherwise re-importing the
        # same conversation replaces only its own turns, keeping the append idempotent.
        if replace:
            await self.case_repo.soft_delete_all_for_suite(suite_id, commit=False)
        else:
            await self.case_repo.soft_delete_for_conversation(
                suite_id, conversation_id, commit=False
            )

        cases = [
            TestCaseModel(
                suite_id=suite_id,
                source_conversation_id=conversation_id,
                turn_index=turn_index,
                input_data={"message": question},
                expected_output={"value": answer},
                tags=["imported"],
            )
            for turn_index, (question, answer) in enumerate(turns)
        ]
        created = await self.case_repo.create_many(cases)
        return [TestCaseInDB.model_validate(c, from_attributes=True) for c in created]

    async def remove_conversation_from_suite(
        self, suite_id: UUID, conversation_id: UUID
    ) -> None:
        """Soft-delete the cases imported from one conversation into a suite."""
        suite = await self.suite_repo.get_by_id(suite_id)
        if not suite:
            raise AppException(status_code=404, error_key=ErrorKey.NOT_FOUND)
        await self.case_repo.soft_delete_for_conversation(suite_id, conversation_id)

    # ---- Runs -------------------------------------------------------------

    async def create_run(self, suite_id: UUID, data: TestRunCreate) -> TestRunInDB:
        """
        Validate the suite/workflow and create a TestRun with status ``queued``.
        Does NOT execute the run — the caller is responsible for dispatching
        the background task.
        """
        suite = await self.suite_repo.get_by_id(suite_id)
        if not suite:
            raise AppException(status_code=404, error_key=ErrorKey.NOT_FOUND)

        target_workflow_id = data.workflow_id or suite.workflow_id
        if not target_workflow_id:
            raise AppException(
                status_code=400,
                error_key=ErrorKey.MISSING_PARAMETER,
                error_detail=(
                    "workflow_id is required to start a run when dataset "
                    "does not define a default workflow"
                ),
            )
        workflow: WorkflowInDB = await self.workflow_service.get_by_id(
            UUID(str(target_workflow_id))
        )

        run = TestRunModel(
            suite_id=suite.id,
            workflow_id=workflow.id,
            status="queued",
            techniques=list(data.techniques),
            summary_metrics=None,
        )

        created = await self.run_repo.create(run)
        return TestRunInDB.model_validate(created, from_attributes=True)

    async def _fail_run(self, run: TestRunModel, error: str) -> None:
        """Move a run to the terminal failed state and notify the user."""
        run.status = "failed"
        run.summary_metrics = {"error": error}
        await self.run_repo.update(run)
        emit_notification(
            socket_connection_manager=injector.get(SocketConnectionManager),
            tenant_id=get_tenant_context(),
            payload=notification_payload(
                notification_id=f"workflow_failed:test:{run.id}",
                title="Workflow Run Failed",
                description=f"Test run {str(run.id)[:8]}... failed.",
                level="error",
                action_url="/tests/evaluations",
                entity_kind="test_run",
                entity_id=run.id,
                event_key=f"workflow_failed:test:{run.id}",
            ),
        )

    async def _execute_run(
        self,
        suite: TestSuiteModel,
        workflow: WorkflowInDB,
        run: TestRunModel,
        run_input_metadata: Dict[str, Any] | None = None,
        technique_configs: Dict[str, Dict[str, Any]] | None = None,
    ) -> None:
        """Guarantee a terminal state: any unhandled error marks the run failed."""
        try:
            await self._execute_run_inner(
                suite,
                workflow,
                run,
                run_input_metadata=run_input_metadata,
                technique_configs=technique_configs,
            )
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("Test run %s failed unexpectedly: %s", run.id, exc)
            if run.status not in ("completed", "failed"):
                await self._fail_run(run, f"Run failed unexpectedly: {exc}")
            raise

    async def _execute_run_inner(
        self,
        suite: TestSuiteModel,
        workflow: WorkflowInDB,
        run: TestRunModel,
        run_input_metadata: Dict[str, Any] | None = None,
        technique_configs: Dict[str, Dict[str, Any]] | None = None,
    ) -> None:
        # Mark running
        run.status = "running"
        await self.run_repo.update(run)

        # Load cases
        cases = await self.list_cases_for_suite(suite.id)
        if not cases:
            await self._fail_run(run, "No test cases in suite")
            return

        # Build workflow config for engine
        workflow_config = {
            "id": str(workflow.id),
            "nodes": workflow.nodes or [],
            "edges": workflow.edges or [],
        }
        engine = WorkflowEngine(workflow_config)

        evaluator_keys = run.techniques or self.evaluators.default_techniques()
        # tool_used is graded once per scope from collected events (not per case),
        # so it is pulled out of the per-case techniques to avoid double counting.
        tool_usage_requested = TOOL_USED_TECHNIQUE in evaluator_keys
        per_case_keys = [k for k in evaluator_keys if k != TOOL_USED_TECHNIQUE]

        per_case_metrics: List[Dict[str, Any]] = []
        status_counts: Dict[str, int] = {}
        case_events: Dict[str, List[Dict[str, Any]]] = {}
        case_executed_agents: Dict[str, set] = {}

        async def record_case_error(
            case: TestCaseInDB, error: str, status: str
        ) -> None:
            status_counts[status] = status_counts.get(status, 0) + 1
            await self.result_repo.create(
                TestResultModel(
                    run_id=run.id,
                    case_id=case.id,
                    actual_output=None,
                    metrics=None,
                    error=error,
                    status=status,
                )
            )

        async def execute_single(case: TestCaseInDB, thread_id: str | None) -> str:
            """Run one turn and report whether it completed, failed, or paused."""
            merged_input: Dict[str, Any] = {}
            if run_input_metadata:
                merged_input.update(run_input_metadata)
            if suite.default_input_metadata:
                merged_input.update(suite.default_input_metadata)
            merged_input.update(case.input_data or {})

            # Applied last so stored run, suite or case metadata cannot point a
            # case at another conversation's memory thread.
            if thread_id:
                merged_input["thread_id"] = thread_id
            else:
                merged_input.pop("thread_id", None)
            # Execution and scoring fail differently: a turn that never ran or never
            # reached memory breaks the thread, while a scoring error does not.
            try:
                state = await asyncio.wait_for(
                    engine.execute_from_node(
                        input_data=merged_input,
                        thread_id=thread_id,
                        persist=bool(thread_id),
                        await_persist=bool(thread_id),
                        usage_context=WorkflowUsageContext(
                            source="test_suite", workflow_id=coerce_uuid(engine.workflow_id)
                        ),
                    ),
                    timeout=CASE_EXECUTION_TIMEOUT_SECONDS,
                )
            except asyncio.TimeoutError:
                logger.error("Test case %s timed out after %ss", case.id, CASE_EXECUTION_TIMEOUT_SECONDS)
                await record_case_error(
                    case,
                    f"Execution timed out after {CASE_EXECUTION_TIMEOUT_SECONDS}s",
                    ResultStatus.EXECUTION_FAILED,
                )
                return "failed"
            except MemoryPersistenceError as exc:
                logger.error("Memory write failed for test case %s: %s", case.id, exc)
                await record_case_error(
                    case,
                    f"Memory write failed, later turns skipped: {exc}",
                    ResultStatus.EXECUTION_FAILED,
                )
                return "failed"
            except Exception as exc:  # pylint: disable=broad-except
                logger.exception("Error executing test case %s: %s", case.id, exc)
                await record_case_error(
                    case, f"Execution failed: {exc}", ResultStatus.EXECUTION_FAILED
                )
                return "failed"

            # The engine reports some failures on the state instead of raising, and
            # a failed run is never written to memory.
            if getattr(state, "status", None) == "failed":
                reason = _failure_reason(state)
                logger.error("Test case %s finished in a failed state: %s", case.id, reason)
                await record_case_error(
                    case, f"Execution failed: {reason}", ResultStatus.EXECUTION_FAILED
                )
                return "failed"

            waiting_for_human = _is_waiting_for_human(state.output)
            try:
                output = state.output
                truncated_output = _truncate_output(output)
                # Capture full workflow execution response in the same shape used
                # elsewhere in the app.
                execution_trace = state.format_state_as_response()
                if tool_usage_requested:
                    node_status = (execution_trace.get("state") or {}).get("nodeExecutionStatus") or {}
                    case_events[str(case.id)] = execution_trace.get("tool_events") or []
                    case_executed_agents[str(case.id)] = set(node_status.keys())
                metrics = await asyncio.wait_for(
                    self.evaluators.evaluate(
                        per_case_keys,
                        inputs=merged_input,
                        outputs=output,
                        reference_outputs=case.expected_output,
                        execution_trace=execution_trace,
                        technique_configs=technique_configs,
                    ),
                    timeout=EVALUATOR_TIMEOUT_SECONDS,
                )
                result = TestResultModel(
                    run_id=run.id,
                    case_id=case.id,
                    actual_output=truncated_output
                    if isinstance(truncated_output, dict)
                    else {"value": truncated_output},
                    execution_trace=execution_trace,
                    metrics=metrics,
                    error=None,
                    status=ResultStatus.SCORED,
                )
                await self.result_repo.create(result)
                per_case_metrics.append(metrics)
                status_counts[ResultStatus.SCORED] = (
                    status_counts.get(ResultStatus.SCORED, 0) + 1
                )
            except Exception as exc:  # pylint: disable=broad-except
                logger.exception("Error scoring test case %s: %s", case.id, exc)
                await record_case_error(
                    case, f"Scoring failed: {exc}", ResultStatus.SCORING_FAILED
                )
            return "waiting_for_human" if waiting_for_human else "completed"

        use_memory = bool((run_input_metadata or {}).get("use_memory"))
        conversations = _group_cases_into_conversations(cases)

        # A fresh thread per conversation per run isolates conversations from each
        # other and stops a run from reading a previous run's memory. Without memory
        # every case runs threadless, so the engine isolates each one.
        for conversation_cases in conversations:
            thread_id = str(uuid4()) if use_memory else None

            # A turn only reaches memory when its input carries a message field.
            # Single-turn cases need no memory, so any input shape is valid there.
            is_multi_turn = bool(thread_id) and len(conversation_cases) > 1

            for position, case in enumerate(conversation_cases):
                # A turn with no message field cannot be written to memory, so every
                # turn after it would replay without its context. An empty message is
                # fine: the field exists and is persisted.
                missing_message = is_multi_turn and "message" not in (case.input_data or {})
                if missing_message:
                    await record_case_error(
                        case,
                        "Skipped: turn has no 'message' field, so it cannot join "
                        "the conversation's memory",
                        ResultStatus.SKIPPED,
                    )
                    turn_outcome = "failed"
                else:
                    turn_outcome = await execute_single(case, thread_id)

                if turn_outcome == "completed":
                    continue

                # Only a shared thread creates a dependency between turns. Without
                # memory an ordinary failure stops nothing. A HIL pause still stops
                # its conversation because later turns do not contain the requested
                # human answer.
                if turn_outcome != "waiting_for_human" and not thread_id:
                    continue

                skip_reason = (
                    "Skipped: an earlier turn is waiting for human input"
                    if turn_outcome == "waiting_for_human"
                    else "Skipped: an earlier turn was not persisted to memory"
                )
                for skipped in conversation_cases[position + 1:]:
                    await record_case_error(
                        skipped,
                        skip_reason,
                        ResultStatus.SKIPPED,
                    )
                break

        # Aggregate metrics. A metric can be scored, an evaluator error, or not
        # evaluated (no source). Only scored metrics count toward pass/fail; the
        # others are surfaced as coverage so a run with skipped checks never
        # reports a misleading 100%.
        summary: Dict[str, Any] = {}
        counts: Dict[str, int] = {}
        evaluated: Dict[str, int] = {}
        sums: Dict[str, float] = {}
        passes: Dict[str, int] = {}
        errors: Dict[str, int] = {}
        not_evaluated: Dict[str, int] = {}

        for metrics in per_case_metrics:
            for key, value in metrics.items():
                counts[key] = counts.get(key, 0) + 1
                if value.get("error"):
                    errors[key] = errors.get(key, 0) + 1
                    continue
                if value.get("not_evaluated"):
                    not_evaluated[key] = not_evaluated.get(key, 0) + 1
                    continue
                evaluated[key] = evaluated.get(key, 0) + 1
                if value.get("passed"):
                    passes[key] = passes.get(key, 0) + 1
                score = value.get("score")
                if isinstance(score, (int, float, bool)):
                    sums[key] = sums.get(key, 0.0) + float(score)

        for key, count in counts.items():
            scored = evaluated.get(key, 0)
            # No scored cases → the metric was not evaluated; leave scores null so
            # it does not read as 0% in health or pass-rate displays.
            avg_score = sums.get(key, 0.0) / scored if scored else None
            accuracy = passes.get(key, 0) / scored if scored else None
            summary[key] = {
                "avg_score": avg_score,
                "accuracy": accuracy,
                "cases": count,
                "evaluated": scored,
                "errors": errors.get(key, 0),
                "not_evaluated": not_evaluated.get(key, 0),
            }

        # Tool Usage: grade rules across their scope from the collected events and
        # persist per-rule results; the summary is computed from those, not per case.
        # Bounded and isolated from the rest of the run — a bug or a stuck DB call
        # here must not leave the whole run stuck in "running" forever.
        if tool_usage_requested:
            try:
                tool_summary = await asyncio.wait_for(
                    self._evaluate_tool_usage(
                        run=run,
                        cases=cases,
                        conversations=conversations,
                        technique_configs=technique_configs,
                        workflow=workflow,
                        case_events=case_events,
                        case_executed_agents=case_executed_agents,
                    ),
                    timeout=60,
                )
                if tool_summary is not None:
                    summary[TOOL_USED_TECHNIQUE] = tool_summary
            except Exception as exc:  # pylint: disable=broad-except
                logger.exception("Tool usage evaluation failed for run %s: %s", run.id, exc)
                summary[TOOL_USED_TECHNIQUE] = {
                    "avg_score": 0.0, "accuracy": 0.0, "cases": 0,
                    "error": "Tool usage evaluation failed or timed out.",
                }

        # Metrics above cover scored cases only. A case can run yet fail scoring, so
        # "executed" and "scored" are counted separately rather than merged.
        scored = status_counts.get(ResultStatus.SCORED, 0)
        scoring_failed = status_counts.get(ResultStatus.SCORING_FAILED, 0)
        summary[RUN_TOTALS_KEY] = {
            "cases": len(cases),
            "executed": scored + scoring_failed,
            "scored": scored,
            "scoring_failed": scoring_failed,
            "execution_failed": status_counts.get(ResultStatus.EXECUTION_FAILED, 0),
            "skipped": status_counts.get(ResultStatus.SKIPPED, 0),
        }

        run.status = "completed"
        run.summary_metrics = summary
        await self.run_repo.update(run)

    async def _evaluate_tool_usage(
        self,
        *,
        run: TestRunModel,
        cases: List[TestCaseInDB],
        conversations: List[List[TestCaseInDB]],
        technique_configs: Dict[str, Dict[str, Any]] | None,
        workflow: WorkflowInDB,
        case_events: Dict[str, List[Dict[str, Any]]],
        case_executed_agents: Dict[str, set],
    ) -> Dict[str, Any] | None:
        """Grade tool-usage rules per scope, persist one result per rule/scope unit,
        and return a summary computed from those results (the canonical source)."""
        from app.services.tool_usage_rules import (
            describe_tool_rule,
            parse_tool_usage_config,
            plan_tool_rule_results,
            summarize_planned_results,
        )

        config = (technique_configs or {}).get(TOOL_USED_TECHNIQUE)
        if not config:
            return None

        # Resolve any legacy display names to graph ids via the full (nested/MCP) catalogue.
        agents = await self._full_agent_catalog(workflow.id)
        resolve_tool_id, resolve_agent_id, agent_ids, all_tool_ids = resolvers_from_agents(agents)
        try:
            parsed = parse_tool_usage_config(
                config,
                resolve_tool_id=resolve_tool_id,
                resolve_agent_id=resolve_agent_id,
                all_tool_ids=all_tool_ids,
            )
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("Invalid tool_used config for run %s: %s", run.id, exc)
            return {
                "avg_score": 0.0, "accuracy": 0.0, "cases": 0, "error": str(exc),
                "coverage": {"passed": 0, "failed": 0, "not_evaluated": 0, "evaluated": 0, "total": 0},
            }

        if not parsed.rules:
            return None

        # Only real agents count as "executed"; a required-tool rule then becomes
        # not_evaluated (rather than failing) when no agent actually ran.
        if agent_ids is not None:
            case_executed_agents = {
                case_id: (executed & agent_ids)
                for case_id, executed in case_executed_agents.items()
            }

        # Describe turns/conversations by id so the scope planner stays ORM-free.
        turns = [
            {
                "id": str(case.id),
                "source_conversation_id": (
                    str(case.source_conversation_id) if case.source_conversation_id else None
                ),
                "turn_index": case.turn_index,
            }
            for case in cases
        ]
        conversation_groups = [[str(case.id) for case in group] for group in conversations]

        planned = plan_tool_rule_results(
            parsed.rules, turns, conversation_groups, case_events, case_executed_agents
        )

        rule_by_id = {rule.id: rule for rule in parsed.rules}
        # Turn index per case so a per-turn result can name the turn it graded.
        turn_index_by_case = {turn["id"]: turn["turn_index"] for turn in turns}

        # Human-readable snapshot captured at run time, so results stay legible even
        # if a tool or agent is later renamed. Labels come from the resolved catalogue.
        agent_labels = {agent["id"]: agent["label"] for agent in agents}
        tool_labels = {
            tool["id"]: tool["label"] for agent in agents for tool in agent["tools"]
        }
        rule_snapshot_by_id = {
            rule.id: self._rule_snapshot(rule, index, agent_labels, tool_labels, describe_tool_rule)
            for index, rule in enumerate(parsed.rules)
        }
        turn_count_by_conv, conv_number_by_id = self._conversation_index(conversations)

        rows = [
            TestToolRuleResultModel(
                run_id=run.id,
                rule_id=entry["rule_id"],
                scope=entry["scope"],
                case_id=entry["case_id"],
                source_conversation_id=entry["source_conversation_id"],
                status=entry["result"]["status"],
                score=self._rule_score(entry["result"]["status"]),
                details={
                    **entry["result"],
                    "rule": rule_by_id[entry["rule_id"]].model_dump(mode="json"),
                    "turn_index": turn_index_by_case.get(entry["case_id"]),
                    **rule_snapshot_by_id[entry["rule_id"]],
                    "target": self._target_snapshot(
                        entry, turn_index_by_case, turn_count_by_conv, conv_number_by_id
                    ),
                    # Label every tool the result mentions (including forbidden/outside
                    # tools) so the UI never has to fall back to a raw id.
                    "tools": self._entry_tool_labels(
                        entry["result"], rule_by_id[entry["rule_id"]].tool_ids, tool_labels
                    ),
                },
            )
            for entry in planned
        ]
        await self.tool_rule_result_repo.create_many(rows)
        return summarize_planned_results(planned)

    @staticmethod
    def _rule_snapshot(rule, index, agent_labels, tool_labels, describe_tool_rule) -> Dict[str, Any]:
        """Readable, rename-proof snapshot of a rule stored with every result.

        Tool labels are attached per-result by ``_entry_tool_labels`` (which also
        covers forbidden/outside tools), so they are not duplicated here.
        """
        agent = (
            {"id": rule.agent_id, "label": agent_labels.get(rule.agent_id, "Unknown agent")}
            if rule.agent_id
            else {"id": None, "label": "Any agent"}
        )
        return {
            "rule_number": index + 1,
            "rule_summary": describe_tool_rule(rule, agent_labels, tool_labels),
            "agent": agent,
        }

    @staticmethod
    def _entry_tool_labels(result: Dict[str, Any], target_ids: List[str], tool_labels: Dict[str, str]) -> Dict[str, Any]:
        """{tool_id: {label}} for every tool this result references, target or not."""
        ids = set(target_ids)
        for key in ("observed_tools", "missing_tools", "failed_tools", "forbidden_tools"):
            ids.update(result.get(key) or [])
        ids.update((result.get("call_counts") or {}).keys())
        return {tool_id: {"label": tool_labels.get(tool_id, tool_id)} for tool_id in ids}

    @staticmethod
    def _conversation_index(conversations: List[List[TestCaseInDB]]):
        """(turn_count_by_conversation_id, conversation_number_by_id) for labelling."""
        turn_count_by_conv: Dict[str, int] = {}
        conv_number_by_id: Dict[str, int] = {}
        for index, group in enumerate(conversations):
            first = group[0] if group else None
            conv_id = str(first.source_conversation_id) if first and first.source_conversation_id else None
            if conv_id:
                turn_count_by_conv[conv_id] = len(group)
                conv_number_by_id[conv_id] = index + 1
        return turn_count_by_conv, conv_number_by_id

    @staticmethod
    def _target_snapshot(entry, turn_index_by_case, turn_count_by_conv, conv_number_by_id) -> Dict[str, Any]:
        """What this result graded: a whole conversation, or a single turn."""
        if entry["scope"] == "conversation":
            conv_id = entry.get("source_conversation_id")
            number = conv_number_by_id.get(conv_id)
            return {
                "type": "conversation",
                "label": f"Conversation {number}" if number else "Conversation",
                "turn_count": turn_count_by_conv.get(conv_id, 1),
            }
        turn_index = turn_index_by_case.get(entry["case_id"])
        return {
            "type": "turn",
            "label": f"Turn {turn_index + 1}" if turn_index is not None else "Turn",
        }

    @staticmethod
    def _rule_score(status: str) -> Optional[float]:
        if status == "passed":
            return 1.0
        if status == "failed":
            return 0.0
        return None

    async def get_runs_by_ids(self, ids: List[str]) -> List[TestRunInDB]:
        rows = await self.run_repo.get_by_ids(ids)
        return [TestRunInDB.model_validate(r, from_attributes=True) for r in rows]

    async def get_run(self, run_id: UUID) -> TestRun:
        run = await self.run_repo.get_by_id(run_id)
        if not run:
            raise AppException(status_code=404, error_key=ErrorKey.NOT_FOUND)
        return TestRun.model_validate(run, from_attributes=True)

    async def list_runs_for_suite(self, suite_id: UUID) -> List[TestRunInDB]:
        rows = await self.run_repo.get_all_for_suite(suite_id)
        return [TestRunInDB.model_validate(r, from_attributes=True) for r in rows]

    async def list_results_for_run(self, run_id: UUID) -> List[TestResultInDB]:
        rows = await self.result_repo.get_all_for_run(run_id)
        return [TestResultInDB.model_validate(r, from_attributes=True) for r in rows]

    async def list_tool_rule_results_for_run(
        self, run_id: UUID
    ) -> List[TestToolRuleResult]:
        rows = await self.tool_rule_result_repo.get_all_for_run(run_id)
        return [TestToolRuleResult.model_validate(r, from_attributes=True) for r in rows]

    # ---- Evaluations -------------------------------------------------------

    async def _effective_workflow_id(self, workflow_id: Any, suite_id: Any) -> Any:
        """The workflow a run will actually use: the evaluation's own, or the
        dataset's default when the evaluation defines none — the same rule the run
        loop applies, so canonicalization validates against the real workflow."""
        if workflow_id:
            return workflow_id
        if not suite_id:
            return None
        suite = await self.suite_repo.get_by_id(suite_id)
        return suite.workflow_id if suite else None

    async def _canonicalize_tool_used_configs(
        self, workflow_id: Any, technique_configs: Dict[str, Any] | None
    ) -> Dict[str, Any] | None:
        """Resolve legacy tool/agent names in a tool_used config to canonical ids
        before it is stored, so names are never persisted as if they were ids."""
        if not technique_configs or TOOL_USED_TECHNIQUE not in technique_configs or not workflow_id:
            return technique_configs
        from app.services.tool_usage_rules import canonicalize_tool_usage_config

        agents = await self._full_agent_catalog(workflow_id)
        resolve_tool_id, resolve_agent_id, _, all_tool_ids = resolvers_from_agents(agents)
        try:
            canonical = canonicalize_tool_usage_config(
                technique_configs[TOOL_USED_TECHNIQUE],
                resolve_tool_id=resolve_tool_id,
                resolve_agent_id=resolve_agent_id,
                all_tool_ids=all_tool_ids,
            )
        except ValueError as exc:
            raise AppException(
                error_key=ErrorKey.TOOL_USAGE_CONFIG_INVALID,
                status_code=400,
                error_detail=str(exc),
            ) from exc
        return {**technique_configs, TOOL_USED_TECHNIQUE: canonical}

    async def create_evaluation(self, data: TestEvaluationCreate) -> TestEvaluationInDB:
        payload = data.model_dump()
        payload["run_ids"] = []
        workflow_id = await self._effective_workflow_id(
            payload.get("workflow_id"), payload.get("suite_id")
        )
        payload["technique_configs"] = await self._canonicalize_tool_used_configs(
            workflow_id, payload.get("technique_configs")
        )
        orm = TestEvaluationModel(**payload)
        created = await self.evaluation_repo.create(orm)
        return TestEvaluationInDB.model_validate(created, from_attributes=True)

    async def list_evaluations(self) -> List[TestEvaluationInDB]:
        rows = await self.evaluation_repo.get_all()
        return [TestEvaluationInDB.model_validate(r, from_attributes=True) for r in rows]

    async def get_evaluation(self, evaluation_id: UUID) -> TestEvaluation:
        row = await self.evaluation_repo.get_by_id(evaluation_id)
        if not row:
            raise AppException(status_code=404, error_key=ErrorKey.NOT_FOUND)
        return TestEvaluation.model_validate(row, from_attributes=True)

    async def update_evaluation(
        self, evaluation_id: UUID, data: TestEvaluationUpdate
    ) -> TestEvaluationInDB:
        row = await self.evaluation_repo.get_by_id(evaluation_id)
        if not row:
            raise AppException(status_code=404, error_key=ErrorKey.NOT_FOUND)
        updates = data.model_dump(exclude_none=True)
        if "technique_configs" in updates:
            # Resolve against the evaluation's *new* dataset/workflow when either is
            # being changed, so validation never uses the old dataset's workflow.
            suite_id = updates.get("suite_id") or row.suite_id
            workflow_id = await self._effective_workflow_id(
                updates.get("workflow_id") or row.workflow_id, suite_id
            )
            updates["technique_configs"] = await self._canonicalize_tool_used_configs(
                workflow_id, updates["technique_configs"]
            )
        for field, value in updates.items():
            setattr(row, field, value)
        updated = await self.evaluation_repo.update(row)
        return TestEvaluationInDB.model_validate(updated, from_attributes=True)

    async def append_run_to_evaluation(
        self, evaluation_id: UUID, run_id: str
    ) -> TestEvaluationInDB:
        row = await self.evaluation_repo.get_by_id(evaluation_id)
        if not row:
            raise AppException(status_code=404, error_key=ErrorKey.NOT_FOUND)
        current: List[str] = list(row.run_ids or [])
        if run_id not in current:
            current.insert(0, run_id)
        row.run_ids = current
        updated = await self.evaluation_repo.update(row)
        return TestEvaluationInDB.model_validate(updated, from_attributes=True)

    async def delete_evaluation(self, evaluation_id: UUID) -> None:
        row = await self.evaluation_repo.get_by_id(evaluation_id)
        if not row:
            raise AppException(status_code=404, error_key=ErrorKey.NOT_FOUND)
        await self.run_repo.soft_delete_all_by_ids(list(row.run_ids or []))
        await self.evaluation_repo.soft_delete(row)

    async def start_workflow_evaluations(
        self,
        workflow_id: UUID,
        dispatch: Callable[
            [TestRunInDB, Optional[Dict[str, Any]], Optional[Dict[str, Any]]], None
        ],
    ) -> List[StartedEvaluationRun]:
        """Queue and dispatch a run for every evaluation targeting this workflow.

        An evaluation targets the workflow either directly (``workflow_id``) or
        through its dataset's default workflow. Each evaluation is created and
        dispatched independently: one failure is reported as ``failed_to_start``
        and does not prevent the rest from running.
        """
        targeted = await self._evaluations_for_workflow(workflow_id)

        results: List[StartedEvaluationRun] = []
        for ev in targeted:
            try:
                run = await self._start_evaluation_run(ev, dispatch)
                results.append(
                    StartedEvaluationRun(
                        evaluation_id=ev.id,
                        run_id=run.id,
                        suite_id=run.suite_id,
                        status=run.status,
                    )
                )
            except Exception:
                logger.exception(
                    "Failed to start evaluation %s for workflow %s", ev.id, workflow_id
                )
                results.append(
                    StartedEvaluationRun(
                        evaluation_id=ev.id,
                        status="failed_to_start",
                        error="Failed to start evaluation.",
                    )
                )
        return results

    async def _evaluations_for_workflow(
        self, workflow_id: UUID
    ) -> List[TestEvaluationModel]:
        """The Run all scope: every evaluation for the workflow (DB-filtered)."""
        return await self.evaluation_repo.get_all_for_workflow(workflow_id)

    async def _walk_workflow_catalog(self, workflow_id: Any) -> Dict[str, List[Dict[str, Any]]]:
        """One cycle-safe walk of a workflow (+ nested) collecting agents, routers and nodes.

        The single catalogue the UI, config canonicalization and run-time grading all
        consume, so a nested or MCP tool shown in the UI resolves everywhere it is
        used — never rejected as unknown, never treated as a non-agent node.
        """
        from app.services.tool_catalog import (
            nested_workflow_refs,
            resolve_action_nodes,
            resolve_agents,
            resolve_routers,
        )

        agents: List[Dict[str, Any]] = []
        routers: List[Dict[str, Any]] = []
        action_nodes: List[Dict[str, Any]] = []
        visited: set[str] = set()

        async def walk(current_id: str, path: List[str]) -> None:
            if current_id in visited:
                return
            visited.add(current_id)
            try:
                workflow = await self.workflow_service.get_by_id(UUID(str(current_id)))
            except Exception:  # pylint: disable=broad-except
                return
            graph = {
                "id": str(workflow.id),
                "nodes": workflow.nodes or [],
                "edges": workflow.edges or [],
            }
            agents.extend(resolve_agents(graph, workflow_path=path))
            routers.extend(resolve_routers(graph, workflow_path=path))
            action_nodes.extend(resolve_action_nodes(graph, workflow_path=path))
            for ref in nested_workflow_refs(graph):
                await walk(ref["workflow_id"], path + [ref["label"]])

        await walk(str(workflow_id), [])
        return {"agents": agents, "routers": routers, "action_nodes": action_nodes}

    async def _full_agent_catalog(self, workflow_id: Any) -> List[Dict[str, Any]]:
        """Agents + tools for a workflow, expanding nested workflows (cycle-safe)."""
        return (await self._walk_workflow_catalog(workflow_id))["agents"]

    async def get_evaluation_tool_catalog(
        self, workflow_id: UUID
    ) -> "EvaluationToolCatalog":
        """Agents, routers and executable nodes for a workflow, expanding nested (cycle-safe)."""
        catalog = await self._walk_workflow_catalog(workflow_id)
        return EvaluationToolCatalog(
            workflow_id=workflow_id,
            agents=catalog["agents"],
            routers=catalog["routers"],
            action_nodes=catalog["action_nodes"],
        )

    async def get_workflow_evaluation_summaries(
        self,
    ) -> List[WorkflowEvaluationSummary]:
        """One row per workflow (and the unassigned bucket): count, health, running."""
        count_rows = await self.evaluation_repo.count_by_effective_workflow()
        pointers = await self.evaluation_repo.get_latest_run_pointers()
        stats_by_workflow = await self._compute_workflow_stats(pointers)
        summaries: List[WorkflowEvaluationSummary] = []
        for workflow_id, count in count_rows:
            health, finished, any_running = stats_by_workflow.get(
                workflow_id, (None, 0, False)
            )
            summaries.append(
                WorkflowEvaluationSummary(
                    workflow_id=workflow_id,
                    eval_count=count,
                    health=health,
                    finished_count=finished,
                    any_running=any_running,
                )
            )
        return summaries

    async def _compute_workflow_stats(
        self,
        pointers: List[Tuple[Optional[UUID], List[str]]],
    ) -> Dict[Optional[UUID], Tuple[Optional[float], int, bool]]:
        """(health, finished_count, any_running) per workflow from latest runs.

        Health is the mean accuracy over evaluations whose latest run has finished,
        counting a failed run as 0. Queued/running runs set ``any_running`` and are
        not scored. Only each evaluation's latest run (``run_ids[0]``) is fetched.
        """
        latest_run_to_workflow: Dict[str, Optional[UUID]] = {}
        for workflow_id, run_ids in pointers:
            if run_ids:
                latest_run_to_workflow[run_ids[0]] = workflow_id
        if not latest_run_to_workflow:
            return {}

        runs = await self.run_repo.get_by_ids(list(latest_run_to_workflow.keys()))
        sums: Dict[Optional[UUID], float] = {}
        counts: Dict[Optional[UUID], int] = {}
        running: Dict[Optional[UUID], bool] = {}
        for run in runs:
            workflow_id = latest_run_to_workflow.get(str(run.id))
            if run.status in ("queued", "running"):
                running[workflow_id] = True
                continue
            if run.status == "failed":
                sums[workflow_id] = sums.get(workflow_id, 0.0)
                counts[workflow_id] = counts.get(workflow_id, 0) + 1
                continue
            if run.status == "completed":
                accuracy = self._run_accuracy(run.summary_metrics)
                if accuracy is None:
                    continue
                sums[workflow_id] = sums.get(workflow_id, 0.0) + accuracy
                counts[workflow_id] = counts.get(workflow_id, 0) + 1

        stats: Dict[Optional[UUID], Tuple[Optional[float], int, bool]] = {}
        for workflow_id in set(counts) | set(running):
            count = counts.get(workflow_id, 0)
            health = sums[workflow_id] / count if count else None
            stats[workflow_id] = (health, count, running.get(workflow_id, False))
        return stats

    async def evaluation_has_active_run(self, evaluation_id: UUID) -> bool:
        """True if this evaluation's latest run is queued or running.

        Used to block edits and deletes while an evaluation is executing.
        """
        row = await self.evaluation_repo.get_by_id(evaluation_id)
        if not row or not row.run_ids:
            return False
        runs = await self.run_repo.get_by_ids([row.run_ids[0]])
        return any(run.status in ("queued", "running") for run in runs)

    async def workflow_has_active_run(self, workflow_id: Optional[UUID]) -> bool:
        """True if any evaluation in the workflow has a queued/running latest run."""
        pointer_lists = await self.evaluation_repo.get_run_pointers_for_workflow(
            workflow_id
        )
        latest_run_ids = [run_ids[0] for run_ids in pointer_lists if run_ids]
        if not latest_run_ids:
            return False
        runs = await self.run_repo.get_by_ids(latest_run_ids)
        return any(run.status in ("queued", "running") for run in runs)

    @staticmethod
    def _run_accuracy(summary_metrics: Optional[Dict[str, Any]]) -> Optional[float]:
        """Mean accuracy across a run's metrics, matching the per-row display."""
        if not summary_metrics:
            return None
        accuracies = [
            metric["accuracy"]
            for metric in summary_metrics.values()
            if isinstance(metric, dict)
            and isinstance(metric.get("accuracy"), (int, float))
            and not isinstance(metric.get("accuracy"), bool)
        ]
        if not accuracies:
            return None
        return sum(accuracies) / len(accuracies)

    async def list_workflow_evaluations(
        self,
        workflow_id: Optional[UUID],
        page: int,
        page_size: int,
        search: Optional[str] = None,
    ) -> PaginatedEvaluations:
        """One page of a workflow's evaluations (``workflow_id=None`` = unassigned).

        Filtering, search and pagination run in the database, so only the
        requested page is loaded.
        """
        page = max(page, 1)
        page_size = max(1, min(page_size, 100))
        offset = (page - 1) * page_size
        rows = await self.evaluation_repo.get_page_for_workflow(
            workflow_id, offset, page_size, search
        )
        total = await self.evaluation_repo.count_for_workflow(workflow_id, search)
        total_unfiltered = (
            total
            if not (search and search.strip())
            else await self.evaluation_repo.count_for_workflow(workflow_id, None)
        )
        any_running = await self.workflow_has_active_run(workflow_id)
        return PaginatedEvaluations(
            items=[
                TestEvaluationInDB.model_validate(row, from_attributes=True)
                for row in rows
            ],
            total=total,
            total_unfiltered=total_unfiltered,
            page=page,
            page_size=page_size,
            any_running=any_running,
        )

    async def _start_evaluation_run(
        self,
        ev: TestEvaluationModel,
        dispatch: Callable[
            [TestRunInDB, Optional[Dict[str, Any]], Optional[Dict[str, Any]]], None
        ],
    ) -> TestRunInDB:
        """Create, record and dispatch a single evaluation run.

        Create, attach and dispatch are treated as one unit: if attaching or
        dispatching fails after the run is created, the run is marked ``failed``
        so it is never left stranded in ``queued`` while the caller reports the
        evaluation as failed to start.
        """
        # Threads are generated per conversation during execution; a run-wide one
        # would merge every conversation into a single memory thread.
        input_metadata = dict(ev.input_metadata or {})
        input_metadata.pop("thread_id", None)
        data = TestRunCreate(
            techniques=list(ev.techniques or []),
            technique_configs=ev.technique_configs or None,
            workflow_id=ev.workflow_id,
            input_metadata=input_metadata or None,
        )
        run = await self.create_run(ev.suite_id, data)
        try:
            await self.append_run_to_evaluation(ev.id, str(run.id))
            dispatch(run, input_metadata or None, ev.technique_configs or None)
        except Exception:
            await self._mark_run_failed_to_start(run.id)
            raise
        return run

    async def _mark_run_failed_to_start(self, run_id: UUID) -> None:
        """Flip a still-queued run to ``failed`` so it is not left dangling."""
        try:
            row = await self.run_repo.get_by_id(run_id)
            if row and row.status == "queued":
                row.status = "failed"
                row.summary_metrics = {"error": "Failed to dispatch run"}
                await self.run_repo.update(row)
        except Exception:
            logger.exception("Could not mark run %s as failed after start error", run_id)
