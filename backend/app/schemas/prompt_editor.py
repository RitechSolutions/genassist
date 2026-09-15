from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Dict, List, Literal, Optional, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator


# ---------------------------------------------------------------------------
# PromptVersion
# ---------------------------------------------------------------------------

class PromptVersionCreate(BaseModel):
    # No min_length; clearing a prompt is considered a change
    content: str = Field(..., max_length=200_000, description="The prompt text.")
    label: Optional[str] = Field(
        default=None, max_length=200, description="Optional human-readable label."
    )


class PromptVersionRead(BaseModel):
    id: UUID
    workflow_id: UUID
    node_id: str
    prompt_field: str
    version_number: int
    content: str
    label: Optional[str] = None
    is_active: bool
    created_at: datetime
    created_by: Optional[UUID] = None

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# PromptConfig
# ---------------------------------------------------------------------------

class PromptConfigRead(BaseModel):
    id: Optional[UUID] = None
    workflow_id: UUID
    node_id: str
    prompt_field: str
    gold_suite_id: Optional[UUID] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class GoldSuiteLinkRequest(BaseModel):
    """Link an existing suite or create a new one."""
    suite_id: Optional[UUID] = Field(
        default=None,
        description="ID of an existing test suite to link. If omitted a new suite is created.",
    )
    name: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Name for the new gold suite (used only when suite_id is omitted).",
    )


# ---------------------------------------------------------------------------
# Prompt history
# ---------------------------------------------------------------------------

class LegacyHistoryRead(BaseModel):
    """Versions saved under a shared DOM id before nodes carried their own history"""
    node_id: str
    versions: List[PromptVersionRead]
    gold_suite_id: Optional[UUID] = None


class PromptHistoryRead(BaseModel):
    """All data the editor needs: versions, node state, and field metadata
    that determine which controls are usable"""
    versions: List[PromptVersionRead]
    gold_suite_id: Optional[UUID] = None
    node_type: Optional[str] = None
    node_missing: bool
    field_label: Optional[str] = None
    inline_check_supported: bool = False
    unsupported_reason: Optional[str] = None
    legacy_shared: Optional[LegacyHistoryRead] = None


# ---------------------------------------------------------------------------
# Prompt Evaluation
# ---------------------------------------------------------------------------

# App status values from test_suite.py::ResultStatus.
# Plain strings to avoid importing the engine.
PromptCaseStatus = Literal["scored", "execution_failed", "scoring_failed", "skipped"]
PromptCaseVerdict = Literal["passed", "failed", "inconclusive"]

MAX_PROMPT_CONTENT = 200_000  # same bound as PromptVersionCreate.content
MAX_CHECK_CASES = 25  # ceiling for max_cases, case_ids and the hold-out list
MAX_ACTUAL_CHARS = 16_000  # bounds actual, input and expected on the wire

# Check payload roots. ``outputs`` bare-only; no nested or registry paths
FIELD_PATH_RE = r"^(outputs|(reference_outputs|inputs)(\.[A-Za-z0-9_\-]{1,64}){0,8})$"

# List bounds don't apply to items. Rejected ids logged in error_detail before client truncation
TechniqueId = Annotated[str, Field(max_length=64)]


def _reject_duplicates(values: Optional[List[Any]]) -> Optional[List[Any]]:
    """Duplicates would grade the same thing twice and desync the client's run key"""
    if values is not None and len(set(values)) != len(values):
        raise ValueError("must not contain duplicate entries")
    return values


class _Forbid(BaseModel):
    """Rejects unknown keys to prevent evaluator options leaking to isolated checks"""

    model_config = ConfigDict(extra="forbid")


class NotContainsConfig(_Forbid):
    phrases: List[str] = Field(..., min_length=1, max_length=50)

    @field_validator("phrases")
    @classmethod
    def _clean_phrases(cls, value: List[str]) -> List[str]:
        phrases = [entry.strip() for entry in value]
        for entry in phrases:
            if not entry:
                raise ValueError("a forbidden phrase must not be blank")
            if len(entry) > 200:
                raise ValueError("a forbidden phrase must be 200 characters or fewer")
        return phrases


class FieldEqualsConfig(_Forbid):
    # Unresolved paths read as empty—typos fail, not skip
    # _read_path can't distinguish empty from missing
    field: str = Field(..., pattern=FIELD_PATH_RE, max_length=200)
    # Stripped before bounds check (matches evaluator), so a blank is rejected here
    # rather than reaching the evaluator, which normalizes it to "" and fails every case
    expected: Optional[
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2_000)]
    ] = None

    @model_validator(mode="after")
    def _only_outputs_may_omit_expected(self) -> Self:
        # Fallback to config.get("expected", reference_outputs)
        # Only bare "outputs" uses it (exact match). Bare "reference_outputs" self-compares;
        # others compare wrong reference
        if self.field != "outputs" and self.expected is None:
            raise ValueError("only the bare outputs field may omit an expected value")
        return self


class PromptTechniqueConfigs(_Forbid):
    """Config for techniques that accept it. nli_eval gets fixed evidence;
    llm_judge/provenance_eval have no model, 422 if named"""

    not_contains: Optional[NotContainsConfig] = None
    field_equals: Optional[FieldEqualsConfig] = None


class PromptEvalRequest(BaseModel):
    prompt_content: str = Field(
        ..., min_length=1, max_length=MAX_PROMPT_CONTENT, description="The system prompt to evaluate."
    )
    provider_id: UUID = Field(..., description="LLM provider to run the prompt against.")
    techniques: List[TechniqueId] = Field(
        ..., min_length=1, max_length=8, description="Evaluator technique identifiers."
    )
    technique_configs: PromptTechniqueConfigs = Field(default_factory=PromptTechniqueConfigs)
    case_ids: Optional[List[UUID]] = Field(
        default=None,
        min_length=1,
        max_length=MAX_CHECK_CASES,
        description="Cases to run. Omit to let the server pick the first max_cases.",
    )
    max_cases: int = Field(
        default=10, ge=1, le=MAX_CHECK_CASES, description="Ignored when case_ids is given."
    )

    @field_validator("techniques", "case_ids")
    @classmethod
    def _unique_entries(cls, value: Optional[List[Any]]) -> Optional[List[Any]]:
        return _reject_duplicates(value)


class PromptEvalCaseResult(BaseModel):
    case_id: UUID
    input: str = Field(default="", max_length=MAX_ACTUAL_CHARS)
    expected: str = Field(default="", max_length=MAX_ACTUAL_CHARS)
    actual: str = Field(default="", max_length=MAX_ACTUAL_CHARS)
    actual_truncated: bool = False
    status: PromptCaseStatus
    error: Optional[str] = None
    metrics: Dict[str, Any] = Field(default_factory=dict)
    verdict: Optional[PromptCaseVerdict] = None
    passed: bool = False
    case_score: Optional[float] = None
    scored_metrics: int = 0
    failed_metrics: int = 0
    errored_metrics: int = 0
    not_evaluated_metrics: int = 0
    not_applicable_metrics: int = 0


class PromptEvalSummary(BaseModel):
    """One count per outcome. The six outcome counts sum to ``total``; ``scored``
    is a separate tally of cases with at least one scored metric, and is
    ``avg_score``'s denominator"""

    total: int
    passed: int
    failed: int
    inconclusive: int
    execution_failed: int
    scoring_failed: int
    skipped: int
    scored: int
    avg_score: Optional[float] = None


class PromptRunProvenance(BaseModel):
    """What the run actually did, so the header can state it rather than imply it"""

    mode: Literal["isolated_prompt"] = "isolated_prompt"
    provider_id: UUID
    provider_key: str  # "" when the row's llm_model_provider is NULL
    model: str
    techniques: List[str]
    evaluated_case_ids: List[UUID]
    total_cases: int  # the linked suite's case count
    trials: int = 1
    ran_at: datetime
    latency_ms_total: int
    usage_total: Dict[str, Any]
    budget_seconds: int
    deadline_hit: bool = False
    metering_handoff_failed: bool = False


class PromptEvalResponse(BaseModel):
    results: List[PromptEvalCaseResult]
    summary: PromptEvalSummary
    provenance: PromptRunProvenance


# ---------------------------------------------------------------------------
# Prompt Optimization
# ---------------------------------------------------------------------------

class FailedCaseRef(BaseModel):
    """Failed case for the optimizer. Only actual travels;
    input and expectation are re-read server-side"""

    case_id: UUID
    actual: str = Field(..., max_length=MAX_ACTUAL_CHARS)


class CaseSplit(BaseModel):
    """Absent = exploratory. The development set is never sent, it is the suite
    minus the hold-out"""

    holdout_case_ids: List[UUID] = Field(..., min_length=1, max_length=MAX_CHECK_CASES)

    @field_validator("holdout_case_ids")
    @classmethod
    def _unique_entries(cls, value: List[UUID]) -> List[UUID]:
        return _reject_duplicates(value)


class PromptOptimizeRequest(BaseModel):
    provider_id: UUID = Field(..., description="LLM provider for generating the optimized prompt.")
    current_prompt: str = Field(..., min_length=1, max_length=MAX_PROMPT_CONTENT)
    instructions: Optional[str] = Field(
        default=None, max_length=4_000, description="Optional extra instructions to guide optimization."
    )
    failed_cases: Optional[List[FailedCaseRef]] = Field(default=None, max_length=10)
    case_split: Optional[CaseSplit] = None

    @field_validator("failed_cases")
    @classmethod
    def _unique_cases(cls, value: Optional[List[FailedCaseRef]]) -> Optional[List[FailedCaseRef]]:
        if value is not None:
            _reject_duplicates([entry.case_id for entry in value])
        return value


class PromptOptimizeResponse(BaseModel):
    suggested_prompt: str
    explanation: str
    exposure: Dict[str, List[UUID]]
    examples_truncated: bool = False
    holdout_case_ids: List[UUID]
    exploratory: bool
    provenance: PromptRunProvenance
