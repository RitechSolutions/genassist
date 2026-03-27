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
            "nli_eval": self._guardrail_nli,
            "provenance_eval": self._guardrail_provenance,
        }

    def available(self) -> List[str]:
        return sorted(self._evaluators.keys())

    async def evaluate(
        self,
        techniques: Iterable[str],
        *,
        inputs: Dict[str, Any],
        outputs: Any,
        reference_outputs: Any,
        technique_configs: Dict[str, Dict[str, Any]] | None = None,
    ) -> Dict[str, Dict[str, Any]]:
        results: Dict[str, Dict[str, Any]] = {}
        payload = {
            "inputs": inputs,
            "outputs": outputs,
            "reference_outputs": reference_outputs,
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
            llm_score, llm_reason = await self._run_llm_judge(
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

    async def _run_llm_judge(
        self,
        *,
        answer: str,
        context: str,
        provider_id: str | None = None,
        system_prompt_suffix: str = "",
    ) -> tuple[float | None, str | None]:
        llm_provider = injector.get(LLMProvider)
        llm = await llm_provider.get_model(provider_id)

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
        response = await llm.ainvoke(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"CONTEXT:\n{context}\n\nANSWER:\n{answer}\n"),
            ]
        )
        raw_content = getattr(response, "content", "")
        if isinstance(raw_content, list):
            raw_content = " ".join(str(part) for part in raw_content)

        try:
            parsed = json.loads(raw_content)
            score = float(parsed.get("score", 0.0))
            score = max(0.0, min(1.0, score))
            reason = str(parsed.get("reason", "")).strip() or None
            return score, reason
        except (ValueError, TypeError, json.JSONDecodeError):
            return None, "LLM judge response could not be parsed"


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
        if await self.result_repo.exists_for_suite(suite_id):
            raise AppException(status_code=409, error_key=ErrorKey.TEST_CASES_HAVE_RESULTS)
        await self.suite_repo.delete(suite)

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
            if await self.result_repo.exists_for_suite(suite_id):
                raise AppException(status_code=409, error_key=ErrorKey.TEST_CASES_HAVE_RESULTS)
            await self.case_repo.delete_all_for_suite(suite_id)

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

    async def start_run(self, suite_id: UUID, data: TestRunCreate) -> TestRunInDB:
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

        # Fire-and-forget async execution; in the current context we execute inline
        await self._execute_run(
            suite,
            workflow,
            created,
            run_input_metadata=data.input_metadata,
            technique_configs=data.technique_configs,
        )
        refreshed = await self.run_repo.get_by_id(UUID(str(created.id)))
        return TestRunInDB.model_validate(refreshed, from_attributes=True)  # type: ignore[arg-type]

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
            return

        # Build workflow config for engine
        workflow_config = {
            "id": str(workflow.id),
            "nodes": workflow.nodes or [],
            "edges": workflow.edges or [],
        }
        engine = WorkflowEngine(workflow_config)

        evaluator_keys = run.techniques or self.evaluators.available()

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
        await self.evaluation_repo.delete(row)

