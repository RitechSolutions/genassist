from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


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

class PromptEvalRequest(BaseModel):
    prompt_content: str = Field(..., description="The system prompt to evaluate.")
    techniques: List[str] = Field(
        default_factory=lambda: ["exact_match", "contains"],
        description="Evaluator technique identifiers.",
    )
    provider_id: UUID = Field(..., description="LLM provider to run the prompt against.")


class PromptEvalCaseResult(BaseModel):
    case_id: UUID
    input: str
    expected: str
    actual: str
    metrics: Dict[str, Any] = Field(default_factory=dict)
    passed: bool = False


class PromptEvalSummary(BaseModel):
    total: int
    passed: int
    avg_score: float


class PromptEvalResponse(BaseModel):
    results: List[PromptEvalCaseResult]
    summary: PromptEvalSummary


# ---------------------------------------------------------------------------
# Prompt Optimization
# ---------------------------------------------------------------------------

class PromptOptimizeRequest(BaseModel):
    provider_id: UUID = Field(..., description="LLM provider for generating the optimized prompt.")
    current_prompt: str = Field(..., description="The current system prompt to improve.")
    instructions: Optional[str] = Field(
        default=None,
        description="Optional extra instructions to guide optimization.",
    )
    failed_cases: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Recent failed evaluation cases for context.",
    )


class PromptOptimizeResponse(BaseModel):
    suggested_prompt: str
    explanation: str
