import asyncio
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Awaitable, Dict, List, Optional, Tuple
from uuid import UUID, uuid4

from injector import inject
from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import DEFAULT_NLI_MODEL
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.utils.date_time_utils import utc_now
from app.core.utils.llm_json import parse_json_object_reply
from app.core.utils.llm_usage_utils import extract_usage_from_aimessage
from app.core.utils.uuid_utils import coerce_uuid
from app.db.models.prompt_editor import PromptVersionModel
from app.db.models.test_suite import TestSuiteModel
from app.modules.workflow.prompt_fields import (
    LEGACY_BUCKET_FOR_NODE_TYPE,
    LEGACY_SHARED_NODE_IDS,
    PromptFieldSpec,
    get_spec,
)
from app.repositories.prompt_editor import PromptConfigRepository, PromptVersionRepository
from app.repositories.test_suite import TestCaseRepository, TestSuiteRepository
from app.repositories.workflow import WorkflowRepository
from app.schemas.llm import LlmProviderRead
from app.schemas.prompt_editor import (
    MAX_ACTUAL_CHARS,
    MAX_PROMPT_CONTENT,
    CaseSplit,
    FailedCaseRef,
    LegacyHistoryRead,
    PromptConfigRead,
    PromptEvalCaseResult,
    PromptEvalRequest,
    PromptEvalResponse,
    PromptEvalSummary,
    PromptHistoryRead,
    PromptOptimizeRequest,
    PromptOptimizeResponse,
    PromptRunProvenance,
    PromptVersionCreate,
    PromptVersionRead,
)
from app.services.evaluation_nli import evaluation_nli_model
from app.services.evaluation_text import normalize_text
from app.services.prompt_editor_evaluators import (
    describe_expectations,
    reject_unsupported_techniques,
    validate_prompt_check_techniques,
)

logger = logging.getLogger(__name__)

# Timeouts sum to 100s (no grounding) / 110s (with grounding)
# Margin under SPA's 120s axios timeout. Phases may overrun during cancellation
PROMPT_CHECK_CONCURRENCY = 4
PROMPT_CHECK_PREPARE_SECONDS = 10
PROMPT_CHECK_MODEL_BUDGET_SECONDS = 70
PROMPT_CHECK_MODEL_BUDGET_WITH_NLI = 50
PROMPT_CHECK_SCORE_BUDGET_SECONDS = 30
PROMPT_CHECK_METERING_SECONDS = 20
PROMPT_CHECK_CALL_TIMEOUT_SECONDS = 45
OPTIMIZE_CALL_TIMEOUT_SECONDS = 80
MAX_OPTIMIZE_FAILED = 10
MAX_OPTIMIZE_FAILED_ACTUAL_CHARS = 4_000
MAX_OPTIMIZE_EXAMPLES = 20
MAX_OPTIMIZE_EXAMPLE_CHARS = 24_000
MAX_OPTIMIZE_EXAMPLE_SCAN = 60

TRUNCATION_MARKER = " […shortened by the editor]"
_GROUNDING_TECHNIQUE = "nli_eval"
_JSON_TECHNIQUE = "json_match"
# Graded against the case's expectation, so a case without one cannot support them
_EXPECTATION_TECHNIQUES = ("exact_match", "contains", _GROUNDING_TECHNIQUE)

_INTERNAL_FAILURE = "Something went wrong on the server. Check the server logs for details."


class Budget:
    """A wall-clock deadline shared by every task in one phase"""

    def __init__(self, seconds: float) -> None:
        self._deadline = time.monotonic() + seconds

    def remaining(self) -> float:
        return self._deadline - time.monotonic()


@dataclass(frozen=True)
class PreparedCase:
    """Detached values only. Rollback expires all ORM objects at release"""

    id: UUID
    input_data: Any
    expected_output: Any
    input_text: str
    expected_text: str


@dataclass
class PromptUsageRef:

    execution_id: str
    workflow_id: Optional[UUID] = None
    agent_id: Optional[UUID] = None
    entries: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class _CaseRun:
    case: PreparedCase
    position: int
    status: str
    actual: str = ""
    response: Any = None
    error: Optional[str] = None
    budget_cut: bool = False


def _case_input_text(input_data: Any) -> str:
    if isinstance(input_data, dict):
        return str(input_data.get("message", input_data))
    return str(input_data)


def _shortened(text: str, limit: int) -> str:
    """Cut inside the limit so the marker itself cannot breach it"""
    if len(text) <= limit:
        return text
    return text[: limit - len(TRUNCATION_MARKER)] + TRUNCATION_MARKER


def _for_wire(text: str) -> str:
    """input and expected have max_length on response model, so marker must fit inside the bound"""
    return _shortened(text, MAX_ACTUAL_CHARS)


def _not_applicable(technique: str, reason: str) -> Dict[str, Any]:
    return {
        "key": technique,
        "score": None,
        "passed": False,
        "not_applicable": True,
        "comment": f"Not applicable: {reason}.",
    }


def _stale_selection(missing: List[str]) -> AppException:
    """Names at most three of the missing ids, so a whole stale dataset cannot
    push an unbounded list into the error body"""
    shown = ", ".join(missing[:3])
    more = f" and {len(missing) - 3} more" if len(missing) > 3 else ""
    return AppException(
        status_code=400,
        error_key=ErrorKey.PROMPT_CASE_SELECTION_INVALID,
        error_detail=(
            f"Some selected cases are no longer in the dataset ({shown}{more}). "
            "Reload the cases and run again."
        ),
    )


def _scoring_timeout_text(techniques: List[str]) -> str:
    """Failed loads are permanent (operator fix only), not waiting.
    Loading and never-attempted self-resolve"""
    if _GROUNDING_TECHNIQUE in techniques:
        if evaluation_nli_model.load_failed(DEFAULT_NLI_MODEL):
            return "The grounding model could not be loaded on this server. Check the server logs."
        if not evaluation_nli_model.is_loaded(DEFAULT_NLI_MODEL):
            return "The grounding model is still loading on this server. Re-run in a minute."
    return "Scoring timed out."


def _grounding_timed_out(techniques: List[str]) -> Dict[str, Any]:
    return {
        "key": _GROUNDING_TECHNIQUE,
        "score": None,
        "passed": False,
        "error": True,
        "comment": _scoring_timeout_text(techniques),
    }


def _metric_outcome(metric: Dict[str, Any]) -> str:
    if metric.get("not_applicable"):
        return "not_applicable"
    if metric.get("error"):
        return "errored"
    if metric.get("not_evaluated"):
        return "not_evaluated"
    if not isinstance(metric.get("score"), (int, float)):
        return "errored"
    return "scored"


def _case_outcome(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """Per-metric counts, case score, and verdict
    not_applicable = excluded (unsupported check)
    not_evaluated = included but spoils verdict
    """
    counts = {
        "scored_metrics": 0,
        "failed_metrics": 0,
        "errored_metrics": 0,
        "not_evaluated_metrics": 0,
        "not_applicable_metrics": 0,
    }
    scores: List[float] = []
    for metric in metrics.values():
        outcome = _metric_outcome(metric)
        if outcome == "scored":
            counts["scored_metrics"] += 1
            scores.append(float(metric["score"]))
            if not metric.get("passed"):
                counts["failed_metrics"] += 1
        elif outcome == "errored":
            counts["errored_metrics"] += 1
            if metric.get("score") is not None and not metric.get("error"):
                logger.warning("Prompt check: metric %s reported an unusable score", metric.get("key"))
        elif outcome == "not_evaluated":
            counts["not_evaluated_metrics"] += 1
        else:
            counts["not_applicable_metrics"] += 1

    if counts["failed_metrics"]:
        verdict = "failed"
    elif counts["scored_metrics"] >= 1 and not (
        counts["errored_metrics"] or counts["not_evaluated_metrics"]
    ):
        verdict = "passed"
    else:
        verdict = "inconclusive"

    return {
        **counts,
        "case_score": sum(scores) / len(scores) if scores else None,
        "verdict": verdict,
        "passed": verdict == "passed",
    }


def _usage_total(ref: "PromptUsageRef") -> Dict[str, Any]:
    """What the run actually spent. Entries with no usage are counted, not dropped:
    the provider answered, it just did not report tokens"""
    totals = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "responses_without_usage": 0}
    for entry in ref.entries:
        usage = entry.get("usage")
        if not usage:
            totals["responses_without_usage"] += 1
            continue
        for key in ("input_tokens", "output_tokens", "total_tokens"):
            totals[key] += int(usage.get(key) or 0)
    return totals


def _bounded_metrics(metrics: Dict[str, Any]) -> Dict[str, Any]:
    return {
        key: {
            name: _for_wire(value) if isinstance(value, str) else value
            for name, value in metric.items()
        }
        for key, metric in metrics.items()
    }


def _usage_entry(response: Any, call_index: int, purpose: str, provider_id: UUID) -> Dict[str, Any]:
    """usage=None is valid; recorder writes unpriced row. All paid calls counted"""
    usage = extract_usage_from_aimessage(response)
    return {
        "call_index": call_index,
        "provider_id": (usage or {}).get("provider_id") or str(provider_id),
        "purpose": purpose,
        "usage": usage,
    }


def _collect_usage(ref: "PromptUsageRef", runs: List["_CaseRun"], provider_id: UUID) -> None:
    """Response is metered before scoring, so failures don't skip it"""
    for run in runs:
        if run.response is None:
            continue
        ref.entries.append(_usage_entry(run.response, run.position, "prompt_check", provider_id))


def _summarise(rows: List[PromptEvalCaseResult]) -> PromptEvalSummary:
    """Six outcome counts sum to total. Verdict set only for scored cases; others are disjoint"""
    scored_rows = [row for row in rows if row.scored_metrics >= 1]
    case_scores = [row.case_score for row in scored_rows if row.case_score is not None]
    return PromptEvalSummary(
        total=len(rows),
        passed=sum(1 for row in rows if row.verdict == "passed"),
        failed=sum(1 for row in rows if row.verdict == "failed"),
        inconclusive=sum(1 for row in rows if row.verdict == "inconclusive"),
        execution_failed=sum(1 for row in rows if row.status == "execution_failed"),
        scoring_failed=sum(1 for row in rows if row.status == "scoring_failed"),
        skipped=sum(1 for row in rows if row.status == "skipped"),
        scored=len(scored_rows),
        avg_score=sum(case_scores) / len(case_scores) if case_scores else None,
    )


@dataclass(frozen=True)
class ValidatedSplit:

    dev: List[UUID]
    holdout: List[UUID]
    exploratory: bool


def _split_refused(detail: str) -> AppException:
    return AppException(
        status_code=400,
        error_key=ErrorKey.PROMPT_CASE_SELECTION_INVALID,
        error_detail=detail,
    )


def validate_case_split(
    split: Optional[CaseSplit],
    index: List[Tuple[UUID, Optional[UUID], Optional[int]]],
    failed_ids: List[UUID],
) -> ValidatedSplit:
    """Validated against suite index; refused request builds no model.
    Both sides str()-ed to prevent one conversation appearing as two groups"""
    known = {str(entry[0]) for entry in index}
    ordered = [entry[0] for entry in index]

    if any(str(case_id) not in known for case_id in failed_ids):
        raise _split_refused(
            "Some failed cases are no longer in the dataset. Reload the cases and run again."
        )

    if split is None:
        return ValidatedSplit(dev=ordered, holdout=[], exploratory=True)

    holdout = {str(case_id) for case_id in split.holdout_case_ids}
    if holdout - known:
        raise _split_refused(
            "Some hold-out cases are no longer in the dataset. Reload the cases and run again."
        )

    groups: Dict[str, List[str]] = defaultdict(list)
    for case_id, conversation_id, _turn in index:
        groups[str(conversation_id or case_id)].append(str(case_id))
    for members in groups.values():
        held = sum(1 for member in members if member in holdout)
        if 0 < held < len(members):
            raise _split_refused("A conversation is split across the development and hold-out sets.")

    if any(str(case_id) in holdout for case_id in failed_ids):
        raise _split_refused(
            "A failed case is in the hold-out set; only development failures can be sent."
        )

    held_groups = sum(1 for members in groups.values() if members[0] in holdout)
    if held_groups < 2 or len(groups) - held_groups < 2:
        raise _split_refused("Each side of the split needs at least two conversations or cases.")

    return ValidatedSplit(
        dev=[case_id for case_id in ordered if str(case_id) not in holdout],
        holdout=[case_id for case_id in ordered if str(case_id) in holdout],
        exploratory=False,
    )


def _unusable_suggestion(detail: str) -> AppException:
    return AppException(
        status_code=400,
        error_key=ErrorKey.PROMPT_OPTIMIZE_UNUSABLE,
        error_detail=detail,
    )


def _parse_suggestion(text: str) -> Tuple[str, str]:
    """Non-matching envelope refused; never returned as suggestion"""
    envelope = (
        "The model did not return the agreed reply: a single JSON object with an "
        "improved_prompt and an explanation. Try again or pick another provider."
    )
    try:
        parsed = parse_json_object_reply(text)
    except ValueError as exc:
        raise _unusable_suggestion(envelope) from exc

    suggested, explanation = parsed.get("improved_prompt"), parsed.get("explanation")
    if not isinstance(suggested, str) or not isinstance(explanation, str):
        raise _unusable_suggestion(envelope)
    if not suggested.strip():
        raise _unusable_suggestion("The model returned an empty prompt. Try again.")
    if len(suggested) > MAX_PROMPT_CONTENT:
        raise _unusable_suggestion(
            f"The suggested prompt is longer than the {MAX_PROMPT_CONTENT} character limit."
        )
    return suggested, explanation


@dataclass(frozen=True)
class _Examples:
    """What the optimizer was actually shown"""

    gold_text: str
    failed_text: str
    case_ids: List[UUID]
    failure_case_ids: List[UUID]
    truncated: bool


_OPTIMIZE_SYSTEM_PROMPT = (
    "You are an expert prompt engineer. Your task is to improve a system prompt "
    "so that when an LLM uses it, the LLM produces responses that match the "
    "gold dataset expected outputs as closely as possible.\n\n"
    "Rules:\n"
    "- Study each gold dataset pair carefully: the Input is what the user will say, "
    "and the Expected output is what the grader compares the reply against, which is "
    "often a fragment or a reference rather than the whole reply\n"
    "- Rewrite the system prompt so the LLM would naturally produce replies the "
    "grader accepts, following the grading rules where they are given\n"
    "- If there are failed cases, pay special attention to fixing those patterns\n"
    "- Preserve the original intent and domain of the prompt\n"
    "- Be specific: add formatting instructions, tone guidance, or constraints "
    "that align with the gold examples\n"
    "- Return your response as JSON with two fields:\n"
    '  {"improved_prompt": "the full improved prompt text", '
    '"explanation": "brief explanation of what you changed and why"}\n'
    "- Return ONLY the JSON object, no other text"
)


def _optimize_request_text(
    current_prompt: str,
    gold_examples: str,
    failed_section: str,
    instructions: Optional[str],
    grading_rules: str,
) -> str:
    grading = (
        "\n\n## GRADING\n"
        "An expected output is not the ideal reply. Each is checked like this:\n\n" + grading_rules
        if grading_rules
        else ""
    )
    failed = (
        "\n\n## FAILED CASES\n"
        "These cases failed evaluation with the current prompt:\n\n" + failed_section
        if failed_section
        else ""
    )
    extra = f"\n\n## ADDITIONAL INSTRUCTIONS\n{instructions}" if instructions else ""
    return (
        f"## CURRENT SYSTEM PROMPT\n{current_prompt}\n\n"
        f"## GOLD DATASET (Input → Expected Output)\n"
        f"The improved prompt must guide the LLM to produce replies the grader accepts:\n\n"
        f"{gold_examples}"
        f"{grading}"
        f"{failed}"
        f"{extra}"
    )


@dataclass(frozen=True)
class PromptContext:
    """A prompt field matched against the stored workflow graph
    ``node_missing`` = node not in saved workflow (newly added or removed;
    graph can't tell which). ``spec`` is None unless a node type resolved it,
    which for a missing node means the caller supplied a valid one
    """

    workflow_id: UUID
    agent_id: Optional[UUID]
    node_id: str
    prompt_field: str
    node_type: Optional[str]
    node_missing: bool
    spec: Optional[PromptFieldSpec]


@inject
class PromptEditorService:
    def __init__(
        self,
        version_repo: PromptVersionRepository,
        config_repo: PromptConfigRepository,
        suite_repo: TestSuiteRepository,
        case_repo: TestCaseRepository,
        workflow_repo: WorkflowRepository,
        db: AsyncSession,
    ) -> None:
        self.version_repo = version_repo
        self.config_repo = config_repo
        self.suite_repo = suite_repo
        self.case_repo = case_repo
        self.workflow_repo = workflow_repo
        self.db = db
        # Request-scoped, so one provider is resolved once per run for pricing
        self._name_cache: Dict[str, Tuple[str, str]] = {}
        # Lazy import to avoid circular dependency (test_suite imports injector at module level)
        from app.services.test_suite import SimpleEvaluatorRegistry

        self.evaluators = SimpleEvaluatorRegistry()

    # ---- Context -------------------------------------------------------------

    async def _context(
        self,
        workflow_id: UUID,
        node_id: str,
        prompt_field: str,
        *,
        require_live_node: bool,
        requested_node_type: Optional[str] = None,
    ) -> PromptContext:
        """Resolve a prompt field against the stored workflow.
        Reads allow missing nodes so history stays readable after deletion.
        Writes reject nodes not in the saved graph.
        ``requested_node_type`` is read-only; hints at deleted nodes.
        Stored type is authoritative; writes ignore it.
        """
        row = await self.workflow_repo.get_access_row(workflow_id)
        if row is None:
            raise AppException(status_code=404, error_key=ErrorKey.WORKFLOW_NOT_FOUND)

        node = next((n for n in (row.nodes or []) if n.get("id") == node_id), None)
        if node is not None:
            node_type = node.get("type")
            spec = get_spec(node_type, prompt_field) if node_type else None
            if spec is None:
                raise AppException(
                    status_code=400,
                    error_key=ErrorKey.PROMPT_FIELD_NOT_SUPPORTED,
                    error_detail=f"{node_type or 'This node'} has no editable prompt field '{prompt_field}'.",
                )
        else:
            # Hint accepted only when it names a field the editor really supports
            spec = get_spec(requested_node_type, prompt_field) if requested_node_type else None
            node_type = requested_node_type if spec else None
            if require_live_node:
                detail = (
                    "This history belongs to the old shared agent configuration and is read-only. "
                    "Copy a version into the node's own history first."
                    if node_id in LEGACY_SHARED_NODE_IDS
                    else "This node isn't in the saved workflow. If it was just added, save the workflow "
                    "before saving prompt versions or running checks."
                )
                raise AppException(
                    status_code=400,
                    error_key=ErrorKey.PROMPT_CONTEXT_INVALID,
                    error_detail=detail,
                )

        return PromptContext(
            workflow_id=workflow_id,
            agent_id=row.agent_id,
            node_id=node_id,
            prompt_field=prompt_field,
            node_type=node_type,
            node_missing=node is None,
            spec=spec,
        )

    # ---- Versions ------------------------------------------------------------

    async def list_versions(
        self, workflow_id: UUID, node_id: str, prompt_field: str
    ) -> List[PromptVersionRead]:
        """Deprecated for get_history. Kept one release for backward compatibility"""
        rows = await self.version_repo.get_versions_for_context(
            workflow_id, node_id, prompt_field
        )
        return [PromptVersionRead.model_validate(r, from_attributes=True) for r in rows]

    async def get_history(
        self,
        workflow_id: UUID,
        node_id: str,
        prompt_field: str,
        node_type: Optional[str] = None,
    ) -> PromptHistoryRead:
        ctx = await self._context(
            workflow_id,
            node_id,
            prompt_field,
            require_live_node=False,
            requested_node_type=node_type,
        )
        rows = await self.version_repo.get_versions_for_context(
            workflow_id, node_id, prompt_field
        )
        config = await self.config_repo.get_by_context(workflow_id, node_id, prompt_field)

        legacy = None
        bucket = LEGACY_BUCKET_FOR_NODE_TYPE.get(ctx.node_type) if ctx.node_type else None
        # Reading the bucket directly yields its rows (already versions)
        if bucket is not None and bucket != node_id:
            legacy_rows = await self.version_repo.get_versions_for_context(
                workflow_id, bucket, prompt_field
            )
            legacy_config = await self.config_repo.get_by_context(
                workflow_id, bucket, prompt_field
            )
            legacy_suite = legacy_config.gold_suite_id if legacy_config else None
            if legacy_rows or legacy_suite:
                legacy = LegacyHistoryRead(
                    node_id=bucket,
                    versions=[
                        PromptVersionRead.model_validate(r, from_attributes=True)
                        for r in legacy_rows
                    ],
                    gold_suite_id=legacy_suite,
                )

        return PromptHistoryRead(
            versions=[
                PromptVersionRead.model_validate(r, from_attributes=True) for r in rows
            ],
            gold_suite_id=config.gold_suite_id if config else None,
            node_type=ctx.node_type,
            node_missing=ctx.node_missing,
            field_label=ctx.spec.label if ctx.spec else None,
            inline_check_supported=bool(ctx.spec and ctx.spec.inline_check),
            unsupported_reason=ctx.spec.unsupported_reason if ctx.spec else None,
            legacy_shared=legacy,
        )

    async def create_version(
        self,
        workflow_id: UUID,
        node_id: str,
        prompt_field: str,
        data: PromptVersionCreate,
    ) -> PromptVersionRead:
        """Append a version. Labels don't prevent duplicates; same label adds a new row"""
        await self._context(workflow_id, node_id, prompt_field, require_live_node=True)
        try:
            # SAVEPOINT for deactivate+number+insert prevents no-active-version state on race
            async with self.db.begin_nested():
                await self.version_repo.deactivate_all_for_context(
                    workflow_id, node_id, prompt_field
                )
                version_number = await self.version_repo.next_version_number(
                    workflow_id, node_id, prompt_field
                )
                created = await self.version_repo.create(
                    PromptVersionModel(
                        workflow_id=workflow_id,
                        node_id=node_id,
                        prompt_field=prompt_field,
                        version_number=version_number,
                        content=data.content,
                        label=data.label,
                        is_active=True,
                    )
                )
        except IntegrityError as exc:
            if getattr(exc.orig, "sqlstate", None) != "23505":
                raise
            raise AppException(
                status_code=409,
                error_key=ErrorKey.PROMPT_VERSION_CONFLICT,
                error_detail="Another save completed first. Try again.",
            ) from exc
        return PromptVersionRead.model_validate(created, from_attributes=True)

    async def delete_version(self, version_id: UUID) -> None:
        """Scoped to the version only: legacy buckets, removed nodes and
        histories under a retired workflow all stay cleanable."""
        version = await self.version_repo.get_by_id(version_id)
        if not version:
            raise AppException(status_code=404, error_key=ErrorKey.NOT_FOUND)
        await self.version_repo.soft_delete(version)

    # ---- Config / Gold Suite -------------------------------------------------

    async def get_config(
        self, workflow_id: UUID, node_id: str, prompt_field: str
    ) -> PromptConfigRead:
        """Read-only. Returns null id if the context has no row"""
        await self._context(workflow_id, node_id, prompt_field, require_live_node=False)
        config = await self.config_repo.get_by_context(
            workflow_id, node_id, prompt_field
        )
        if config is None:
            return PromptConfigRead(
                workflow_id=workflow_id, node_id=node_id, prompt_field=prompt_field
            )
        return PromptConfigRead.model_validate(config, from_attributes=True)

    async def link_gold_suite(
        self,
        workflow_id: UUID,
        node_id: str,
        prompt_field: str,
        suite_id: Optional[UUID] = None,
        name: Optional[str] = None,
    ) -> PromptConfigRead:
        await self._context(workflow_id, node_id, prompt_field, require_live_node=True)
        config = await self.config_repo.get_or_create(workflow_id, node_id, prompt_field)

        if suite_id:
            suite = await self.suite_repo.get_by_id(suite_id)
            if not suite:
                raise AppException(status_code=404, error_key=ErrorKey.NOT_FOUND)
            config.gold_suite_id = suite_id
        else:
            suite_name = name or f"Gold Dataset - {node_id}/{prompt_field}"
            suite = TestSuiteModel(name=suite_name, workflow_id=workflow_id)
            suite = await self.suite_repo.create(suite)
            config.gold_suite_id = suite.id

        return PromptConfigRead.model_validate(config, from_attributes=True)

    # ---- Evaluate ------------------------------------------------------------

    async def _prepare_context(
        self, workflow_id: UUID, node_id: str, prompt_field: str
    ) -> PromptContext:
        """Shared requirements: node in saved graph, field is runnable.
        Without this gate, prompts reach the model via direct API call."""
        ctx = await self._context(workflow_id, node_id, prompt_field, require_live_node=True)
        if not ctx.spec.inline_check:
            raise AppException(
                status_code=400,
                error_key=ErrorKey.PROMPT_FIELD_NOT_SUPPORTED,
                error_detail=ctx.spec.unsupported_reason,
            )
        return ctx

    async def _select_cases(
        self, suite_id: UUID, request: PromptEvalRequest
    ) -> Tuple[List[PreparedCase], int]:
        """Index is JSONB-free; loads only needed payloads, not all"""
        index = await self.case_repo.get_case_index_for_suite(suite_id)
        if not index:
            raise AppException(
                status_code=400,
                error_key=ErrorKey.MISSING_PARAMETER,
                error_detail="Gold dataset has no cases. Add test cases first.",
            )

        if request.case_ids:
            known = {str(entry[0]) for entry in index}
            missing = [str(case_id) for case_id in request.case_ids if str(case_id) not in known]
            if missing:
                raise _stale_selection(missing)
            selected = list(request.case_ids)
        else:
            # Ordered by the uuid7 primary key, so this is creation order
            selected = [entry[0] for entry in index[: request.max_cases]]

        rows = await self.case_repo.get_cases_by_ids(suite_id, selected)
        by_id = {str(row.id): row for row in rows}
        if request.case_ids:
            # Detect deletions between reads; hold-out run needs the full set
            vanished = [str(case_id) for case_id in selected if str(case_id) not in by_id]
            if vanished:
                raise _stale_selection(vanished)
        cases = [
            PreparedCase(
                id=row.id,
                input_data=row.input_data,
                expected_output=row.expected_output,
                input_text=_case_input_text(row.input_data),
                expected_text=normalize_text(row.expected_output),
            )
            for row in (by_id.get(str(case_id)) for case_id in selected)
            if row is not None
        ]
        return cases, len(index)

    async def _build_model(self, provider: LlmProviderRead, check_id: UUID) -> Any:
        """Release point; report the provider that built the model"""
        from app.dependencies.injector import injector
        from app.modules.workflow.llm.provider import LLMProvider

        try:
            return await injector.get(LLMProvider).get_model_from_provider(provider)
        except AppException:
            raise
        except Exception as exc:
            logger.warning("Prompt check %s: provider build failed", str(check_id)[:8], exc_info=True)
            raise AppException(
                status_code=502,
                error_key=ErrorKey.PROMPT_MODEL_CALL_FAILED,
                error_detail=(
                    "The selected provider could not be initialised. "
                    "Choose another provider or check its configuration."
                ),
            ) from exc
        finally:
            if self.db.in_transaction():
                try:
                    await self.db.rollback()
                except Exception:
                    logger.warning(
                        "Prompt check %s: session rollback after provider build failed",
                        str(check_id)[:8],
                        exc_info=True,
                    )

    async def _prepare_check(
        self, workflow_id: UUID, node_id: str, prompt_field: str, request: PromptEvalRequest, check_id: UUID
    ) -> Tuple[PromptContext, List[PreparedCase], Dict[str, Dict[str, Any]], LlmProviderRead, Any, int]:
        from app.dependencies.injector import injector
        from app.services.llm_providers import LlmProviderService

        ctx = await self._prepare_context(workflow_id, node_id, prompt_field)
        configs = validate_prompt_check_techniques(request.techniques, request.technique_configs)

        config = await self.config_repo.get_by_context(workflow_id, node_id, prompt_field)
        if not config or not config.gold_suite_id:
            raise AppException(
                status_code=400,
                error_key=ErrorKey.MISSING_PARAMETER,
                error_detail="No gold dataset linked to this prompt. Create one first.",
            )
        cases, total_cases = await self._select_cases(config.gold_suite_id, request)

        provider = await injector.get(LlmProviderService).get_by_id(request.provider_id)
        llm = await self._build_model(provider, check_id)
        return ctx, cases, configs, provider, llm, total_cases

    async def _call_model(
        self,
        case: PreparedCase,
        position: int,
        prompt_content: str,
        llm: Any,
        budget: Budget,
        semaphore: asyncio.Semaphore,
        check_id: UUID,
    ) -> _CaseRun:
        async with semaphore:
            remaining = budget.remaining()
            if remaining <= 0:
                return _CaseRun(
                    case=case,
                    position=position,
                    status="skipped",
                    error="Not run: the time budget for this check ran out.",
                )
            call_timeout = min(PROMPT_CHECK_CALL_TIMEOUT_SECONDS, remaining)
            try:
                response = await asyncio.wait_for(
                    llm.ainvoke(
                        [
                            SystemMessage(content=prompt_content),
                            HumanMessage(content=case.input_text),
                        ]
                    ),
                    timeout=call_timeout,
                )
                actual = response.text
            except asyncio.TimeoutError:
                budget_cut = call_timeout < PROMPT_CHECK_CALL_TIMEOUT_SECONDS
                return _CaseRun(
                    case=case, position=position, status="execution_failed",
                    error=(
                        "Cut short: the time budget for this check ran out."
                        if budget_cut
                        else "The model call timed out."
                    ),
                    budget_cut=budget_cut,
                )
            except Exception:
                logger.warning(
                    "Prompt check %s: model call for case %s failed",
                    str(check_id)[:8], position, exc_info=True,
                )
                return _CaseRun(
                    case=case, position=position, status="execution_failed", error=_INTERNAL_FAILURE,
                )
        return _CaseRun(case=case, position=position, status="scored", actual=actual, response=response)

    async def _score(
        self,
        run: _CaseRun,
        request: PromptEvalRequest,
        configs: Dict[str, Dict[str, Any]],
        budget: Optional[Budget],
    ) -> Tuple[Dict[str, Any], bool]:
        """Up to three calls: plain text group, nli_eval, json_match. nli_eval is
        called on its own so its deadline cannot cancel the metrics beside it"""
        case = run.case
        reference = case.expected_output if case.expected_output is not None else case.expected_text
        metrics: Dict[str, Any] = {}
        exhausted = False

        text_ids = [t for t in request.techniques if t != _JSON_TECHNIQUE]
        if case.expected_output is None:
            reason = "the case has no expected output"
        elif not case.expected_text:
            reason = "the expected output is empty"
        else:
            reason = None

        if reason is not None:
            gaps = [
                t for t in text_ids
                if t in _EXPECTATION_TECHNIQUES
                or (t == "field_equals" and "expected" not in configs.get(t, {}))
            ]
            for technique in gaps:
                metrics[technique] = _not_applicable(technique, reason)
            text_ids = [t for t in text_ids if t not in gaps]

        if budget is not None and _GROUNDING_TECHNIQUE in text_ids and budget.remaining() <= 0:
            exhausted = True
            text_ids = [t for t in text_ids if t != _GROUNDING_TECHNIQUE]
            metrics[_GROUNDING_TECHNIQUE] = _grounding_timed_out(request.techniques)

        def _evaluate(technique_ids: List[str]) -> Awaitable[Dict[str, Any]]:
            return self.evaluators.evaluate(
                technique_ids,
                inputs=case.input_data,
                outputs=run.actual,
                reference_outputs=reference,
                technique_configs=configs,
                usage_ref=None,
            )

        plain_ids = [t for t in text_ids if t != _GROUNDING_TECHNIQUE]
        if plain_ids:
            metrics.update(await _evaluate(plain_ids))

        if _GROUNDING_TECHNIQUE in text_ids:
            call = _evaluate([_GROUNDING_TECHNIQUE])
            if budget is not None:
                call = asyncio.wait_for(call, timeout=max(1.0, budget.remaining()))
            try:
                metrics.update(await call)
            except asyncio.TimeoutError:
                exhausted = True
                metrics[_GROUNDING_TECHNIQUE] = _grounding_timed_out(request.techniques)
            self._rewrite_grounding_comment(metrics, request.techniques)

        if _JSON_TECHNIQUE in request.techniques:
            metrics[_JSON_TECHNIQUE] = await self._score_json(case, run.actual, reference, configs)

        return metrics, exhausted

    @staticmethod
    def _rewrite_grounding_comment(metrics: Dict[str, Any], techniques: List[str]) -> None:
        metric = metrics.get(_GROUNDING_TECHNIQUE)
        if metric and metric.get("error") and not evaluation_nli_model.is_loaded(DEFAULT_NLI_MODEL):
            metric["comment"] = _scoring_timeout_text(techniques)

    async def _score_json(
        self, case: PreparedCase, actual: str, reference: Any, configs: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        if case.expected_output is None:
            return _not_applicable(_JSON_TECHNIQUE, "the case has no expected output")
        try:
            parsed = parse_json_object_reply(actual)
        except ValueError:
            return {
                "key": _JSON_TECHNIQUE,
                "score": False,
                "passed": False,
                "comment": "Model output is not a single JSON object.",
            }
        result = await self.evaluators.evaluate(
            [_JSON_TECHNIQUE],
            inputs=case.input_data,
            outputs=parsed,
            reference_outputs=reference,
            technique_configs=configs,
            usage_ref=None,
        )
        metric = result.get(_JSON_TECHNIQUE)
        if metric is None:
            return {
                "key": _JSON_TECHNIQUE,
                "score": None,
                "passed": False,
                "error": True,
                "comment": _INTERNAL_FAILURE,
            }
        if metric.get("not_evaluated") and parsed.get("status") == "awaiting_input":
            metric["comment"] = "Not evaluated: the reply is a human-input envelope, not a final answer."
        return metric

    @staticmethod
    def _row(run: _CaseRun, *, status: str, metrics: Optional[Dict[str, Any]] = None,
             error: Optional[str] = None) -> PromptEvalCaseResult:
        outcome = _case_outcome(metrics) if metrics is not None else {}
        return PromptEvalCaseResult(
            case_id=run.case.id,
            input=_for_wire(run.case.input_text),
            expected=_for_wire(run.case.expected_text),
            actual=run.actual[:MAX_ACTUAL_CHARS],
            actual_truncated=len(run.actual) > MAX_ACTUAL_CHARS,
            status=status,
            error=error,
            metrics=_bounded_metrics(metrics) if metrics else {},
            **outcome,
        )

    async def _persist_usage(self, ref: PromptUsageRef) -> None:
        from app.modules.workflow.engine.llm_usage_tracking import resolve_provider_model
        from app.services.llm_usage_recorder import LlmUsageRecorder

        entries = []
        for collected in ref.entries:
            provider, model = await resolve_provider_model(collected.get("provider_id"), self._name_cache)
            entries.append(
                {
                    **collected,
                    "provider": provider,
                    "model": model,
                    "llm_provider_id": coerce_uuid(collected.get("provider_id")),
                }
            )
        await LlmUsageRecorder().record_evaluation_calls(
            ref.execution_id,
            entries,
            workflow_id=ref.workflow_id,
            agent_id=ref.agent_id,
            source="prompt_editor",
        )

    async def _flush_usage(self, ref: PromptUsageRef) -> bool:
        """One hand-over per run (per-case would exceed budget). Returns failure status.
        False = handed over, not confirmed written"""
        if not ref.entries:
            return False
        try:
            await asyncio.wait_for(self._persist_usage(ref), PROMPT_CHECK_METERING_SECONDS)
        except Exception:
            logger.warning("Recording prompt-editor LLM usage failed", exc_info=True)
            return True
        return False

    async def evaluate_prompt(
        self,
        workflow_id: UUID,
        node_id: str,
        prompt_field: str,
        request: PromptEvalRequest,
    ) -> PromptEvalResponse:
        check_id = uuid4()
        started = time.monotonic()
        ref = PromptUsageRef(execution_id=f"prompt_editor:{check_id}")

        try:
            ctx, cases, configs, provider, llm, total_cases = await asyncio.wait_for(
                self._prepare_check(workflow_id, node_id, prompt_field, request, check_id),
                PROMPT_CHECK_PREPARE_SECONDS,
            )
        except asyncio.TimeoutError as exc:
            raise AppException(
                status_code=504,
                error_key=ErrorKey.PROMPT_EXECUTION_TIMEOUT,
                error_detail="Preparing the check took too long. Try again.",
            ) from exc
        ref.workflow_id, ref.agent_id = ctx.workflow_id, ctx.agent_id

        uses_grounding = _GROUNDING_TECHNIQUE in request.techniques
        model_budget = Budget(
            PROMPT_CHECK_MODEL_BUDGET_WITH_NLI if uses_grounding else PROMPT_CHECK_MODEL_BUDGET_SECONDS
        )
        semaphore = asyncio.Semaphore(PROMPT_CHECK_CONCURRENCY)

        try:
            runs = await asyncio.gather(
                *(
                    self._call_model(
                        case, position, request.prompt_content, llm, model_budget, semaphore, check_id
                    )
                    for position, case in enumerate(cases)
                )
            )
            _collect_usage(ref, runs, request.provider_id)
            rows, deadline_hit = await self._score_all(runs, request, configs, check_id)
        finally:
            metering_handoff_failed = await self._flush_usage(ref)

        # Built after the flush; inside it the hand-over flag would be frozen False
        return PromptEvalResponse(
            results=rows,
            summary=_summarise(rows),
            provenance=PromptRunProvenance(
                provider_id=request.provider_id,
                provider_key=provider.llm_model_provider or "",
                model=provider.llm_model or "",
                techniques=list(request.techniques),
                evaluated_case_ids=[case.id for case in cases],
                total_cases=total_cases,
                ran_at=utc_now(),
                latency_ms_total=int((time.monotonic() - started) * 1000),
                usage_total=_usage_total(ref),
                budget_seconds=PROMPT_CHECK_MODEL_BUDGET_WITH_NLI + PROMPT_CHECK_SCORE_BUDGET_SECONDS
                if uses_grounding
                else PROMPT_CHECK_MODEL_BUDGET_SECONDS,
                deadline_hit=deadline_hit,
                metering_handoff_failed=metering_handoff_failed,
            ),
        )

    async def _score_all(
        self,
        runs: List[_CaseRun],
        request: PromptEvalRequest,
        configs: Dict[str, Dict[str, Any]],
        check_id: UUID,
    ) -> Tuple[List[PromptEvalCaseResult], bool]:
        """Sequential. nli_eval serializes with module lock; rest is in-memory"""
        rows: List[PromptEvalCaseResult] = []
        deadline_hit = any(run.status == "skipped" or run.budget_cut for run in runs)
        score_budget = (
            Budget(PROMPT_CHECK_SCORE_BUDGET_SECONDS)
            if _GROUNDING_TECHNIQUE in request.techniques
            else None
        )

        for run in runs:
            if run.status != "scored":
                rows.append(self._row(run, status=run.status, error=run.error))
                continue
            try:
                metrics, exhausted = await self._score(run, request, configs, score_budget)
                deadline_hit = deadline_hit or exhausted
                rows.append(self._row(run, status="scored", metrics=metrics))
            except Exception:
                logger.exception(
                    "Prompt check %s: scoring case %s failed", str(check_id)[:8], run.position
                )
                rows.append(self._row(run, status="scoring_failed", error=_INTERNAL_FAILURE))
        return rows, deadline_hit

    # ---- Optimize ------------------------------------------------------------

    async def _case_rows(self, suite_id: UUID, case_ids: List[UUID]) -> Dict[str, Any]:
        rows = await self.case_repo.get_cases_by_ids(suite_id, case_ids)
        return {str(row.id): row for row in rows}

    async def _build_examples(
        self,
        suite_id: Optional[UUID],
        split: ValidatedSplit,
        failed: List[FailedCaseRef],
    ) -> _Examples:
        """Failures first, dev cases next, shared budget. No duplicate failed cases.
        Re-read input/expectation for optimizer accuracy."""
        shown_failed = failed[:MAX_OPTIMIZE_FAILED]
        failure_ids = [entry.case_id for entry in shown_failed]
        already_shown = {str(case_id) for case_id in failure_ids}
        development = [c for c in split.dev if str(c) not in already_shown]
        truncated = len(failed) > len(shown_failed)

        if suite_id is None or not (failure_ids or development):
            return _Examples("", "", [], [], truncated)

        rendered = 0
        used = 0

        def _fits(block: str) -> bool:
            nonlocal rendered, used
            if rendered >= MAX_OPTIMIZE_EXAMPLES or used + len(block) > MAX_OPTIMIZE_EXAMPLE_CHARS:
                return False
            rendered += 1
            used += len(block)
            return True

        failed_blocks: List[str] = []
        gold_blocks: List[str] = []
        case_ids: List[UUID] = []
        failure_case_ids: List[UUID] = []

        # The first read carries the failures and the first window of development cases
        window = development[:MAX_OPTIMIZE_EXAMPLES]
        by_id = await self._case_rows(suite_id, failure_ids + window)

        for entry in shown_failed:
            row = by_id.get(str(entry.case_id))
            if row is None:
                truncated = True
                continue
            block = (
                f"Input: {_case_input_text(row.input_data)}\n"
                f"Expected: {normalize_text(row.expected_output)}\n"
                f"Got: {_shortened(entry.actual, MAX_OPTIMIZE_FAILED_ACTUAL_CHARS)}"
            )
            if entry.failed_metrics:
                block += f"\nFailed: {', '.join(entry.failed_metrics)}"
            if not _fits(block):
                truncated = True
                continue
            failed_blocks.append(block)
            failure_case_ids.append(row.id)
            case_ids.append(row.id)

        scanned = 0
        scan_limit = min(len(development), MAX_OPTIMIZE_EXAMPLE_SCAN)
        while True:
            for case_id in window:
                row = by_id.get(str(case_id))
                if row is None:
                    truncated = True
                    continue
                block = (
                    f"Input: {_case_input_text(row.input_data)}\n"
                    f"Expected: {normalize_text(row.expected_output)}"
                )
                if not _fits(block):
                    truncated = True
                    continue
                gold_blocks.append(block)
                case_ids.append(row.id)
            scanned += len(window)
            if rendered >= MAX_OPTIMIZE_EXAMPLES or scanned >= scan_limit:
                break
            window = development[scanned : scanned + MAX_OPTIMIZE_EXAMPLES]
            by_id = await self._case_rows(suite_id, window)

        truncated = truncated or scanned < len(development)

        return _Examples(
            gold_text="\n\n".join(gold_blocks),
            failed_text="\n\n---\n".join(failed_blocks),
            case_ids=case_ids,
            failure_case_ids=failure_case_ids,
            truncated=truncated,
        )

    async def _prepare_optimize(
        self,
        workflow_id: UUID,
        node_id: str,
        prompt_field: str,
        request: PromptOptimizeRequest,
        op_id: UUID,
    ) -> Tuple[PromptContext, LlmProviderRead, Any, ValidatedSplit, _Examples, int]:
        """Same gate as check. Allows no dataset (instructions-only is valid)"""
        from app.dependencies.injector import injector
        from app.services.llm_providers import LlmProviderService

        ctx = await self._prepare_context(workflow_id, node_id, prompt_field)
        reject_unsupported_techniques(request.techniques)

        config = await self.config_repo.get_by_context(workflow_id, node_id, prompt_field)
        suite_id = config.gold_suite_id if config else None
        index = await self.case_repo.get_case_index_for_suite(suite_id) if suite_id else []

        failed = list(request.failed_cases or [])
        reject_unsupported_techniques([m for entry in failed for m in entry.failed_metrics])
        split = validate_case_split(request.case_split, index, [entry.case_id for entry in failed])
        examples = await self._build_examples(suite_id, split, failed)

        provider = await injector.get(LlmProviderService).get_by_id(request.provider_id)
        llm = await self._build_model(provider, op_id)
        return ctx, provider, llm, split, examples, len(index)

    async def optimize_prompt(
        self,
        workflow_id: UUID,
        node_id: str,
        prompt_field: str,
        request: PromptOptimizeRequest,
    ) -> PromptOptimizeResponse:
        op_id = uuid4()
        started = time.monotonic()
        ref = PromptUsageRef(execution_id=f"prompt_editor:optimize:{op_id}")

        try:
            ctx, provider, llm, split, examples, total_cases = await asyncio.wait_for(
                self._prepare_optimize(workflow_id, node_id, prompt_field, request, op_id),
                PROMPT_CHECK_PREPARE_SECONDS,
            )
        except asyncio.TimeoutError as exc:
            raise AppException(
                status_code=504,
                error_key=ErrorKey.PROMPT_EXECUTION_TIMEOUT,
                error_detail="Preparing the rewrite took too long. Try again.",
            ) from exc
        ref.workflow_id, ref.agent_id = ctx.workflow_id, ctx.agent_id

        messages = [
            SystemMessage(content=_OPTIMIZE_SYSTEM_PROMPT),
            HumanMessage(
                content=_optimize_request_text(
                    request.current_prompt,
                    examples.gold_text,
                    examples.failed_text,
                    request.instructions,
                    describe_expectations(request.techniques),
                )
            ),
        ]

        try:
            try:
                response = await asyncio.wait_for(
                    llm.ainvoke(messages), timeout=OPTIMIZE_CALL_TIMEOUT_SECONDS
                )
            except asyncio.TimeoutError as exc:
                raise AppException(
                    status_code=504,
                    error_key=ErrorKey.PROMPT_EXECUTION_TIMEOUT,
                    error_detail="The rewrite did not finish within the time budget.",
                ) from exc
            except Exception as exc:
                logger.warning("Prompt optimize %s: model call failed", str(op_id)[:8], exc_info=True)
                raise AppException(
                    status_code=502,
                    error_key=ErrorKey.PROMPT_MODEL_CALL_FAILED,
                    error_detail=(
                        "The selected provider did not answer. "
                        "Choose another provider or check its configuration."
                    ),
                ) from exc

            ref.entries.append(_usage_entry(response, 0, "prompt_optimize", request.provider_id))
            suggested_prompt, explanation = _parse_suggestion(response.text)
        finally:
            metering_handoff_failed = await self._flush_usage(ref)

        return PromptOptimizeResponse(
            suggested_prompt=suggested_prompt,
            explanation=explanation,
            exposure={
                "case_ids": examples.case_ids,
                "failure_case_ids": examples.failure_case_ids,
            },
            examples_truncated=examples.truncated,
            holdout_case_ids=split.holdout,
            exploratory=split.exploratory,
            provenance=PromptRunProvenance(
                provider_id=request.provider_id,
                provider_key=provider.llm_model_provider or "",
                model=provider.llm_model or "",
                techniques=list(request.techniques),
                evaluated_case_ids=examples.case_ids,
                total_cases=total_cases,
                ran_at=utc_now(),
                latency_ms_total=int((time.monotonic() - started) * 1000),
                usage_total=_usage_total(ref),
                budget_seconds=OPTIMIZE_CALL_TIMEOUT_SECONDS,
                metering_handoff_failed=metering_handoff_failed,
            ),
        )
