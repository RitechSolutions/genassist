import logging
import json
from typing import Any, Dict, Iterable, List
from uuid import UUID

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
)
from app.modules.workflow.engine.nodes.local_nli_model import local_nli_model
from app.modules.workflow.engine.workflow_engine import WorkflowEngine
from app.modules.workflow.llm.provider import LLMProvider
from app.core.utils.transcript_utils import extract_qa_pairs
from app.repositories.conversations import ConversationRepository
from app.repositories.test_suite import (
    TestSuiteRepository,
    TestCaseRepository,
    TestRunRepository,
    TestResultRepository,
    TestEvaluationRepository,
)
from app.schemas.test_suite import (
    ImportCasesFromConversationRequest,
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
    TestSuiteCreate,
    TestSuiteUpdate,
    TestSuiteInDB,
)
from app.schemas.workflow import WorkflowInDB
from app.services.workflow import WorkflowService
from app.core.tenant_scope import get_tenant_context
from app.dependencies.injector import injector
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


def _names_equal(first: Any, second: Any) -> bool:
    return _normalize_text(first).lower() == _normalize_text(second).lower()


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
    for entry in nodes.values():
        if entry.get("error"):
            errors.append({"node": entry["id"], "error": entry["error"]})
        for call in _extract_tool_calls(entry["output"]):
            tools.append({"node": entry["id"], **call})
        retrieval = _extract_retrieval(entry["type"], entry["output"])
        if retrieval is not None:
            retrievals.append({"node": entry["id"], "label": entry["label"], **retrieval})

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
    }


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
        self._evaluators = {
            "exact_match": self._exact_match,
            "contains": self._contains,
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
    ) -> Dict[str, Dict[str, Any]]:
        results: Dict[str, Dict[str, Any]] = {}
        payload = {
            "inputs": inputs,
            "outputs": outputs,
            "reference_outputs": reference_outputs,
            "trace": _build_grading_context(execution_trace),
        }
        for key in techniques:
            fn = self._evaluators.get(key)
            if not fn:
                continue
            try:
                result = await fn(
                    inputs=inputs,
                    outputs=outputs,
                    reference_outputs=reference_outputs,
                    payload=payload,
                    config=(technique_configs or {}).get(key, {}),
                )
                results[result["key"]] = result
            except Exception as exc:  # pylint: disable=broad-except
                logger.exception("Error running evaluator %s: %s", key, exc)
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
        passed = bool(actual and expected and expected in actual)
        return {
            "key": "contains",
            "score": passed,
            "passed": passed,
            "comment": None if passed else "Expected text not found in output.",
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
        """Pass when the agent called the expected tool, optionally with matching args.
        Set should_call=False to assert the tool (or any tool, if unset) was NOT called."""
        tools = (payload.get("trace") or {}).get("tools") or []
        called_names = [tool.get("name") for tool in tools if tool.get("name")]
        expected = config.get("tool")
        expected_args = config.get("expected_args") or {}
        should_call = bool(config.get("should_call", True))

        matches = [t for t in tools if not expected or _names_equal(t.get("name"), expected)]

        if not should_call:
            passed = not matches
            target = expected or "any tool"
            comment = None if passed else f"Expected {target!r} not to be called, but it was (called: {called_names})."
            return {"key": "tool_used", "score": passed, "passed": passed, "comment": comment}

        if not matches:
            comment = (
                f"Tool {expected!r} not called (called: {called_names or 'none'})."
                if expected else "No tool was called."
            )
            return {"key": "tool_used", "score": False, "passed": False, "comment": comment}

        if expected_args:
            passed = any(_args_superset_match(call.get("args"), expected_args) for call in matches)
            comment = None if passed else f"No matching call had expected args {expected_args!r}."
        else:
            passed = True
            comment = None

        return {"key": "tool_used", "score": passed, "passed": passed, "comment": comment}

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
            routers = [r for r in routers if r.get("id") == selector or r.get("label") == selector]

        routes = [
            _normalize_text((r.get("output") or {}).get("route"))
            for r in routers
            if isinstance(r.get("output"), dict)
        ]
        passed = any(_names_equal(route, expected) for route in routes)

        return {
            "key": "route_taken",
            "score": passed,
            "passed": passed,
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
            if selector and node.get("id") != selector and node.get("label") != selector:
                return False
            if node_type and node.get("type") != node_type:
                return False
            return True

        candidates = [node for node in nodes.values() if is_target(node)]
        fired = any(node.get("status") == "success" and not node.get("error") for node in candidates)
        passed = fired if should_fire else not fired

        if passed:
            comment = f"{target!r} did not run in this evaluation." if not candidates else None
        elif should_fire:
            comment = f"Expected {target!r} to fire but it did not."
        else:
            comment = f"Expected {target!r} not to fire but it did."
        return {"key": "action_taken", "score": passed, "passed": passed, "comment": comment}

    async def _guardrail_nli(
        self,
        *,
        inputs: Dict[str, Any],  # noqa: ARG002 - not used directly
        outputs: Any,
        reference_outputs: Any,
        payload: Dict[str, Any],
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        default_answer = outputs
        default_evidence = reference_outputs

        answer = _resolve_selector_value(
            config.get("answer_field"), payload=payload, default=default_answer
        )
        evidence = _resolve_selector_value(
            config.get("evidence_field"), payload=payload, default=default_evidence
        )

        entail_score, contradiction_score, verdict = local_nli_model.score(
            answer=_normalize_text(answer),
            evidence=_normalize_text(evidence),
            model_name=config.get("nli_model_name"),
        )
        min_entail_score = float(config.get("min_entail_score", 0.5))
        fail_on_contradiction = bool(config.get("fail_on_contradiction", False))

        if verdict == "entails" and entail_score < min_entail_score:
            verdict = "unknown"

        passed = verdict == "entails"
        if verdict == "contradicts" and fail_on_contradiction:
            passed = False

        return {
            "key": "nli_eval",
            "score": entail_score,
            "passed": passed,
            "comment": (
                f"verdict={verdict}, contradiction_score={contradiction_score:.3f}, "
                f"threshold={min_entail_score:.3f}"
            ),
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
        default_answer = outputs
        default_context = reference_outputs

        answer = _resolve_selector_value(
            config.get("answer_field"), payload=payload, default=default_answer
        )
        context_text = _resolve_selector_value(
            config.get("context_field"),
            payload=payload,
            default=default_context,
        )

        heuristic_score = self._naive_provenance_score(
            _normalize_text(answer), _normalize_text(context_text)
        )
        score = heuristic_score
        reason = "Heuristic overlap score"
        use_llm_judge = bool(
            config.get("use_llm_judge", False)
            or config.get("provenance_mode") == "llm"
        )

        if use_llm_judge:
            llm_score, llm_reason = await self._run_provenance_judge(
                answer=_normalize_text(answer),
                context=_normalize_text(context_text),
                provider_id=config.get("llm_provider_id"),
                system_prompt_suffix=config.get("llm_judge_system_prompt_suffix") or "",
            )
            if llm_score is not None:
                score = llm_score
            if llm_reason:
                reason = llm_reason

        min_score = float(config.get("min_score", 0.5))
        fail_on_violation = bool(config.get("fail_on_violation", False))
        passed = score >= min_score
        if fail_on_violation and not passed:
            passed = False

        return {
            "key": "provenance_eval",
            "score": score,
            "passed": passed,
            "comment": (
                f"{reason}; heuristic_score={heuristic_score:.3f}; threshold={min_score:.3f}"
            ),
        }

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

        try:
            parsed = json.loads(raw_content)
            if not isinstance(parsed, dict):
                return None, "LLM judge response was not a JSON object"
            score = float(parsed.get("score", 0.0))
            score = max(0.0, min(1.0, score))
            reason = str(parsed.get("reason", "")).strip() or None
            return score, reason
        except (ValueError, TypeError, json.JSONDecodeError):
            return None, "LLM judge response could not be parsed"

    async def _llm_judge(
        self,
        *,
        inputs: Dict[str, Any],  # noqa: ARG002 - question sourced via question_field
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
        question = _resolve_selector_value(config.get("question_field"), payload=payload, default="")
        source_field = config.get("source_field")
        source = _read_path(payload, source_field) if source_field else None
        answer_text = _normalize_text(answer)
        question_text = _normalize_text(question)
        source_text = _serialize_judge_source(source)

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
        if score is None:
            return {
                "key": "llm_judge",
                "score": 0.0,
                "passed": False,
                "comment": reason or "LLM judge failed.",
            }

        passed = score >= min_score
        return {
            "key": "llm_judge",
            "score": score,
            "passed": passed,
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
        workflow_service: WorkflowService,
        conversation_repo: ConversationRepository,
    ) -> None:
        self.suite_repo = suite_repo
        self.case_repo = case_repo
        self.run_repo = run_repo
        self.result_repo = result_repo
        self.evaluation_repo = evaluation_repo
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

        if replace:
            await self.case_repo.soft_delete_all_for_suite(suite_id)

        created: List[TestCaseInDB] = []
        for question, answer in extract_qa_pairs(conversation.messages):
            orm = TestCaseModel(
                suite_id=suite_id,
                input_data={"message": question},
                expected_output={"value": answer},
                tags=["imported"],
            )
            case = await self.case_repo.create(orm)
            created.append(TestCaseInDB.model_validate(case, from_attributes=True))

        return created

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

    async def _execute_run(
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
            run.status = "failed"
            run.summary_metrics = {"error": "No test cases in suite"}
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
            return

        # Build workflow config for engine
        workflow_config = {
            "id": str(workflow.id),
            "nodes": workflow.nodes or [],
            "edges": workflow.edges or [],
        }
        engine = WorkflowEngine(workflow_config)

        evaluator_keys = run.techniques or self.evaluators.default_techniques()

        per_case_metrics: List[Dict[str, Any]] = []

        async def execute_single(case: TestCaseInDB) -> None:
            merged_input: Dict[str, Any] = {}
            if run_input_metadata:
                merged_input.update(run_input_metadata)
            if suite.default_input_metadata:
                merged_input.update(suite.default_input_metadata)
            merged_input.update(case.input_data or {})
            try:
                state = await engine.execute_from_node(
                    input_data=merged_input,
                    thread_id=merged_input.get("thread_id"),
                )
                output = state.output
                truncated_output = _truncate_output(output)
                # Capture full workflow execution response in the same shape used
                # elsewhere in the app.
                execution_trace = state.format_state_as_response()
                metrics = await self.evaluators.evaluate(
                    evaluator_keys,
                    inputs=merged_input,
                    outputs=output,
                    reference_outputs=case.expected_output,
                    execution_trace=execution_trace,
                    technique_configs=technique_configs,
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
                )
                await self.result_repo.create(result)
                per_case_metrics.append(metrics)
            except Exception as exc:  # pylint: disable=broad-except
                logger.exception("Error executing test case %s: %s", case.id, exc)
                result = TestResultModel(
                    run_id=run.id,
                    case_id=case.id,
                    actual_output=None,
                    metrics=None,
                    error=str(exc),
                )
                await self.result_repo.create(result)

        # Execute sequentially for now to keep DB/session usage simple
        for case in cases:
            await execute_single(case)

        # Aggregate metrics
        summary: Dict[str, Any] = {}
        counts: Dict[str, int] = {}
        sums: Dict[str, float] = {}
        passes: Dict[str, int] = {}

        for metrics in per_case_metrics:
            for key, value in metrics.items():
                score = value.get("score")
                passed = bool(value.get("passed"))
                counts[key] = counts.get(key, 0) + 1
                passes[key] = passes.get(key, 0) + (1 if passed else 0)
                if isinstance(score, (int, float, bool)):
                    sums[key] = sums.get(key, 0.0) + float(score)

        for key, count in counts.items():
            avg_score = sums.get(key, 0.0) / count if count else 0.0
            accuracy = passes.get(key, 0) / count if count else 0.0
            summary[key] = {
                "avg_score": avg_score,
                "accuracy": accuracy,
                "cases": count,
            }

        run.status = "completed"
        run.summary_metrics = summary
        await self.run_repo.update(run)

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

    # ---- Evaluations -------------------------------------------------------

    async def create_evaluation(self, data: TestEvaluationCreate) -> TestEvaluationInDB:
        payload = data.model_dump()
        payload["run_ids"] = []
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
        for field, value in data.model_dump(exclude_none=True).items():
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

