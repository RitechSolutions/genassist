"""Export/import of evaluations as portable bundles.

Technique configs embed ids that only exist in the source environment's
database (graph node ids, LLM provider ids, test case ids). Export records a
display label next to every such id; import resolves the labels against the
target workflow's catalog and rewrites the config before creating anything.

The same walk is used to collect references and to rewrite them (the resolver
is swapped), so the two can never disagree about where references live.
"""

from __future__ import annotations

import copy
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple
from uuid import UUID

from injector import inject

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.schemas.eval_bundle import (
    EVALUATION_BUNDLE_KIND,
    EVALUATION_BUNDLE_SCHEMA_VERSION,
    EVALUATION_BUNDLE_SET_KIND,
    EVALUATION_BUNDLE_SET_SCHEMA_VERSION,
    MAX_BUNDLE_CASES,
    MAX_SET_DATASETS,
    MAX_SET_EVALUATIONS,
    MAX_SET_TOTAL_CASES,
    REF_KIND_ACTION,
    REF_KIND_AGENT,
    REF_KIND_ROUTER,
    REF_KIND_TOOL,
    REF_STATUS_AMBIGUOUS,
    REF_STATUS_MISSING,
    REF_STATUS_RESOLVED,
    SET_ITEM_FAILED,
    SET_ITEM_IMPORTED,
    SET_ITEM_SKIPPED,
    BundleCase,
    BundleDataset,
    BundleEvaluation,
    BundleExistingDataset,
    BundleNodeRef,
    BundleNodeResolution,
    BundleProviderRef,
    BundleProviderResolution,
    BundleRefCandidate,
    BundleReferences,
    BundleSetDataset,
    BundleSetDatasetPreview,
    BundleSetItem,
    BundleSource,
    EvaluationBundle,
    EvaluationBundleSet,
    EvaluationImportPreview,
    EvaluationImportPreviewRequest,
    EvaluationImportRequest,
    EvaluationImportResult,
    EvaluationSetImportPreview,
    EvaluationSetImportPreviewRequest,
    EvaluationSetImportRequest,
    EvaluationSetImportResult,
    EvaluationSetItemPreview,
    EvaluationSetItemResult,
)
from app.db.models.test_suite import TestCaseModel
from app.repositories.test_suite import TestCaseRepository
from app.schemas.test_suite import (
    TestCaseInDB,
    TestEvaluationCreate,
    TestSuiteCreate,
)
from app.services.llm_providers import LlmProviderService
from app.services.test_suite import TestSuiteService, resolvers_from_agents
from app.services.tool_usage_rules import canonicalize_tool_usage_config
from app.services.workflow import WorkflowService

logger = logging.getLogger(__name__)

TOOL_USED = "tool_used"
ROUTE_TAKEN = "route_taken"
ACTION_TAKEN = "action_taken"
LLM_JUDGE = "llm_judge"
PROVENANCE_EVAL = "provenance_eval"
NLI_EVAL = "nli_eval"

# Techniques whose configs carry an llm_provider_id.
_PROVIDER_TECHNIQUES = (LLM_JUDGE, PROVENANCE_EVAL)

_TECHNIQUE_LABELS = {
    TOOL_USED: "Tool Usage",
    ROUTE_TAKEN: "Route Taken",
    ACTION_TAKEN: "Action Taken",
}

# Credential-bearing key names for bundle payloads. Tuned differently from
# template_sanitizer's list, which matches a bare "token" — correct for workflow
# node.data, but here it would eat ordinary settings like ``max_tokens``.
_SECRET_KEY_SUBSTRINGS = (
    "api_key",
    "apikey",
    "api_token",
    "apitoken",
    "auth_token",
    "authtoken",
    "access_token",
    "accesstoken",
    "refresh_token",
    "refreshtoken",
    "session_token",
    "sessiontoken",
    "id_token",
    "secret",
    "password",
    "passwd",
    "credential",
    "private_key",
    "privatekey",
    "access_key",
    "accesskey",
    "bearer",
)

# A key that IS the credential rather than merely mentioning one, so "token"
# is stripped while "max_tokens" and "token_budget" are kept.
_SECRET_KEY_EXACT = frozenset({"token", "authorization", "auth"})

# Maps whose keys are identifiers, not field names — a tool id can contain
# "secret" without the entry being a credential. Their values are still walked.
_IDENTIFIER_KEYED_FIELDS = frozenset({"per_tool"})

_URL_PATTERN = re.compile(r"https?://", re.IGNORECASE)
_UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
_MAX_METADATA_WARNINGS = 10


def _normalize_name(value: Any) -> str:
    return str(value).strip().lower()


_GENERIC_ITEM_FAILURE = "The evaluation could not be imported."
_MAX_ITEM_DETAIL_CHARS = 300


def _client_safe_item_detail(error: AppException) -> str:
    """One item's failure reason, safe to return inside a 2xx batch result.

    A batch result never reaches the exception handler, so it never passes that
    gate on which error keys may expose ``error_detail`` outside dev. Only this
    feature's own bundle messages are written for users; anything else could
    carry internal text such as a raw validation error.
    """
    detail = (error.error_detail or "").strip()
    if error.error_key != ErrorKey.EVALUATION_BUNDLE_INVALID or not detail:
        return _GENERIC_ITEM_FAILURE
    return detail[:_MAX_ITEM_DETAIL_CHARS]


@dataclass
class _BatchState:
    """Bookkeeping shared by the items of one batch import."""

    existing_names: set
    # The caller's manual picks, applied to whichever items use those refs.
    resolutions: Dict[str, str]
    # Set-wide node metadata, so every item resolves as the preview did.
    merged_nodes: Dict[str, BundleNodeRef]
    suites_by_local: Dict[int, UUID] = field(default_factory=dict)
    # Normalized dataset name -> the local id that already materialized it. A
    # second dataset sharing that name is a different dataset and keeps its own
    # cases, whether the first one was created here or already on the target.
    dataset_owner_by_name: Dict[str, int] = field(default_factory=dict)


class UnresolvedRefError(ValueError):
    """A config reference that has no usable mapping in the target environment."""

    def __init__(self, ref: str, kind: str, reason: Optional[str] = None):
        self.ref = ref
        self.kind = kind
        self.reason = reason or (
            f"no match for {kind} '{ref}' in the target workflow"
        )
        super().__init__(self.reason)


def ref_key(ref: str, kind: str) -> str:
    """Key for resolution maps. A ref value can appear under two kinds (an agent
    node id is also an action node), so maps are keyed by kind + ref."""
    return f"{kind}:{ref}"


# ---------------------------------------------------------------------------
# Sanitization (secrets never travel inside a bundle)
# ---------------------------------------------------------------------------


def _is_bundle_secret_key(key: Any) -> bool:
    """Whether a bundle payload key names a credential."""
    if not isinstance(key, str):
        return False
    lowered = key.strip().lower()
    if lowered in _SECRET_KEY_EXACT:
        return True
    return any(substring in lowered for substring in _SECRET_KEY_SUBSTRINGS)


def sanitize_secret_keys(
    mapping: Optional[Dict[str, Any]], context: str
) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    """Copy of ``mapping`` without credential-bearing keys, at any depth.

    Keys are only treated as field names where they are one: inside an
    identifier-keyed map such as ``per_tool`` a key is a tool id, and dropping
    it because the tool is called "get_api_key" would silently delete a check.
    """
    if not isinstance(mapping, dict):
        return mapping, []
    notes: List[str] = []

    def clean(value: Any, parent_key: Optional[str] = None) -> Any:
        if isinstance(value, dict):
            keys_are_identifiers = parent_key in _IDENTIFIER_KEYED_FIELDS
            result = {}
            for key, nested in value.items():
                if not keys_are_identifiers and _is_bundle_secret_key(key):
                    notes.append(f"Removed secret field '{key}' from {context}.")
                    continue
                result[key] = clean(nested, key)
            return result
        if isinstance(value, list):
            return [clean(item, parent_key) for item in value]
        return copy.deepcopy(value)

    # One note per distinct field: a rule repeated across cases should not
    # produce a wall of identical lines.
    return clean(mapping), list(dict.fromkeys(notes))


def sanitize_technique_configs(
    configs: Optional[Dict[str, Any]],
) -> Tuple[Dict[str, Any], List[str]]:
    """Strip secret-looking keys from the top level of every technique config."""
    clean: Dict[str, Any] = {}
    notes: List[str] = []
    for technique, config in (configs or {}).items():
        if not isinstance(config, dict):
            clean[technique] = config
            continue
        safe, config_notes = sanitize_secret_keys(
            config, f"the {technique} configuration"
        )
        clean[technique] = safe
        notes.extend(config_notes)
    return clean, notes


# ---------------------------------------------------------------------------
# Reference walk (collection and rewriting share it)
# ---------------------------------------------------------------------------

Resolver = Callable[[str, str], str]


def _rewrite_tool_rule(rule: Dict[str, Any], resolve: Resolver) -> Dict[str, Any]:
    """Rewrite one tool rule (rules shape or the legacy single-tool config)."""
    updated = dict(rule)
    if isinstance(updated.get("tool_ids"), list):
        mapped_ids = [
            resolve(str(tool_id), REF_KIND_TOOL)
            for tool_id in updated["tool_ids"]
            if tool_id
        ]
        # Two source refs (e.g. a tool's id and its display name) may map to
        # one target tool; a duplicate entry would be redundant, not wrong.
        updated["tool_ids"] = list(dict.fromkeys(mapped_ids))
    if updated.get("agent_id"):
        updated["agent_id"] = resolve(str(updated["agent_id"]), REF_KIND_AGENT)
    if isinstance(updated.get("per_tool"), dict):
        updated["per_tool"] = _rewrite_per_tool(updated["per_tool"], resolve)
    # Legacy keys: "tool" is a tool reference, "node" is the agent.
    if updated.get("tool"):
        updated["tool"] = resolve(str(updated["tool"]), REF_KIND_TOOL)
    if updated.get("node"):
        updated["node"] = resolve(str(updated["node"]), REF_KIND_AGENT)
    return updated


def _rewrite_per_tool(per_tool: Dict[str, Any], resolve: Resolver) -> Dict[str, Any]:
    """Re-key per-tool checks. Unlike tool_ids, two checks collapsing onto one
    target tool would silently drop one of them — refuse instead."""
    rewritten: Dict[str, Any] = {}
    for tool_id, check in per_tool.items():
        mapped = resolve(str(tool_id), REF_KIND_TOOL)
        if mapped in rewritten:
            raise UnresolvedRefError(
                str(tool_id),
                REF_KIND_TOOL,
                reason=(
                    f"per-tool checks for '{tool_id}' and another entry both "
                    "map to the same target tool"
                ),
            )
        rewritten[mapped] = check
    return rewritten


def _rewrite_route_rule(rule: Dict[str, Any], resolve: Resolver) -> Dict[str, Any]:
    updated = dict(rule)
    selector_key = "router" if updated.get("router") else "node"
    if updated.get(selector_key):
        updated[selector_key] = resolve(str(updated[selector_key]), REF_KIND_ROUTER)
    return updated


def _rewrite_action_rule(rule: Dict[str, Any], resolve: Resolver) -> Dict[str, Any]:
    updated = dict(rule)
    if updated.get("node"):
        updated["node"] = resolve(str(updated["node"]), REF_KIND_ACTION)
    return updated


_RULE_REWRITERS: Dict[str, Callable[[Dict[str, Any], Resolver], Dict[str, Any]]] = {
    TOOL_USED: _rewrite_tool_rule,
    ROUTE_TAKEN: _rewrite_route_rule,
    ACTION_TAKEN: _rewrite_action_rule,
}


def _drop_message(technique: str, rule_number: int, error: UnresolvedRefError) -> str:
    label = _TECHNIQUE_LABELS.get(technique, technique)
    return f"{label} rule {rule_number} was dropped: {error.reason}."


def _rewrite_technique_config(
    technique: str,
    config: Dict[str, Any],
    resolve: Resolver,
    drop_log: Optional[List[str]],
) -> Optional[Dict[str, Any]]:
    """Rewrite one technique config; None when every rule was dropped.

    With ``drop_log`` set, a rule whose reference cannot be resolved is dropped
    and logged; without it the ``UnresolvedRefError`` propagates.
    """
    rule_rewriter = _RULE_REWRITERS[technique]
    raw_rules = config.get("rules")
    if not isinstance(raw_rules, list):
        # Legacy single-rule shape: the config itself is the rule.
        try:
            return rule_rewriter(config, resolve)
        except UnresolvedRefError as error:
            if drop_log is None:
                raise
            drop_log.append(_drop_message(technique, 1, error))
            return None

    rewritten: List[Dict[str, Any]] = []
    for number, rule in enumerate(raw_rules, start=1):
        if not isinstance(rule, dict):
            continue
        try:
            rewritten.append(rule_rewriter(rule, resolve))
        except UnresolvedRefError as error:
            if drop_log is None:
                raise
            drop_log.append(_drop_message(technique, number, error))
    if not rewritten:
        return None
    return {**config, "rules": rewritten}


def rewrite_node_refs(
    configs: Dict[str, Any],
    resolve: Resolver,
    drop_log: Optional[List[str]] = None,
) -> Tuple[Dict[str, Any], List[str]]:
    """Rewrite every graph-node reference. Returns (configs, dropped techniques)."""
    new_configs: Dict[str, Any] = {}
    dropped_techniques: List[str] = []
    for technique, config in configs.items():
        no_node_refs = technique not in _RULE_REWRITERS or not isinstance(config, dict)
        if no_node_refs:
            new_configs[technique] = config
            continue
        rewritten = _rewrite_technique_config(technique, config, resolve, drop_log)
        if rewritten is None:
            dropped_techniques.append(technique)
            continue
        new_configs[technique] = rewritten
    return new_configs, dropped_techniques


def collect_node_refs(configs: Optional[Dict[str, Any]]) -> List[Tuple[str, str]]:
    """Every (ref value, kind) a config embeds, in first-seen order."""
    seen: Dict[Tuple[str, str], None] = {}

    def record(value: str, kind: str) -> str:
        seen.setdefault((value, kind), None)
        return value

    rewrite_node_refs(configs or {}, record, drop_log=[])
    return list(seen.keys())


def collect_provider_ids(configs: Optional[Dict[str, Any]]) -> List[str]:
    ids: Dict[str, None] = {}
    for technique in _PROVIDER_TECHNIQUES:
        config = (configs or {}).get(technique)
        if isinstance(config, dict) and config.get("llm_provider_id"):
            ids.setdefault(str(config["llm_provider_id"]), None)
    return list(ids.keys())


def collect_case_ids(configs: Optional[Dict[str, Any]]) -> List[str]:
    """Test case ids referenced by turn-targeted rules of any rule-based technique."""
    ids: Dict[str, None] = {}
    for _, _, rule in _rules_with_targets(configs):
        for case_id in _rule_case_ids(rule):
            ids.setdefault(case_id, None)
    return list(ids.keys())


def _rule_case_ids(rule: Dict[str, Any]) -> List[str]:
    """Every case id a rule targets, from the one-turn and many-turn shapes."""
    values = rule.get("target_case_ids")
    ids = [str(value) for value in values if value] if isinstance(values, list) else []
    if rule.get("target_case_id"):
        ids.append(str(rule["target_case_id"]))
    return list(dict.fromkeys(ids))


def _rules_with_targets(
    configs: Optional[Dict[str, Any]],
) -> List[Tuple[str, int, Dict[str, Any]]]:
    """(technique, index, rule) for every rule that targets a specific test case."""
    found: List[Tuple[str, int, Dict[str, Any]]] = []
    for technique in _RULE_REWRITERS:
        config = (configs or {}).get(technique)
        if not isinstance(config, dict) or not isinstance(config.get("rules"), list):
            continue
        for index, rule in enumerate(config["rules"]):
            if isinstance(rule, dict) and _rule_case_ids(rule):
                found.append((technique, index, rule))
    return found


# ---------------------------------------------------------------------------
# Resolution against a target workflow catalog
# ---------------------------------------------------------------------------


def build_node_indexes(catalog: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Per-kind lookup tables: id -> label, id -> node type, and normalized
    name -> matching nodes."""
    indexes: Dict[str, Dict[str, Any]] = {
        kind: {"labels_by_id": {}, "types_by_id": {}, "ids_by_name": {}}
        for kind in (REF_KIND_TOOL, REF_KIND_AGENT, REF_KIND_ROUTER, REF_KIND_ACTION)
    }

    def add(
        kind: str, node_id: Any, label: Any, node_type: Any = None, *names: Any
    ) -> None:
        if not node_id:
            return
        node_id = str(node_id)
        label = str(label or node_id)
        index = indexes[kind]
        index["labels_by_id"][node_id] = label
        if node_type:
            index["types_by_id"][node_id] = str(node_type)
        for name in (label, *names):
            if not name:
                continue
            index["ids_by_name"].setdefault(_normalize_name(name), {})[node_id] = label

    for agent in catalog.get("agents", []):
        add(REF_KIND_AGENT, agent.get("id"), agent.get("label"), agent.get("type"))
        for tool in agent.get("tools", []):
            add(
                REF_KIND_TOOL,
                tool.get("id"),
                tool.get("label"),
                tool.get("type"),
                tool.get("name"),
            )
    for router in catalog.get("routers", []):
        # Every router is a routerNode, so a type mismatch cannot arise here.
        add(REF_KIND_ROUTER, router.get("id"), router.get("label"))
    for node in catalog.get("action_nodes", []):
        add(REF_KIND_ACTION, node.get("id"), node.get("label"), node.get("type"))
    return indexes


def resolve_node_ref(
    ref: str,
    kind: str,
    bundle_label: Optional[str],
    indexes: Dict[str, Dict[str, Any]],
    bundle_node_type: Optional[str] = None,
) -> BundleNodeResolution:
    """Match one reference: same id first, then by name/label, then the export label.

    An id match is authoritative — it is the same node, whatever it is now called
    or typed. A name match is not: the same name can belong to a different kind of
    node in a rebuilt workflow, so a differing ``node_type`` downgrades the match
    to a confirmation rather than binding the check to the wrong node.
    """
    index = indexes[kind]

    def outcome(**fields: Any) -> BundleNodeResolution:
        return BundleNodeResolution(
            ref=ref,
            kind=kind,
            label=bundle_label,
            original_type=bundle_node_type,
            **fields,
        )

    if ref in index["labels_by_id"]:
        return outcome(
            status=REF_STATUS_RESOLVED,
            resolved_id=ref,
            resolved_label=index["labels_by_id"][ref],
        )

    matches: Dict[str, str] = index["ids_by_name"].get(_normalize_name(ref), {})
    if not matches and bundle_label:
        matches = index["ids_by_name"].get(_normalize_name(bundle_label), {})

    candidates = [
        BundleRefCandidate(id=node_id, label=label)
        for node_id, label in sorted(matches.items())
    ]
    if len(candidates) == 1:
        matched_type = index["types_by_id"].get(candidates[0].id)
        mismatch = _type_mismatch_note(bundle_node_type, matched_type)
        if mismatch:
            return outcome(
                status=REF_STATUS_AMBIGUOUS, candidates=candidates, note=mismatch
            )
        return outcome(
            status=REF_STATUS_RESOLVED,
            resolved_id=candidates[0].id,
            resolved_label=candidates[0].label,
        )
    status = REF_STATUS_AMBIGUOUS if candidates else REF_STATUS_MISSING
    return outcome(status=status, candidates=candidates)


def _type_mismatch_note(
    bundle_node_type: Optional[str], matched_type: Optional[str]
) -> Optional[str]:
    """Why a name match must be confirmed, or None when the types agree.

    Either type being unknown means no judgement is possible — a bundle exported
    before types were recorded must keep resolving as it always did.
    """
    if not bundle_node_type or not matched_type:
        return None
    if bundle_node_type == matched_type:
        return None
    return (
        f"The name matches, but this node is a {matched_type} and the original "
        f"was a {bundle_node_type}."
    )


def resolve_provider_ref(
    provider_id: str,
    meta: Optional[BundleProviderRef],
    providers: List[Any],
) -> BundleProviderResolution:
    """Match a provider by id, then model name, then display name."""
    name = meta.name if meta else None
    model = meta.model if meta else None

    def resolved(provider: Any) -> BundleProviderResolution:
        return BundleProviderResolution(
            ref=provider_id,
            name=name,
            model=model,
            status=REF_STATUS_RESOLVED,
            resolved_id=str(provider.id),
            resolved_name=provider.name,
        )

    # An exact id is honoured whatever its state; a match found by name must be
    # usable, and the wizard only offers active providers.
    for provider in providers:
        if str(provider.id) == provider_id:
            return resolved(provider)
    providers = [p for p in providers if getattr(p, "is_active", 1) == 1]

    matches = [
        p
        for p in providers
        if model and p.llm_model and _normalize_name(p.llm_model) == _normalize_name(model)
    ]
    if len(matches) > 1 and name:
        narrowed = [p for p in matches if _normalize_name(p.name or "") == _normalize_name(name)]
        matches = narrowed or matches
    if not matches and name:
        matches = [
            p for p in providers if _normalize_name(p.name or "") == _normalize_name(name)
        ]
    if matches:
        return resolved(matches[0])
    return BundleProviderResolution(
        ref=provider_id, name=name, model=model, status=REF_STATUS_MISSING
    )


# ---------------------------------------------------------------------------
# Provider / case reference rewriting
# ---------------------------------------------------------------------------


def rewrite_provider_refs(
    configs: Dict[str, Any],
    provider_map: Dict[str, Optional[str]],
) -> Tuple[Dict[str, Any], List[str]]:
    """Re-point llm_provider_id fields; an unmatched provider falls back to the
    target environment's default provider (the field is removed)."""
    new_configs = dict(configs)
    warnings: List[str] = []
    for technique in _PROVIDER_TECHNIQUES:
        config = new_configs.get(technique)
        if not isinstance(config, dict) or not config.get("llm_provider_id"):
            continue
        updated = dict(config)
        mapped = provider_map.get(str(updated["llm_provider_id"]))
        if mapped:
            updated["llm_provider_id"] = mapped
        else:
            updated.pop("llm_provider_id")
            warnings.append(
                f"No matching LLM provider for {technique}; "
                "the default provider will be used."
            )
        new_configs[technique] = updated
    return new_configs, warnings


def rewrite_case_refs(
    configs: Dict[str, Any],
    case_map: Dict[str, str],
) -> Tuple[Dict[str, Any], List[str]]:
    """Re-point every turn-targeted rule's target_case_id at the recreated cases.

    A rule that also targets by (conversation, turn) just loses the stale id —
    the portable pair keeps working. A rule with neither mapping is kept but
    will grade as "target turn not found", so it is reported.
    """
    warnings: List[str] = []
    new_configs = dict(configs)
    for technique, index, rule in _rules_with_targets(configs):
        updated, warning = _repoint_rule(technique, rule, case_map)
        if warning:
            warnings.append(warning)
        config = new_configs[technique]
        rules = list(config["rules"])
        rules[index] = updated
        new_configs[technique] = {**config, "rules": rules}
    return new_configs, warnings


def _repoint_rule(
    technique: str, rule: Dict[str, Any], case_map: Dict[str, str]
) -> Tuple[Dict[str, Any], Optional[str]]:
    updated = dict(rule)
    case_ids = _rule_case_ids(updated)
    mapped = [case_map.get(case_id) for case_id in case_ids]

    if all(mapped):
        return _with_case_ids(updated, [case_id for case_id in mapped if case_id]), None

    # The portable (conversation, turn) pair still points at the right turns, so a
    # stale id is dropped rather than kept as a target that cannot resolve.
    if _has_conversation_target(updated):
        return _with_case_ids(updated, []), None

    label = _TECHNIQUE_LABELS.get(technique, technique)
    return updated, (
        f"{label} rule '{updated.get('id')}' targets a test case that "
        "is not part of the bundle; it will grade as not evaluated."
    )


def _has_conversation_target(rule: Dict[str, Any]) -> bool:
    turn_indexes = rule.get("target_turn_indexes")
    has_turns = rule.get("target_turn_index") is not None or (
        isinstance(turn_indexes, list) and bool(turn_indexes)
    )
    return rule.get("target_source_conversation_id") is not None and has_turns


def _with_case_ids(rule: Dict[str, Any], case_ids: List[str]) -> Dict[str, Any]:
    """Write case ids back in the shape the rule already used."""
    updated = {
        key: value
        for key, value in rule.items()
        if key not in ("target_case_id", "target_case_ids")
    }
    if not case_ids:
        return updated
    if isinstance(rule.get("target_case_ids"), list):
        updated["target_case_ids"] = case_ids
    else:
        updated["target_case_id"] = case_ids[0]
    return updated


# ---------------------------------------------------------------------------
# Warnings for values that may not make sense in another environment
# ---------------------------------------------------------------------------


def scan_metadata_warnings(context: str, metadata: Optional[Dict[str, Any]]) -> List[str]:
    """Flag URL- and UUID-looking values so the user reviews them after import."""
    warnings: List[str] = []
    if not isinstance(metadata, dict):
        return warnings
    for key, value in metadata.items():
        if len(warnings) >= _MAX_METADATA_WARNINGS:
            break
        if not isinstance(value, str):
            continue
        if _URL_PATTERN.search(value) or _UUID_PATTERN.match(value.strip()):
            warnings.append(
                f"{context} field '{key}' looks environment-specific; "
                "review it after import."
            )
    return warnings


def environment_warnings(configs: Dict[str, Any]) -> List[str]:
    """Notes about config values that must exist in the target environment."""
    # NLI needs no warning: the model can only be one of the platform's curated
    # options (anything else falls back to the default at run time), so the
    # choice carries nothing environment-specific.
    warnings: List[str] = []
    provenance_config = configs.get(PROVENANCE_EVAL)
    if isinstance(provenance_config, dict):
        embedding_type = provenance_config.get("embedding_type")
        if embedding_type in ("openai", "bedrock"):
            warnings.append(
                "Provenance embeddings use the target environment's "
                f"{embedding_type} credentials and endpoint settings."
            )
    return warnings


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


@inject
class EvalBundleService:
    """Builds bundles from stored evaluations and imports them elsewhere."""

    def __init__(
        self,
        suite_service: TestSuiteService,
        workflow_service: WorkflowService,
        llm_provider_service: LlmProviderService,
        case_repo: TestCaseRepository,
    ) -> None:
        self.suites = suite_service
        self.workflows = workflow_service
        self.providers = llm_provider_service
        self.case_repo = case_repo

    # ---- Export -----------------------------------------------------------

    async def export_evaluation(self, evaluation_id: UUID) -> EvaluationBundle:
        evaluation = await self.suites.get_evaluation(evaluation_id)
        suite = await self.suites.get_suite(evaluation.suite_id)
        cases = await self.suites.list_cases_for_suite(evaluation.suite_id)
        workflow_id = evaluation.workflow_id or suite.workflow_id

        configs, notes = sanitize_technique_configs(evaluation.technique_configs)
        input_metadata, metadata_notes = sanitize_secret_keys(
            evaluation.input_metadata, "the evaluation input metadata"
        )
        default_metadata, default_notes = sanitize_secret_keys(
            suite.default_input_metadata, "the dataset input metadata"
        )
        notes.extend(metadata_notes + default_notes)

        # Case inputs merge into the same run payload as the metadata above, so
        # they get the same secret stripping.
        bundle_cases: List[BundleCase] = []
        for index, case in enumerate(cases, 1):
            input_data, case_notes = sanitize_secret_keys(
                case.input_data, f"test case {index} input"
            )
            expected_output, expected_notes = sanitize_secret_keys(
                case.expected_output, f"test case {index} expected output"
            )
            notes.extend(case_notes + expected_notes)
            bundle_cases.append(
                _bundle_case(case, index, input_data or {}, expected_output)
            )

        return EvaluationBundle(
            source=await self._bundle_source(workflow_id),
            evaluation=BundleEvaluation(
                name=evaluation.name,
                description=evaluation.description,
                techniques=list(evaluation.techniques or []),
                technique_configs=configs or None,
                input_metadata=input_metadata,
            ),
            dataset=BundleDataset(
                name=suite.name,
                description=suite.description,
                default_input_metadata=default_metadata,
                cases=bundle_cases,
            ),
            references=await self._bundle_references(workflow_id, configs, cases),
            notes=notes,
        )

    async def _bundle_source(self, workflow_id: Optional[UUID]) -> BundleSource:
        if not workflow_id:
            return BundleSource()
        try:
            workflow = await self.workflows.get_by_id(UUID(str(workflow_id)))
        except Exception:  # pylint: disable=broad-except
            return BundleSource(workflow_id=workflow_id)
        return BundleSource(
            workflow_id=workflow_id,
            workflow_name=workflow.name,
            workflow_version=workflow.version,
        )

    async def _bundle_references(
        self,
        workflow_id: Optional[UUID],
        configs: Dict[str, Any],
        cases: List[TestCaseInDB],
    ) -> BundleReferences:
        indexes = build_node_indexes(await self._workflow_catalog(workflow_id))
        nodes: Dict[str, BundleNodeRef] = {}
        for ref, kind in collect_node_refs(configs):
            nodes[ref] = BundleNodeRef(
                label=indexes[kind]["labels_by_id"].get(ref),
                kind=kind,
                node_type=indexes[kind]["types_by_id"].get(ref),
            )

        providers: Dict[str, BundleProviderRef] = {}
        if collect_provider_ids(configs):
            known = {str(p.id): p for p in await self.providers.get_all_minimal()}
            for provider_id in collect_provider_ids(configs):
                provider = known.get(provider_id)
                providers[provider_id] = BundleProviderRef(
                    name=provider.name if provider else None,
                    provider=provider.llm_model_provider if provider else None,
                    model=provider.llm_model if provider else None,
                )

        local_ids = {str(case.id): index for index, case in enumerate(cases, 1)}
        case_refs = {
            case_id: local_ids[case_id]
            for case_id in collect_case_ids(configs)
            if case_id in local_ids
        }
        return BundleReferences(nodes=nodes, llm_providers=providers, cases=case_refs)

    async def _workflow_catalog(self, workflow_id: Optional[UUID]) -> Dict[str, Any]:
        if not workflow_id:
            return {}
        try:
            catalog = await self.suites.get_evaluation_tool_catalog(
                UUID(str(workflow_id))
            )
        except Exception:  # pylint: disable=broad-except
            return {}
        return catalog.model_dump()

    # ---- Import -----------------------------------------------------------

    async def preview_import(
        self, request: EvaluationImportPreviewRequest
    ) -> EvaluationImportPreview:
        bundle = request.bundle
        _validate_bundle_header(bundle)
        target_workflow = await self.workflows.get_by_id(request.target_workflow_id)
        resolution = await self._resolve_against_target(
            bundle, request.target_workflow_id
        )

        existing_dataset = await self._find_existing_dataset(
            bundle.dataset.name, request.target_workflow_id
        )
        workflow_name_matches = bool(
            bundle.source.workflow_name
            and _normalize_name(bundle.source.workflow_name)
            == _normalize_name(target_workflow.name)
        )
        can_import = all(
            ref.status == REF_STATUS_RESOLVED for ref in resolution["node_refs"]
        )
        return EvaluationImportPreview(
            dropping_all_would_empty=self._dropping_all_would_empty(
                bundle, resolution
            ),
            evaluation_name=bundle.evaluation.name,
            dataset_name=bundle.dataset.name,
            case_count=len(bundle.dataset.cases),
            existing_dataset=existing_dataset,
            workflow_name_matches=workflow_name_matches,
            node_refs=resolution["node_refs"],
            provider_refs=resolution["provider_refs"],
            warnings=self._preview_warnings(bundle, resolution),
            can_import=can_import,
        )

    async def _workflow_version_ids(self, workflow_id: UUID) -> set:
        """Every version of this workflow, as id strings.

        Datasets are attached to whichever version was current when they were
        made, so scoping to a single version would keep re-creating duplicates
        the moment an import targets a different one.
        """
        workflows = await self.workflows.get_all_minimal()
        target = next((w for w in workflows if str(w.id) == str(workflow_id)), None)
        if not target or not target.agent_id:
            return {str(workflow_id)}
        return {
            str(w.id)
            for w in workflows
            if w.agent_id and str(w.agent_id) == str(target.agent_id)
        }

    async def _find_existing_dataset(
        self, name: str, target_workflow_id: UUID
    ) -> Optional[BundleExistingDataset]:
        """A dataset on the target workflow already using this name.

        Scoped to the workflow: two workflows can each own a "Regression set",
        and reusing the other one's would grade the wrong cases.
        """
        found = await self._existing_datasets_by_name([name], target_workflow_id)
        return found.get(_normalize_name(name))

    async def _existing_datasets_by_name(
        self, names: List[str], target_workflow_id: UUID
    ) -> Dict[str, BundleExistingDataset]:
        """Look several dataset names up in one pass, keyed by normalized name.

        A set import asks about every dataset in the file, and scanning the
        target's suites once per name turns a large file into a long run of
        identical full scans.
        """
        wanted = {_normalize_name(name) for name in names}
        if not wanted:
            return {}
        version_ids = await self._workflow_version_ids(target_workflow_id)
        matches: Dict[str, Any] = {}
        for suite in await self.suites.list_suites():
            key = _normalize_name(suite.name)
            if key not in wanted or key in matches:
                continue
            if str(suite.workflow_id) in version_ids:
                matches[key] = suite
        return {
            key: BundleExistingDataset(
                id=suite.id,
                name=suite.name,
                case_count=len(await self.suites.list_cases_for_suite(suite.id)),
            )
            for key, suite in matches.items()
        }

    def _dropping_all_would_empty(
        self, bundle: EvaluationBundle, resolution: Dict[str, Any]
    ) -> bool:
        """Whether dropping the unmatched rules would leave nothing to grade.

        Import refuses that outcome, so the dialog needs to know before it
        offers dropping as the way forward.
        """
        if not bundle.evaluation.techniques:
            return False
        configs, _ = sanitize_technique_configs(bundle.evaluation.technique_configs)
        node_map = {
            ref_key(ref.ref, ref.kind): ref.resolved_id
            for ref in resolution["node_refs"]
            if ref.status == REF_STATUS_RESOLVED and ref.resolved_id
        }
        _, dropped = rewrite_node_refs(configs, _map_resolver(node_map), [])
        return all(
            technique in dropped for technique in bundle.evaluation.techniques
        )

    async def import_bundle(
        self, request: EvaluationImportRequest
    ) -> EvaluationImportResult:
        bundle = request.bundle
        _validate_bundle_header(bundle)
        await self.workflows.get_by_id(request.target_workflow_id)
        resolution = await self._resolve_against_target(
            bundle, request.target_workflow_id
        )

        node_map = self._node_map(resolution, request)
        configs, _ = sanitize_technique_configs(
            bundle.evaluation.technique_configs
        )
        dropped_rules: List[str] = []
        drop_log = dropped_rules if request.drop_unresolved_rules else None
        try:
            configs, dropped_techniques = rewrite_node_refs(
                configs, _map_resolver(node_map), drop_log
            )
        except UnresolvedRefError as error:
            raise AppException(
                status_code=400,
                error_key=ErrorKey.EVALUATION_BUNDLE_INVALID,
                error_detail=(
                    f"{error.reason.capitalize()}. Resolve it manually or "
                    "allow dropping the rule."
                ),
            ) from error

        provider_map = {
            ref.ref: ref.resolved_id for ref in resolution["provider_refs"]
        }
        configs, provider_warnings = rewrite_provider_refs(configs, provider_map)
        techniques = [
            technique
            for technique in bundle.evaluation.techniques
            if technique not in dropped_techniques
        ]
        if bundle.evaluation.techniques and not techniques:
            # An empty technique list does NOT mean "grade nothing": the run loop
            # falls back to the platform defaults, so this would silently score
            # the evaluation with checks nobody chose. Refuse instead.
            raise AppException(
                status_code=400,
                error_key=ErrorKey.EVALUATION_BUNDLE_INVALID,
                error_detail=(
                    "Every check was dropped, so the imported evaluation would "
                    "grade nothing. Map the references to this workflow, or "
                    "choose a different target workflow."
                ),
            )
        self._validate_tool_config(configs, resolution["catalog"])

        reuse_suite_id = request.existing_suite_id
        if reuse_suite_id:
            suite_id, case_map, case_count, reuse_warnings = await self._reuse_dataset(
                reuse_suite_id, bundle, request.target_workflow_id
            )
        else:
            suite_id, case_map, case_count, reuse_warnings = await self._new_dataset(
                request.target_workflow_id, bundle
            )

        configs, case_warnings = rewrite_case_refs(configs, case_map)
        try:
            evaluation = await self.suites.create_evaluation(
                TestEvaluationCreate(
                    name=bundle.evaluation.name,
                    description=bundle.evaluation.description,
                    suite_id=suite_id,
                    workflow_id=request.target_workflow_id,
                    techniques=techniques,
                    technique_configs=configs or None,
                    input_metadata=bundle.evaluation.input_metadata,
                )
            )
        except Exception:
            # Only a dataset this import created may be cleaned up; an existing
            # one belongs to other evaluations.
            if not reuse_suite_id:
                await self._cleanup_suite(suite_id)
            raise
        return EvaluationImportResult(
            evaluation_id=evaluation.id,
            suite_id=suite_id,
            case_count=case_count,
            reused_dataset=bool(reuse_suite_id),
            dropped_rules=dropped_rules,
            warnings=provider_warnings + case_warnings + reuse_warnings,
        )

    async def _new_dataset(
        self, target_workflow_id: UUID, bundle: EvaluationBundle
    ) -> Tuple[UUID, Dict[str, str], int, List[str]]:
        """Create the bundle's dataset and its cases."""
        suite = await self.suites.create_suite(
            TestSuiteCreate(
                name=bundle.dataset.name,
                description=bundle.dataset.description,
                workflow_id=target_workflow_id,
                default_input_metadata=bundle.dataset.default_input_metadata,
            )
        )
        # Repos commit per call, so a later failure can't roll the suite back —
        # clean it up explicitly instead of leaving an orphan dataset behind.
        try:
            case_map = await self._create_cases(suite.id, bundle)
        except Exception:
            await self._cleanup_suite(suite.id)
            raise
        return suite.id, case_map, len(bundle.dataset.cases), []

    async def _reuse_dataset(
        self, suite_id: UUID, bundle: EvaluationBundle, target_workflow_id: UUID
    ) -> Tuple[UUID, Dict[str, str], int, List[str]]:
        """Attach to an existing dataset, leaving its cases untouched.

        Turn-targeted rules are re-pointed at the existing cases by
        (conversation, turn), the only pairing stable across environments.
        """
        try:
            suite = await self.suites.get_suite(suite_id)
        except AppException as error:
            raise AppException(
                status_code=400,
                error_key=ErrorKey.EVALUATION_BUNDLE_INVALID,
                error_detail="The dataset to reuse no longer exists.",
            ) from error
        version_ids = await self._workflow_version_ids(target_workflow_id)
        if str(suite.workflow_id) not in version_ids:
            raise AppException(
                status_code=400,
                error_key=ErrorKey.EVALUATION_BUNDLE_INVALID,
                error_detail=(
                    "The dataset to reuse belongs to a different workflow."
                ),
            )

        existing = await self.suites.list_cases_for_suite(suite.id)
        case_map = _case_map_for_existing(bundle, existing)
        warnings: List[str] = []
        if len(existing) != len(bundle.dataset.cases):
            warnings.append(
                f"Reused dataset '{suite.name}' has {len(existing)} case(s) while "
                f"the bundle has {len(bundle.dataset.cases)}; the evaluation grades "
                "the existing cases."
            )
        return suite.id, case_map, len(existing), warnings

    async def _resolve_against_target(
        self, bundle: EvaluationBundle, target_workflow_id: UUID
    ) -> Dict[str, Any]:
        catalog = await self._workflow_catalog(target_workflow_id)
        indexes = build_node_indexes(catalog)
        configs = bundle.evaluation.technique_configs or {}

        node_refs = [
            resolve_node_ref(
                ref,
                kind,
                _bundle_label(bundle, ref),
                indexes,
                _bundle_node_type(bundle, ref),
            )
            for ref, kind in collect_node_refs(configs)
        ]
        provider_refs: List[BundleProviderResolution] = []
        provider_ids = collect_provider_ids(configs)
        if provider_ids:
            providers = await self.providers.get_all_minimal()
            provider_refs = [
                resolve_provider_ref(
                    provider_id,
                    bundle.references.llm_providers.get(provider_id),
                    providers,
                )
                for provider_id in provider_ids
            ]
        return {
            "catalog": catalog,
            "node_refs": node_refs,
            "provider_refs": provider_refs,
        }

    def _node_map(
        self,
        resolution: Dict[str, Any],
        request: EvaluationImportRequest,
    ) -> Dict[str, str]:
        """Auto-resolved references plus the caller's manual picks (validated).

        Keyed by ``ref_key(ref, kind)``: one value may appear under two kinds
        (an agent node id is also an action node), and each needs its own
        resolution against its own kind's catalog.
        """
        indexes = build_node_indexes(resolution["catalog"])
        node_map: Dict[str, str] = {
            ref_key(ref.ref, ref.kind): ref.resolved_id
            for ref in resolution["node_refs"]
            if ref.status == REF_STATUS_RESOLVED and ref.resolved_id
        }
        kind_by_key = {
            ref_key(ref.ref, ref.kind): ref.kind for ref in resolution["node_refs"]
        }
        for key, chosen_id in request.resolutions.items():
            kind = kind_by_key.get(key)
            if not kind:
                continue
            if chosen_id not in indexes[kind]["labels_by_id"]:
                raise AppException(
                    status_code=400,
                    error_key=ErrorKey.EVALUATION_BUNDLE_INVALID,
                    error_detail=(
                        f"Resolution for '{key}' points at unknown {kind} "
                        f"'{chosen_id}' in the target workflow."
                    ),
                )
            node_map[key] = chosen_id
        return node_map

    def _validate_tool_config(
        self, configs: Dict[str, Any], catalog: Dict[str, Any]
    ) -> None:
        """Fail before anything is created if the tool config cannot canonicalize."""
        if TOOL_USED not in configs or not isinstance(configs.get(TOOL_USED), dict):
            return
        resolve_tool_id, resolve_agent_id, _, all_tool_ids = resolvers_from_agents(
            catalog.get("agents", [])
        )
        try:
            canonicalize_tool_usage_config(
                configs[TOOL_USED],
                resolve_tool_id=resolve_tool_id,
                resolve_agent_id=resolve_agent_id,
                all_tool_ids=all_tool_ids,
            )
        except ValueError as error:
            # str(error) here can be a raw pydantic ValidationError over
            # caller-supplied JSON, and this error key's detail is returned to
            # clients — log the specifics, return a fixed sentence.
            logger.warning(
                "Tool usage config in an imported bundle could not be "
                "canonicalized: %s",
                error,
            )
            raise AppException(
                status_code=400,
                error_key=ErrorKey.EVALUATION_BUNDLE_INVALID,
                error_detail=(
                    "The Tool Usage configuration could not be matched to this "
                    "workflow. Check its rules against the target workflow's tools."
                ),
            ) from error

    async def _cleanup_suite(self, suite_id: UUID) -> None:
        """Best-effort removal of a half-imported dataset; never masks the cause."""
        try:
            await self.suites.delete_suite(suite_id)
        except Exception:  # pylint: disable=broad-except
            logger.warning(
                "Failed to clean up suite %s after a failed import", suite_id,
                exc_info=True,
            )

    async def _create_cases(
        self, suite_id: UUID, bundle: EvaluationBundle
    ) -> Dict[str, str]:
        """Create the dataset's cases; map exported case ids to the new ids."""
        models = [
            TestCaseModel(
                suite_id=suite_id,
                input_data=case.input_data,
                expected_output=case.expected_output,
                tags=case.tags,
                weight=case.weight,
                source_conversation_id=case.source_conversation_id,
                turn_index=case.turn_index,
            )
            for case in bundle.dataset.cases
        ]
        created = await self.case_repo.create_many(models) if models else []
        new_id_by_local = {
            case.local_id: str(model.id)
            for case, model in zip(bundle.dataset.cases, created)
        }
        return {
            case_id: new_id_by_local[local_id]
            for case_id, local_id in bundle.references.cases.items()
            if local_id in new_id_by_local
        }

    def _preview_warnings(
        self, bundle: EvaluationBundle, resolution: Dict[str, Any]
    ) -> List[str]:
        configs = bundle.evaluation.technique_configs or {}
        warnings = list(bundle.notes)
        warnings.extend(environment_warnings(configs))
        warnings.extend(
            scan_metadata_warnings(
                "Evaluation input metadata", bundle.evaluation.input_metadata
            )
        )
        warnings.extend(
            scan_metadata_warnings(
                "Dataset input metadata", bundle.dataset.default_input_metadata
            )
        )
        for provider_ref in resolution["provider_refs"]:
            if provider_ref.status == REF_STATUS_MISSING:
                warnings.append(
                    "No matching LLM provider was found; the default provider "
                    "will be used for judged checks."
                )
        unmapped_cases = [
            case_id
            for case_id in collect_case_ids(configs)
            if case_id not in bundle.references.cases
        ]
        if unmapped_cases:
            warnings.append(
                "Some turn-targeted rules reference test cases that are not part "
                "of the bundle and will grade as not evaluated."
            )
        return warnings

    # ---- Set export / import ------------------------------------------------

    async def export_workflow_evaluations(
        self, workflow_id: UUID
    ) -> EvaluationBundleSet:
        """Every evaluation of the workflow (all versions) in one file, with
        each shared dataset stored once."""
        await self.workflows.get_by_id(workflow_id)
        evaluations = await self._group_evaluations(workflow_id)
        if not evaluations:
            raise AppException(
                status_code=404,
                error_key=ErrorKey.NOT_FOUND,
                error_detail="This workflow has no evaluations to export.",
            )
        if len(evaluations) > MAX_SET_EVALUATIONS:
            raise AppException(
                status_code=400,
                error_key=ErrorKey.EVALUATION_BUNDLE_INVALID,
                error_detail=(
                    f"This workflow has {len(evaluations)} evaluations; the "
                    f"export limit is {MAX_SET_EVALUATIONS}."
                ),
            )

        datasets: Dict[str, BundleSetDataset] = {}
        items: List[BundleSetItem] = []
        for evaluation in evaluations:
            bundle = await self.export_evaluation(evaluation.id)
            suite_key = str(evaluation.suite_id)
            if suite_key not in datasets:
                datasets[suite_key] = BundleSetDataset(
                    local_id=len(datasets) + 1, **bundle.dataset.model_dump()
                )
            items.append(
                BundleSetItem(
                    evaluation=bundle.evaluation,
                    dataset_local_id=datasets[suite_key].local_id,
                    references=bundle.references,
                    notes=bundle.notes,
                )
            )

        # Both bounds match the import side: a file this export refuses to cap
        # would be rejected wholesale on the way back in.
        oversized = next(
            (d for d in datasets.values() if len(d.cases) > MAX_BUNDLE_CASES),
            None,
        )
        if oversized:
            raise AppException(
                status_code=400,
                error_key=ErrorKey.EVALUATION_BUNDLE_INVALID,
                error_detail=(
                    f"Dataset '{oversized.name}' has {len(oversized.cases)} "
                    f"test cases; the limit is {MAX_BUNDLE_CASES}."
                ),
            )
        total_cases = sum(len(d.cases) for d in datasets.values())
        if total_cases > MAX_SET_TOTAL_CASES:
            raise AppException(
                status_code=400,
                error_key=ErrorKey.EVALUATION_BUNDLE_INVALID,
                error_detail=(
                    f"The datasets hold {total_cases} test cases in total; the "
                    f"export limit is {MAX_SET_TOTAL_CASES}."
                ),
            )
        return EvaluationBundleSet(
            source=await self._bundle_source(workflow_id),
            datasets=list(datasets.values()),
            evaluations=items,
        )

    async def _group_evaluations(self, workflow_id: UUID) -> List[Any]:
        """The workflow group's evaluations, ordered by name for a stable file."""
        version_ids = await self._workflow_version_ids(workflow_id)
        evaluations = await self.suites.list_evaluations()
        matched = [e for e in evaluations if str(e.workflow_id) in version_ids]
        return sorted(matched, key=lambda e: _normalize_name(e.name))

    async def preview_set_import(
        self, request: EvaluationSetImportPreviewRequest
    ) -> EvaluationSetImportPreview:
        bundle_set = request.bundle_set
        _validate_set_header(bundle_set)
        target_workflow = await self.workflows.get_by_id(request.target_workflow_id)
        resolution = await self._resolve_set_refs(
            bundle_set, request.target_workflow_id
        )
        existing_names = await self._existing_evaluation_names(
            request.target_workflow_id
        )

        datasets_by_id = {d.local_id: d for d in bundle_set.datasets}
        keys_by_item = resolution["keys_by_item"]
        item_previews: List[EvaluationSetItemPreview] = []
        warnings: List[str] = []
        for index, item in enumerate(bundle_set.evaluations):
            dataset = datasets_by_id[item.dataset_local_id]
            item_bundle = _item_bundle(
                bundle_set, item, resolution["merged_nodes"]
            )
            item_previews.append(
                EvaluationSetItemPreview(
                    name=item.evaluation.name,
                    dataset_name=dataset.name,
                    case_count=len(dataset.cases),
                    already_exists=_normalize_name(item.evaluation.name)
                    in existing_names,
                    dropping_all_would_empty=self._dropping_all_would_empty(
                        item_bundle, resolution
                    ),
                    node_ref_keys=keys_by_item[index],
                )
            )
            warnings.extend(self._preview_warnings(item_bundle, resolution))

        existing_by_name = await self._existing_datasets_by_name(
            [d.name for d in bundle_set.datasets], request.target_workflow_id
        )
        # Only the first dataset of a given name can attach to the target's own
        # copy; the import gives every later namesake its own, so promising
        # reuse for all of them would contradict what actually happens.
        claimed_names: set = set()
        dataset_previews = []
        for dataset in bundle_set.datasets:
            name_key = _normalize_name(dataset.name)
            existing = (
                None if name_key in claimed_names else existing_by_name.get(name_key)
            )
            claimed_names.add(name_key)
            dataset_previews.append(
                BundleSetDatasetPreview(
                    local_id=dataset.local_id,
                    name=dataset.name,
                    case_count=len(dataset.cases),
                    existing_dataset=existing,
                )
            )
        workflow_name_matches = bool(
            bundle_set.source.workflow_name
            and _normalize_name(bundle_set.source.workflow_name)
            == _normalize_name(target_workflow.name)
        )
        return EvaluationSetImportPreview(
            workflow_name_matches=workflow_name_matches,
            evaluations=item_previews,
            datasets=dataset_previews,
            node_refs=resolution["node_refs"],
            provider_refs=resolution["provider_refs"],
            warnings=list(dict.fromkeys(warnings)),
            can_import=all(
                ref.status == REF_STATUS_RESOLVED
                for ref in resolution["node_refs"]
            ),
        )

    async def _resolve_set_refs(
        self, bundle_set: EvaluationBundleSet, target_workflow_id: UUID
    ) -> Dict[str, Any]:
        """The union of every item's references, each resolved exactly once.

        Items are exported against their own pinned version, so one ref can
        carry a label in one item and nothing in another. Resolution therefore
        uses the best metadata ANY item recorded, and ``import_bundle_set``
        replays the outcome to every item — a per-item re-resolution could
        otherwise disagree with the preview the user approved.
        """
        catalog = await self._workflow_catalog(target_workflow_id)
        indexes = build_node_indexes(catalog)
        metadata = _merge_set_node_metadata(bundle_set)
        merged_nodes = metadata["nodes"]
        node_refs = [
            resolve_node_ref(
                ref,
                kind,
                merged_nodes[ref].label,
                indexes,
                merged_nodes[ref].node_type,
            )
            for ref, kind in metadata["refs_by_key"].values()
        ]

        provider_refs: List[BundleProviderResolution] = []
        provider_meta = _merge_set_provider_metadata(bundle_set)
        if provider_meta:
            providers = await self.providers.get_all_minimal()
            provider_refs = [
                resolve_provider_ref(provider_id, meta, providers)
                for provider_id, meta in provider_meta.items()
            ]
        return {
            "catalog": catalog,
            "node_refs": node_refs,
            "provider_refs": provider_refs,
            "keys_by_item": metadata["keys_by_item"],
            "merged_nodes": merged_nodes,
        }

    async def _existing_evaluation_names(self, target_workflow_id: UUID) -> set:
        """Names already used by the target workflow group's evaluations."""
        version_ids = await self._workflow_version_ids(target_workflow_id)
        evaluations = await self.suites.list_evaluations()
        return {
            _normalize_name(e.name)
            for e in evaluations
            if str(e.workflow_id) in version_ids
        }

    async def import_bundle_set(
        self, request: EvaluationSetImportRequest
    ) -> EvaluationSetImportResult:
        """Import the selected evaluations one by one; a failure is recorded on
        its item and never stops the rest of the batch."""
        bundle_set = request.bundle_set
        _validate_set_header(bundle_set)
        await self.workflows.get_by_id(request.target_workflow_id)
        selected = _selected_items(bundle_set, request.include)
        existing_names = (
            await self._existing_evaluation_names(request.target_workflow_id)
            if request.skip_existing
            else set()
        )

        # Every item resolves from the set-wide merge the preview used, so none
        # of them can reach a verdict the user was not shown.
        resolution = await self._resolve_set_refs(
            bundle_set, request.target_workflow_id
        )
        batch = _BatchState(
            existing_names=existing_names,
            resolutions=request.resolutions,
            merged_nodes=resolution["merged_nodes"],
        )
        results = [
            await self._import_set_item(bundle_set, item, request, batch)
            for item in selected
        ]
        return EvaluationSetImportResult(
            results=results,
            imported=sum(r.status == SET_ITEM_IMPORTED for r in results),
            skipped=sum(r.status == SET_ITEM_SKIPPED for r in results),
            failed=sum(r.status == SET_ITEM_FAILED for r in results),
        )

    async def _import_set_item(
        self,
        bundle_set: EvaluationBundleSet,
        item: BundleSetItem,
        request: EvaluationSetImportRequest,
        batch: "_BatchState",
    ) -> EvaluationSetItemResult:
        name = item.evaluation.name
        if _normalize_name(name) in batch.existing_names:
            return EvaluationSetItemResult(
                name=name,
                status=SET_ITEM_SKIPPED,
                detail=(
                    "An evaluation with this name already exists on the "
                    "target workflow."
                ),
            )
        try:
            result = await self.import_bundle(
                EvaluationImportRequest(
                    bundle=_item_bundle(bundle_set, item, batch.merged_nodes),
                    target_workflow_id=request.target_workflow_id,
                    existing_suite_id=await self._suite_to_reuse(
                        bundle_set, item, request, batch
                    ),
                    resolutions=_resolutions_for_item(item, batch.resolutions),
                    drop_unresolved_rules=request.drop_unresolved_rules,
                )
            )
        except AppException as error:
            logger.warning(
                "Importing evaluation '%s' from a bundle set failed: %s (%s)",
                name,
                error.error_key,
                error.error_detail,
            )
            return EvaluationSetItemResult(
                name=name,
                status=SET_ITEM_FAILED,
                detail=_client_safe_item_detail(error),
            )
        except Exception:  # pylint: disable=broad-except
            logger.exception(
                "Importing evaluation '%s' from a bundle set failed", name
            )
            return EvaluationSetItemResult(
                name=name,
                status=SET_ITEM_FAILED,
                detail=_GENERIC_ITEM_FAILURE,
            )

        batch.suites_by_local[item.dataset_local_id] = result.suite_id
        batch.dataset_owner_by_name.setdefault(
            _normalize_name(_dataset_of(bundle_set, item).name),
            item.dataset_local_id,
        )
        if request.skip_existing:
            # A second copy of the same name inside the file must not slip past
            # the check that only looked at the database.
            batch.existing_names.add(_normalize_name(name))
        return EvaluationSetItemResult(
            name=name,
            status=SET_ITEM_IMPORTED,
            evaluation_id=result.evaluation_id,
            suite_id=result.suite_id,
            case_count=result.case_count,
            reused_dataset=result.reused_dataset,
            dropped_rules=result.dropped_rules,
            warnings=result.warnings,
        )

    async def _suite_to_reuse(
        self,
        bundle_set: EvaluationBundleSet,
        item: BundleSetItem,
        request: EvaluationSetImportRequest,
        batch: "_BatchState",
    ) -> Optional[UUID]:
        """The dataset this item should attach to, if one already exists."""
        batch_suite_id = batch.suites_by_local.get(item.dataset_local_id)
        if batch_suite_id:
            return batch_suite_id
        dataset = _dataset_of(bundle_set, item)
        owner = batch.dataset_owner_by_name.get(_normalize_name(dataset.name))
        if owner is not None and owner != item.dataset_local_id:
            # Another dataset in this file already took that name. The file
            # keeps the two apart, so this one gets its own copy rather than
            # collapsing onto the first and losing its cases.
            return None
        found = await self._find_existing_dataset(
            dataset.name, request.target_workflow_id
        )
        return found.id if found else None


def _bundle_case(
    case: TestCaseInDB,
    local_id: int,
    input_data: Dict[str, Any],
    expected_output: Optional[Dict[str, Any]],
) -> BundleCase:
    return BundleCase(
        local_id=local_id,
        input_data=input_data,
        expected_output=expected_output,
        tags=case.tags,
        weight=case.weight,
        source_conversation_id=case.source_conversation_id,
        turn_index=case.turn_index,
    )


def _case_map_for_existing(
    bundle: EvaluationBundle, existing: List[TestCaseInDB]
) -> Dict[str, str]:
    """Map the bundle's referenced case ids onto an existing dataset's cases.

    Matching is by (conversation, turn), which survives across environments;
    a manually created case has no such pairing and stays unmapped, which
    ``rewrite_case_refs`` reports rather than mis-pointing the rule.
    """
    existing_by_turn = {
        (str(case.source_conversation_id), case.turn_index): str(case.id)
        for case in existing
        if case.source_conversation_id is not None and case.turn_index is not None
    }
    new_id_by_local: Dict[int, str] = {}
    for case in bundle.dataset.cases:
        if case.source_conversation_id is None or case.turn_index is None:
            continue
        matched = existing_by_turn.get(
            (str(case.source_conversation_id), case.turn_index)
        )
        if matched:
            new_id_by_local[case.local_id] = matched
    return {
        case_id: new_id_by_local[local_id]
        for case_id, local_id in bundle.references.cases.items()
        if local_id in new_id_by_local
    }


def _bundle_label(bundle: EvaluationBundle, ref: str) -> Optional[str]:
    node = bundle.references.nodes.get(ref)
    return node.label if node else None


def _bundle_node_type(bundle: EvaluationBundle, ref: str) -> Optional[str]:
    node = bundle.references.nodes.get(ref)
    return node.node_type if node else None


def _map_resolver(node_map: Dict[str, str]) -> Resolver:
    def resolve(value: str, kind: str) -> str:
        mapped = node_map.get(ref_key(value, kind))
        if not mapped:
            raise UnresolvedRefError(value, kind)
        return mapped

    return resolve


def _resolutions_for_item(
    item: BundleSetItem, resolutions: Dict[str, str]
) -> Dict[str, str]:
    """Only the picks this item's own references need.

    An item's request carries its own resolution cap, and the set's union plus
    the caller's manual picks can together exceed it — sending the whole map
    would fail every item on a size limit that none of them actually reach.
    """
    configs = item.evaluation.technique_configs or {}
    keys = {ref_key(ref, kind) for ref, kind in collect_node_refs(configs)}
    return {key: value for key, value in resolutions.items() if key in keys}


def _merge_set_node_metadata(bundle_set: EvaluationBundleSet) -> Dict[str, Any]:
    """Best label and type recorded for each ref across all items, the union of
    ref keys, and the keys each item uses.

    First non-empty value wins: an item pinned to a version where the node was
    deleted records nothing, and that absence must not hide the label a sibling
    item carries.
    """
    labels: Dict[str, str] = {}
    types: Dict[str, str] = {}
    kinds: Dict[str, str] = {}
    refs_by_key: Dict[str, Tuple[str, str]] = {}
    keys_by_item: List[List[str]] = []
    for item in bundle_set.evaluations:
        configs = item.evaluation.technique_configs or {}
        item_keys: List[str] = []
        for ref, kind in collect_node_refs(configs):
            key = ref_key(ref, kind)
            refs_by_key.setdefault(key, (ref, kind))
            kinds.setdefault(ref, kind)
            if key not in item_keys:
                item_keys.append(key)
            node = item.references.nodes.get(ref)
            if not node:
                continue
            if node.label and ref not in labels:
                labels[ref] = node.label
            if node.node_type and ref not in types:
                types[ref] = node.node_type
        keys_by_item.append(item_keys)
    return {
        "refs_by_key": refs_by_key,
        "keys_by_item": keys_by_item,
        # The merged view every item resolves from, so no item can reach a
        # different verdict than the set-wide one the user was shown.
        "nodes": {
            ref: BundleNodeRef(
                label=labels.get(ref), kind=kind, node_type=types.get(ref)
            )
            for ref, kind in kinds.items()
        },
    }


def _merge_set_provider_metadata(
    bundle_set: EvaluationBundleSet,
) -> Dict[str, Optional[BundleProviderRef]]:
    """Each provider id once, described by the first item that recorded it."""
    merged: Dict[str, Optional[BundleProviderRef]] = {}
    for item in bundle_set.evaluations:
        configs = item.evaluation.technique_configs or {}
        for provider_id in collect_provider_ids(configs):
            if merged.get(provider_id) is not None:
                continue
            merged[provider_id] = item.references.llm_providers.get(provider_id)
    return merged


def _dataset_of(
    bundle_set: EvaluationBundleSet, item: BundleSetItem
) -> BundleSetDataset:
    return next(
        d for d in bundle_set.datasets if d.local_id == item.dataset_local_id
    )


def _item_bundle(
    bundle_set: EvaluationBundleSet,
    item: BundleSetItem,
    merged_nodes: Optional[Dict[str, BundleNodeRef]] = None,
) -> EvaluationBundle:
    """A self-contained single bundle for one set item, so every single-bundle
    rule (validation, resolution, dataset reuse) applies unchanged.

    ``merged_nodes`` swaps the item's own node metadata for the set-wide merge.
    Resolution is deterministic in its inputs, so an item given the merged view
    reaches exactly the union's verdict: it can neither fail on a ref the
    preview resolved, nor quietly resolve one the preview refused.
    """
    dataset = _dataset_of(bundle_set, item)
    references = item.references
    if merged_nodes is not None:
        references = BundleReferences(
            nodes=merged_nodes,
            llm_providers=item.references.llm_providers,
            # Case ids are this item's own; only node metadata is shared.
            cases=item.references.cases,
        )
    return EvaluationBundle(
        source=bundle_set.source,
        evaluation=item.evaluation,
        dataset=BundleDataset(**dataset.model_dump(exclude={"local_id"})),
        references=references,
        notes=item.notes,
    )


def _selected_items(
    bundle_set: EvaluationBundleSet, include: Optional[List[int]]
) -> List[BundleSetItem]:
    """The items the caller picked, in file order; ``None`` selects all."""
    if include is None:
        return list(bundle_set.evaluations)
    items = []
    for position in dict.fromkeys(include):
        if position < 0 or position >= len(bundle_set.evaluations):
            raise AppException(
                status_code=400,
                error_key=ErrorKey.EVALUATION_BUNDLE_INVALID,
                error_detail=f"Selection index {position} is out of range.",
            )
        items.append(bundle_set.evaluations[position])
    return items


def _validate_set_header(bundle_set: EvaluationBundleSet) -> None:
    def invalid(detail: str) -> AppException:
        return AppException(
            status_code=400,
            error_key=ErrorKey.EVALUATION_BUNDLE_INVALID,
            error_detail=detail,
        )

    if bundle_set.kind != EVALUATION_BUNDLE_SET_KIND:
        if bundle_set.kind == EVALUATION_BUNDLE_KIND:
            raise invalid(
                "The file is a single-evaluation bundle, not a bundle set."
            )
        raise invalid("The file is not an evaluation bundle set.")
    if bundle_set.schema_version > EVALUATION_BUNDLE_SET_SCHEMA_VERSION:
        raise invalid(
            "The bundle set was exported by a newer version of the platform "
            "and cannot be imported here."
        )
    if not bundle_set.evaluations:
        raise invalid("The bundle set contains no evaluations.")
    if len(bundle_set.evaluations) > MAX_SET_EVALUATIONS:
        raise invalid(
            f"This file has {len(bundle_set.evaluations)} evaluations; the "
            f"import limit is {MAX_SET_EVALUATIONS}."
        )
    if len(bundle_set.datasets) > MAX_SET_DATASETS:
        raise invalid(
            f"This file has {len(bundle_set.datasets)} datasets; the import "
            f"limit is {MAX_SET_DATASETS}."
        )

    local_ids = [d.local_id for d in bundle_set.datasets]
    if len(set(local_ids)) != len(local_ids):
        raise invalid("The file's datasets carry duplicate ids.")
    known_ids = set(local_ids)
    used_ids = {item.dataset_local_id for item in bundle_set.evaluations}
    if used_ids - known_ids:
        raise invalid(
            "An evaluation in the file references a dataset that is not "
            "part of the file."
        )
    if known_ids - used_ids:
        # Unused datasets are pure payload: no evaluation would import them,
        # but every one still costs a lookup in the preview.
        raise invalid("The file contains datasets that no evaluation uses.")
    for dataset in bundle_set.datasets:
        if len(dataset.cases) > MAX_BUNDLE_CASES:
            raise invalid(
                f"Dataset '{dataset.name}' has {len(dataset.cases)} test "
                f"cases; the import limit is {MAX_BUNDLE_CASES}."
            )
    total_cases = sum(len(d.cases) for d in bundle_set.datasets)
    if total_cases > MAX_SET_TOTAL_CASES:
        raise invalid(
            f"The file holds {total_cases} test cases in total; the import "
            f"limit is {MAX_SET_TOTAL_CASES}."
        )


def _validate_bundle_header(bundle: EvaluationBundle) -> None:
    if len(bundle.dataset.cases) > MAX_BUNDLE_CASES:
        raise AppException(
            status_code=400,
            error_key=ErrorKey.EVALUATION_BUNDLE_INVALID,
            error_detail=(
                f"This bundle has {len(bundle.dataset.cases)} test cases; "
                f"the import limit is {MAX_BUNDLE_CASES}."
            ),
        )
    if bundle.kind != EVALUATION_BUNDLE_KIND:
        raise AppException(
            status_code=400,
            error_key=ErrorKey.EVALUATION_BUNDLE_INVALID,
            error_detail="The file is not an evaluation bundle.",
        )
    if bundle.schema_version > EVALUATION_BUNDLE_SCHEMA_VERSION:
        raise AppException(
            status_code=400,
            error_key=ErrorKey.EVALUATION_BUNDLE_INVALID,
            error_detail=(
                "The bundle was exported by a newer version of the platform "
                "and cannot be imported here."
            ),
        )
