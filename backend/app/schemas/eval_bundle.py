"""Portable evaluation bundle: the export/import file format and its API shapes.

A bundle carries one evaluation, its dataset (cases included) and the display
labels of every environment-specific reference embedded in the technique
configs, so an importer can re-link the config to the target environment's
workflow by name instead of by id.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

EVALUATION_BUNDLE_KIND = "genassist.evaluation-bundle"
EVALUATION_BUNDLE_SCHEMA_VERSION = 1

# Reference kinds a technique config can point at in the workflow graph.
REF_KIND_TOOL = "tool"
REF_KIND_AGENT = "agent"
REF_KIND_ROUTER = "router"
REF_KIND_ACTION = "action"

REF_STATUS_RESOLVED = "resolved"
REF_STATUS_AMBIGUOUS = "ambiguous"
REF_STATUS_MISSING = "missing"


class BundleNodeRef(BaseModel):
    """Label and node type recorded for one graph-node reference at export time.

    ``node_type`` lets import refuse to bind a name match onto a node of a
    different type. Absent on bundles exported before it was recorded.
    """

    label: Optional[str] = None
    kind: str
    node_type: Optional[str] = None


class BundleProviderRef(BaseModel):
    """Display metadata recorded for one LLM provider reference at export time."""

    name: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None


class BundleReferences(BaseModel):
    """Label maps for every environment-specific id embedded in the configs.

    ``cases`` maps an exported test case id to its ``local_id`` inside the
    bundle, so turn-targeted rules can be re-pointed at the recreated cases.
    """

    nodes: Dict[str, BundleNodeRef] = Field(default_factory=dict)
    llm_providers: Dict[str, BundleProviderRef] = Field(default_factory=dict)
    cases: Dict[str, int] = Field(default_factory=dict)


class BundleCase(BaseModel):
    local_id: int
    input_data: Dict[str, Any]
    expected_output: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None
    weight: Optional[float] = None
    source_conversation_id: Optional[UUID] = None
    turn_index: Optional[int] = None


# Ceiling on an INBOUND bundle: the whole payload is parsed into memory before
# anything is written. Enforced on the import paths rather than on the model,
# which is also the export response — capping that would make a large dataset
# impossible to export.
MAX_BUNDLE_CASES = 5000
MAX_BUNDLE_RESOLUTIONS = 1000


class BundleDataset(BaseModel):
    # Length limits match the DB columns so a bad bundle fails at parse time,
    # not halfway through an import.
    name: str = Field(max_length=200)
    description: Optional[str] = None
    default_input_metadata: Optional[Dict[str, Any]] = None
    cases: List[BundleCase] = Field(default_factory=list)


class BundleEvaluation(BaseModel):
    name: str = Field(max_length=200)
    description: Optional[str] = None
    techniques: List[str] = Field(default_factory=list)
    technique_configs: Optional[Dict[str, Any]] = None
    input_metadata: Optional[Dict[str, Any]] = None


class BundleSource(BaseModel):
    """Where the bundle came from — display-only, never used for linking."""

    workflow_id: Optional[UUID] = None
    workflow_name: Optional[str] = None
    workflow_version: Optional[str] = None


class EvaluationBundle(BaseModel):
    # Plain str, not a Literal: the runtime check in _validate_bundle_header
    # gives a readable 400 ("this file is not an evaluation bundle") where a
    # Literal would fail in Pydantic with a raw 422.
    kind: str = EVALUATION_BUNDLE_KIND
    schema_version: int = EVALUATION_BUNDLE_SCHEMA_VERSION
    source: BundleSource = Field(default_factory=BundleSource)
    evaluation: BundleEvaluation
    dataset: BundleDataset
    references: BundleReferences = Field(default_factory=BundleReferences)
    # Human-readable notes recorded at export time (e.g. stripped secret fields).
    notes: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Bundle set: every evaluation of one workflow in a single file
# ---------------------------------------------------------------------------

EVALUATION_BUNDLE_SET_KIND = "genassist.evaluation-bundle-set"
EVALUATION_BUNDLE_SET_SCHEMA_VERSION = 1

MAX_SET_EVALUATIONS = 200
MAX_SET_TOTAL_CASES = 20000
# Datasets are not bounded by the evaluation count on their own: unreferenced
# ones are rejected, but the cap keeps a crafted file from driving the
# per-dataset lookups before that check can run.
MAX_SET_DATASETS = 200


class BundleSetDataset(BundleDataset):
    """One dataset stored once for the whole set; items point at ``local_id``."""

    local_id: int


class BundleSetItem(BaseModel):
    """One evaluation in a set; its dataset lives in the set's ``datasets``."""

    evaluation: BundleEvaluation
    dataset_local_id: int
    references: BundleReferences = Field(default_factory=BundleReferences)
    notes: List[str] = Field(default_factory=list)


class EvaluationBundleSet(BaseModel):
    # Plain str for the same reason as EvaluationBundle.kind: the runtime check
    # gives a readable 400 where a Literal would fail with a raw 422.
    kind: str = EVALUATION_BUNDLE_SET_KIND
    schema_version: int = EVALUATION_BUNDLE_SET_SCHEMA_VERSION
    source: BundleSource = Field(default_factory=BundleSource)
    datasets: List[BundleSetDataset] = Field(default_factory=list)
    evaluations: List[BundleSetItem] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Import preview / commit
# ---------------------------------------------------------------------------


class BundleRefCandidate(BaseModel):
    id: str
    label: str


class BundleNodeResolution(BaseModel):
    """How one graph-node reference resolved against the target workflow."""

    ref: str
    kind: str
    label: Optional[str] = None
    status: str
    resolved_id: Optional[str] = None
    resolved_label: Optional[str] = None
    candidates: List[BundleRefCandidate] = Field(default_factory=list)
    # Why the status is not a plain match, shown next to the row.
    note: Optional[str] = None
    # The node type this reference had in the source workflow, so a manual pick
    # can be narrowed to nodes that could actually play the same role.
    original_type: Optional[str] = None


class BundleProviderResolution(BaseModel):
    """How one LLM provider reference resolved against the target environment."""

    ref: str
    name: Optional[str] = None
    model: Optional[str] = None
    status: str
    resolved_id: Optional[str] = None
    resolved_name: Optional[str] = None


class EvaluationImportPreviewRequest(BaseModel):
    bundle: EvaluationBundle
    target_workflow_id: UUID


class BundleExistingDataset(BaseModel):
    """A dataset in the target environment already using the bundle's name, so
    the import can attach to it instead of creating a duplicate."""

    id: UUID
    name: str
    case_count: int


class EvaluationImportPreview(BaseModel):
    evaluation_name: str
    dataset_name: str
    case_count: int
    existing_dataset: Optional[BundleExistingDataset] = None
    workflow_name_matches: bool
    node_refs: List[BundleNodeResolution] = Field(default_factory=list)
    provider_refs: List[BundleProviderResolution] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    # True when every node reference resolved without a manual pick.
    can_import: bool
    # Dropping the unmatched rules would leave the evaluation with no checks at
    # all, which import refuses — so the UI must not offer that route.
    dropping_all_would_empty: bool = False


class EvaluationImportRequest(BaseModel):
    bundle: EvaluationBundle
    target_workflow_id: UUID
    # Attach to this existing dataset instead of creating one; its cases are
    # kept as they are and the bundle's cases are not re-created.
    existing_suite_id: Optional[UUID] = None
    # Manual picks for ambiguous/missing references, keyed "<kind>:<ref>"
    # (a ref value can appear under two kinds) -> target node id.
    resolutions: Dict[str, str] = Field(
        default_factory=dict, max_length=MAX_BUNDLE_RESOLUTIONS
    )
    # Drop rules whose references stayed unresolved instead of failing the import.
    drop_unresolved_rules: bool = False


class EvaluationImportResult(BaseModel):
    evaluation_id: UUID
    suite_id: UUID
    case_count: int
    # True when the evaluation was attached to an existing dataset rather than
    # a newly created one.
    reused_dataset: bool = False
    dropped_rules: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Set import preview / commit
# ---------------------------------------------------------------------------

SET_ITEM_IMPORTED = "imported"
SET_ITEM_SKIPPED = "skipped"
SET_ITEM_FAILED = "failed"


class EvaluationSetItemPreview(BaseModel):
    """How one evaluation of the set would land on the target workflow."""

    name: str
    dataset_name: str
    case_count: int
    # An evaluation with this name already exists on the target workflow, so
    # the import skips it unless the caller opts out of skipping.
    already_exists: bool = False
    dropping_all_would_empty: bool = False
    # The reference keys THIS evaluation uses, so the UI can judge each row on
    # its own instead of on the set-wide unmatched count.
    node_ref_keys: List[str] = Field(default_factory=list)


class BundleSetDatasetPreview(BaseModel):
    local_id: int
    name: str
    case_count: int
    existing_dataset: Optional[BundleExistingDataset] = None


class EvaluationSetImportPreviewRequest(BaseModel):
    bundle_set: EvaluationBundleSet
    target_workflow_id: UUID


class EvaluationSetImportPreview(BaseModel):
    workflow_name_matches: bool
    evaluations: List[EvaluationSetItemPreview] = Field(default_factory=list)
    datasets: List[BundleSetDatasetPreview] = Field(default_factory=list)
    # The union of every item's references, resolved once — each ref appears a
    # single time no matter how many evaluations use it.
    node_refs: List[BundleNodeResolution] = Field(default_factory=list)
    provider_refs: List[BundleProviderResolution] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    can_import: bool


class EvaluationSetImportRequest(BaseModel):
    bundle_set: EvaluationBundleSet
    target_workflow_id: UUID
    # Positions (0-based) of the evaluations to import; None imports all.
    include: Optional[List[int]] = Field(default=None, max_length=MAX_SET_EVALUATIONS)
    # Shared manual picks, applied to every evaluation in the set.
    resolutions: Dict[str, str] = Field(
        default_factory=dict, max_length=MAX_BUNDLE_RESOLUTIONS
    )
    drop_unresolved_rules: bool = False
    skip_existing: bool = True


class EvaluationSetItemResult(BaseModel):
    name: str
    status: str
    evaluation_id: Optional[UUID] = None
    suite_id: Optional[UUID] = None
    case_count: int = 0
    reused_dataset: bool = False
    dropped_rules: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    # Why the item failed or was skipped, in one client-safe sentence.
    detail: Optional[str] = None


class EvaluationSetImportResult(BaseModel):
    results: List[EvaluationSetItemResult] = Field(default_factory=list)
    imported: int = 0
    skipped: int = 0
    failed: int = 0
