from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TestCaseBase(BaseModel):
    input_data: Dict[str, Any] = Field(
        ...,
        description=(
            "Input payload passed to the workflow engine as input_data."
        ),
    )
    expected_output: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Expected output (string/JSON) for evaluators.",
    )
    tags: Optional[List[str]] = Field(
        default=None, description="Optional labels, e.g. ['refund', 'es-ES']."
    )
    weight: Optional[float] = Field(
        default=None,
        description="Optional weight used when aggregating metrics.",
    )
    source_conversation_id: Optional[UUID] = Field(
        default=None,
        description=(
            "Conversation this case was imported from. Cases sharing a value "
            "replay as one memory thread; null cases are independent."
        ),
    )
    turn_index: Optional[int] = Field(
        default=None,
        description="Position of this turn within its source conversation.",
    )


class TestCaseCreate(TestCaseBase):
    suite_id: Optional[UUID] = None


class TestCaseUpdate(BaseModel):
    input_data: Optional[Dict[str, Any]] = None
    expected_output: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None
    weight: Optional[float] = None


class TestCaseInDB(TestCaseBase):
    id: UUID
    suite_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TestCase(TestCaseInDB):
    pass


class ImportCasesFromConversationRequest(BaseModel):
    conversation_id: UUID
    replace: bool = False


class TestSuiteBase(BaseModel):
    name: str
    description: Optional[str] = None
    workflow_id: Optional[UUID] = Field(
        default=None,
        description=(
            "Optional default workflow used when a run does not specify "
            "workflow_id."
        ),
    )
    default_input_metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description=(
            "Metadata merged into each test case input_data before execution."
        ),
    )


class TestSuiteCreate(TestSuiteBase):
    pass


class TestSuiteUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    workflow_id: Optional[UUID] = None
    default_input_metadata: Optional[Dict[str, Any]] = None


class TestSuiteInDB(TestSuiteBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TestSuite(TestSuiteInDB):
    pass


class TestResultMetrics(BaseModel):
    # technique_key -> {score, passed, comment}
    # A check that could not run has no score; it is neither a pass nor a fail.
    score: float | bool | None = None
    passed: bool
    error: bool = False
    not_evaluated: bool = False
    comment: Optional[str] = None
    # Human-readable expected vs observed values, shown on the result card for the
    # methods that genuinely have them (e.g. route/action). None when not applicable.
    expected: Optional[str] = None
    actual: Optional[str] = None
    # Pass threshold for scored methods (NLI, Provenance, LLM Judge), shown by the score.
    threshold: Optional[float] = None
    # Per-rule breakdown for tool_used (and future multi-rule techniques).
    details: Optional[List[Dict[str, Any]]] = None


class TestResultBase(BaseModel):
    run_id: UUID
    case_id: UUID
    actual_output: Optional[Dict[str, Any]] = None
    execution_trace: Optional[Dict[str, Any]] = Field(
        default=None,
        description=(
            "Optional full workflow execution / agent logs payload stored for "
            "debugging and traceability."
        ),
    )
    metrics: Optional[Dict[str, TestResultMetrics]] = None
    error: Optional[str] = None
    status: Optional[str] = Field(
        default=None,
        description=(
            "scored | execution_failed | scoring_failed | skipped. Null for "
            "results recorded before statuses were introduced."
        ),
    )


class TestResultInDB(TestResultBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TestResult(TestResultInDB):
    pass


class TestToolRuleResult(BaseModel):
    """One rule outcome for a scope unit (turn or conversation), for any
    rule-based technique: tool_used, route_taken or action_taken."""

    id: UUID
    run_id: UUID
    technique: str = Field(default="tool_used", description="tool_used | route_taken | action_taken")
    rule_id: str
    scope: str
    case_id: Optional[UUID] = None
    source_conversation_id: Optional[UUID] = None
    status: str = Field(description="passed | failed | not_evaluated")
    score: Optional[float] = None
    details: Optional[Dict[str, Any]] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TestRunBase(BaseModel):
    suite_id: UUID
    workflow_id: UUID
    status: str = Field(
        default="queued",
        description="queued | running | completed | failed",
    )
    techniques: List[str] = Field(
        default_factory=list,
        description="Identifiers of selected evaluation techniques.",
    )
    summary_metrics: Optional[Dict[str, Any]] = None


class TestRunCreate(BaseModel):
    techniques: List[str]
    technique_configs: Optional[Dict[str, Dict[str, Any]]] = Field(
        default=None,
        description=(
            "Optional per-technique configuration map. "
            "Example: {'nli_eval': {'min_entail_score': 0.6}}"
        ),
    )
    workflow_id: Optional[UUID] = Field(
        default=None,
        description="Optional workflow override for this run. "
        "If not provided, the suite's workflow_id will be used.",
    )
    input_metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description=(
            "Optional extra input metadata merged into each test case "
            "input_data at execution time."
        ),
    )


class TestRunInDB(TestRunBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TestRun(TestRunInDB):
    # Display metadata of the workflow version the run executed; populated on
    # read paths, None on the create response.
    workflow_name: Optional[str] = None
    workflow_version: Optional[str] = None


# ---------------------------------------------------------------------------
# TestEvaluation
# ---------------------------------------------------------------------------

class BatchRunsRequest(BaseModel):
    ids: List[str] = Field(
        ...,
        description="List of test run UUIDs to fetch.",
    )


class EvaluationRunRequest(BaseModel):
    """Options for starting a single evaluation run."""

    target_workflow_id: Optional[UUID] = Field(
        default=None,
        description=(
            "Run against this workflow version instead of the evaluation's own. "
            "Must be a version of the same workflow (same agent)."
        ),
    )


class RunWorkflowEvaluationsRequest(BaseModel):
    """Options for the workflow-wide Run all."""

    target_workflow_id: Optional[UUID] = Field(
        default=None,
        description=(
            "Run every evaluation against this workflow version instead of its "
            "own. Must be a version of the same workflow (same agent)."
        ),
    )


class StartedEvaluationRun(BaseModel):
    """Outcome of starting one evaluation in a batch/workflow run.

    ``run_id``/``suite_id`` are unset and ``error`` is populated when the
    evaluation could not be queued (``status == "failed_to_start"``).
    """

    evaluation_id: UUID
    run_id: Optional[UUID] = None
    suite_id: Optional[UUID] = None
    status: str
    error: Optional[str] = None


class TestEvaluationBase(BaseModel):
    name: str
    description: Optional[str] = None
    suite_id: UUID
    workflow_id: Optional[UUID] = None
    techniques: List[str] = Field(default_factory=list)
    technique_configs: Optional[Dict[str, Any]] = None
    input_metadata: Optional[Dict[str, Any]] = None


class TestEvaluationCreate(TestEvaluationBase):
    pass


class TestEvaluationUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    suite_id: Optional[UUID] = None
    workflow_id: Optional[UUID] = None
    techniques: Optional[List[str]] = None
    technique_configs: Optional[Dict[str, Any]] = None
    input_metadata: Optional[Dict[str, Any]] = None


class TestEvaluationInDB(TestEvaluationBase):
    id: UUID
    run_ids: List[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TestEvaluation(TestEvaluationInDB):
    pass


class EvaluationToolInfo(BaseModel):
    """A tool an agent can call, from the workflow graph. ``id`` matches tool events."""

    id: str
    name: str
    label: str
    type: str


class EvaluationAgentInfo(BaseModel):
    id: str
    label: str
    type: str
    workflow_path: List[str] = Field(default_factory=list)
    tools: List[EvaluationToolInfo] = Field(default_factory=list)


class EvaluationRouterBranch(BaseModel):
    """One selectable branch of a router node, with the node it routes to."""

    value: str
    destination: Optional[str] = None


class EvaluationRouterInfo(BaseModel):
    id: str
    label: str
    workflow_path: List[str] = Field(default_factory=list)
    branches: List[EvaluationRouterBranch] = Field(default_factory=list)


class EvaluationActionNodeInfo(BaseModel):
    id: str
    label: str
    type: str
    workflow_path: List[str] = Field(default_factory=list)


class EvaluationToolCatalog(BaseModel):
    """Agents/tools, routers and executable nodes for a workflow (incl. nested), for the UI."""

    workflow_id: UUID
    agents: List[EvaluationAgentInfo] = Field(default_factory=list)
    routers: List[EvaluationRouterInfo] = Field(default_factory=list)
    action_nodes: List[EvaluationActionNodeInfo] = Field(default_factory=list)


class WorkflowEvaluationSummary(BaseModel):
    """One overview row: a workflow (or the unassigned bucket) and its eval count.

    ``health`` is the mean accuracy across the workflow's evaluations whose latest
    run has finished, counting failed runs as 0; ``None`` when none have finished.
    ``finished_count`` is how many evaluations contributed to ``health``.
    ``any_running`` is true when any evaluation's latest run is queued or running.
    """

    workflow_id: Optional[UUID] = None
    eval_count: int
    health: Optional[float] = None
    finished_count: int = 0
    any_running: bool = False


class PaginatedEvaluations(BaseModel):
    """One page of a workflow's evaluations.

    ``total`` is the count for the current search; ``total_unfiltered`` is the
    workflow's full evaluation count (ignoring search), so the header can show
    "N of M". ``any_running`` reflects the whole workflow (across all pages), not
    just this page, so the client can block a duplicate "Run all".
    """

    items: List[TestEvaluationInDB] = Field(default_factory=list)
    total: int
    total_unfiltered: int
    page: int
    page_size: int
    any_running: bool = False
