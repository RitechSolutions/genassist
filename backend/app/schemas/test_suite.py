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
    score: float | bool
    passed: bool
    comment: Optional[str] = None


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


class TestResultInDB(TestResultBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TestResult(TestResultInDB):
    pass


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
    pass


# ---------------------------------------------------------------------------
# TestEvaluation
# ---------------------------------------------------------------------------

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

