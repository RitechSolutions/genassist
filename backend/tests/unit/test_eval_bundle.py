"""Unit tests for evaluation export/import bundles: reference collection,
sanitization, resolution against a target workflow and config rewriting."""
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.schemas.eval_bundle import (
    EVALUATION_BUNDLE_KIND,
    EVALUATION_BUNDLE_SCHEMA_VERSION,
    EVALUATION_BUNDLE_SET_KIND,
    EVALUATION_BUNDLE_SET_SCHEMA_VERSION,
    MAX_SET_DATASETS,
    MAX_SET_EVALUATIONS,
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
    BundleNodeRef,
    BundleProviderRef,
    BundleReferences,
    BundleSetDataset,
    BundleSetItem,
    BundleSource,
    EvaluationBundle,
    EvaluationBundleSet,
    EvaluationImportPreviewRequest,
    EvaluationImportRequest,
    EvaluationSetImportPreviewRequest,
    EvaluationSetImportRequest,
)
from app.schemas.test_suite import (
    EvaluationToolCatalog,
    TestCaseInDB,
    TestEvaluation,
    TestSuiteInDB,
)
from app.services import eval_bundle
from app.services.eval_bundle import (
    EvalBundleService,
    UnresolvedRefError,
    build_node_indexes,
    collect_case_ids,
    collect_node_refs,
    collect_provider_ids,
    resolve_node_ref,
    resolve_provider_ref,
    rewrite_case_refs,
    rewrite_node_refs,
    rewrite_provider_refs,
    sanitize_technique_configs,
)


NOW = datetime(2026, 1, 1)


def _catalog(prefix: str) -> dict:
    """A one-agent catalog whose node ids are unique per environment."""
    return {
        "workflow_id": uuid4(),
        "agents": [
            {
                "id": f"{prefix}-agent",
                "label": "HR Agent",
                "type": "reactAgentNode",
                "workflow_path": [],
                "tools": [
                    {
                        "id": f"{prefix}-tool-search",
                        "name": "search_handbook",
                        "label": "Search Handbook",
                        "type": "knowledgeBaseNode",
                    },
                    {
                        "id": f"{prefix}-tool-escalate",
                        "name": "escalate_to_hr",
                        "label": "Escalate To HR",
                        "type": "pythonNode",
                    },
                ],
            }
        ],
        "routers": [
            {
                "id": f"{prefix}-router",
                "label": "Intent Router",
                "workflow_path": [],
                "branches": [],
            }
        ],
        "action_nodes": [
            {
                "id": f"{prefix}-agent",
                "label": "HR Agent",
                "type": "reactAgentNode",
                "workflow_path": [],
            },
            {
                "id": f"{prefix}-escalation",
                "label": "Escalation Message",
                "type": "pythonNode",
                "workflow_path": [],
            },
        ],
    }


def _configs(case_id: str, provider_id: str) -> dict:
    return {
        "tool_used": {
            "rules": [
                {
                    "id": "rule-1",
                    "tool_ids": ["src-tool-search"],
                    "operator": "all",
                    "agent_id": "src-agent",
                    "scope": "specific_turn",
                    "target_case_id": case_id,
                    "per_tool": {"src-tool-search": {"result_not_empty": True}},
                }
            ]
        },
        "route_taken": {"rules": [{"router": "src-router", "expected": "hr"}]},
        "action_taken": {"rules": [{"node": "src-escalation", "should_fire": True}]},
        "llm_judge": {
            "rules": [{"rubric": "Grade politeness", "min_score": 0.7}],
            "llm_provider_id": provider_id,
        },
        "provenance_eval": {
            "min_score": 0.5,
            "embedding_type": "openai",
            "embedding_api_key": "sk-secret",
            "llm_provider_id": provider_id,
        },
    }


class TestSanitization:
    def test_secret_keys_are_stripped_with_notes(self):
        configs, notes = sanitize_technique_configs(_configs("c1", "p1"))

        assert "embedding_api_key" not in configs["provenance_eval"]
        assert any("embedding_api_key" in note for note in notes)

    def test_non_secret_keys_survive(self):
        configs, _ = sanitize_technique_configs(_configs("c1", "p1"))

        assert configs["provenance_eval"]["embedding_type"] == "openai"
        assert configs["llm_judge"]["llm_provider_id"] == "p1"


class TestSecretHeuristic:
    """Credentials must go; ordinary settings that merely contain "token" stay."""

    def test_ordinary_settings_survive(self):
        configs, notes = sanitize_technique_configs(
            {"llm_judge": {"max_tokens": 512, "token_budget": 10, "min_score": 0.5}}
        )

        assert configs["llm_judge"] == {
            "max_tokens": 512,
            "token_budget": 10,
            "min_score": 0.5,
        }
        assert notes == []

    def test_credentials_are_stripped_at_any_depth(self):
        configs, notes = sanitize_technique_configs(
            {
                "tool_used": {
                    "rules": [
                        {"id": "r", "per_tool": {"t": {"expected_args": {"api_key": "sk-x"}}}}
                    ]
                }
            }
        )

        rule = configs["tool_used"]["rules"][0]
        assert rule["per_tool"]["t"]["expected_args"] == {}
        assert len(notes) == 1

    def test_auth_bearing_tokens_are_still_stripped(self):
        configs, _ = sanitize_technique_configs(
            {"provenance_eval": {"auth_token": "x", "access_token": "y", "min_score": 0.5}}
        )

        assert configs["provenance_eval"] == {"min_score": 0.5}

    def test_a_bare_token_key_is_a_credential(self):
        """template_sanitizer strips these from shared artifacts; case inputs
        are merged into the run payload the same way, so they must go too."""
        configs, _ = sanitize_technique_configs(
            {
                "provenance_eval": {
                    "token": "sk-live",
                    "api_token": "x",
                    "refresh_token": "y",
                    "session_token": "z",
                    "id_token": "w",
                    "authorization": "Bearer v",
                    "min_score": 0.5,
                }
            }
        )

        assert configs["provenance_eval"] == {"min_score": 0.5}

    def test_per_tool_keys_are_tool_ids_not_field_names(self):
        """per_tool is keyed by tool id — an MCP tool called get_api_key must
        not have its whole check deleted as if the key were a credential."""
        configs, notes = sanitize_technique_configs(
            {
                "tool_used": {
                    "rules": [
                        {
                            "id": "r",
                            "tool_ids": ["mcp_1:get_api_key", "toolNode_4"],
                            "per_tool": {
                                "mcp_1:get_api_key": {"min_calls": 1},
                                "toolNode_4": {"result_not_empty": True},
                            },
                        }
                    ]
                }
            }
        )

        per_tool = configs["tool_used"]["rules"][0]["per_tool"]
        assert set(per_tool) == {"mcp_1:get_api_key", "toolNode_4"}
        assert notes == []

    def test_notes_do_not_repeat_per_occurrence(self):
        configs, notes = sanitize_technique_configs(
            {
                "tool_used": {
                    "rules": [
                        {"id": "a", "expected_args": {"api_key": "x"}},
                        {"id": "b", "expected_args": {"api_key": "y"}},
                    ]
                }
            }
        )

        assert notes == ["Removed secret field 'api_key' from the tool_used configuration."]
        assert configs["tool_used"]["rules"][0]["expected_args"] == {}


class TestReferenceCollection:
    def test_collects_every_node_ref_kind(self):
        refs = dict(collect_node_refs(_configs("c1", "p1")))

        assert refs["src-tool-search"] == REF_KIND_TOOL
        assert refs["src-agent"] == REF_KIND_AGENT
        assert refs["src-router"] == REF_KIND_ROUTER
        assert refs["src-escalation"] == "action"

    def test_collects_legacy_shapes(self):
        configs = {
            "tool_used": {"tool": "search_handbook", "node": "HR Agent"},
            "route_taken": {"node": "src-router", "expected": "hr"},
        }
        refs = dict(collect_node_refs(configs))

        assert refs["search_handbook"] == REF_KIND_TOOL
        assert refs["HR Agent"] == REF_KIND_AGENT
        assert refs["src-router"] == REF_KIND_ROUTER

    def test_collects_provider_and_case_ids(self):
        configs = _configs("case-9", "provider-7")

        assert collect_provider_ids(configs) == ["provider-7"]
        assert collect_case_ids(configs) == ["case-9"]


class TestNodeResolution:
    def test_same_id_resolves_directly(self):
        indexes = build_node_indexes(_catalog("tgt"))

        result = resolve_node_ref("tgt-tool-search", REF_KIND_TOOL, None, indexes)

        assert result.status == REF_STATUS_RESOLVED
        assert result.resolved_id == "tgt-tool-search"

    def test_label_from_bundle_resolves_new_id(self):
        indexes = build_node_indexes(_catalog("tgt"))

        result = resolve_node_ref(
            "src-tool-search", REF_KIND_TOOL, "Search Handbook", indexes
        )

        assert result.status == REF_STATUS_RESOLVED
        assert result.resolved_id == "tgt-tool-search"

    def test_unknown_ref_is_missing(self):
        indexes = build_node_indexes(_catalog("tgt"))

        result = resolve_node_ref("nope", REF_KIND_ROUTER, "No Router", indexes)

        assert result.status == REF_STATUS_MISSING
        assert result.candidates == []

    def test_duplicate_labels_are_ambiguous(self):
        catalog = _catalog("tgt")
        catalog["routers"].append(
            {"id": "tgt-router-2", "label": "Intent Router", "workflow_path": [], "branches": []}
        )
        indexes = build_node_indexes(catalog)

        result = resolve_node_ref("src-router", REF_KIND_ROUTER, "Intent Router", indexes)

        assert result.status == REF_STATUS_AMBIGUOUS
        assert {c.id for c in result.candidates} == {"tgt-router", "tgt-router-2"}


class TestNodeTypeGuard:
    """A name match must not bind a check to a differently-typed node."""

    def test_same_type_name_match_resolves(self):
        indexes = build_node_indexes(_catalog("tgt"))

        result = resolve_node_ref(
            "src-escalation", REF_KIND_ACTION, "Escalation Message", indexes, "pythonNode"
        )

        assert result.status == REF_STATUS_RESOLVED
        assert result.resolved_id == "tgt-escalation"
        assert result.note is None

    def test_differing_type_needs_confirmation(self):
        indexes = build_node_indexes(_catalog("tgt"))

        result = resolve_node_ref(
            "src-escalation", REF_KIND_ACTION, "Escalation Message", indexes, "routerNode"
        )

        assert result.status == REF_STATUS_AMBIGUOUS
        assert result.resolved_id is None
        assert [c.id for c in result.candidates] == ["tgt-escalation"]
        assert "pythonNode" in result.note and "routerNode" in result.note

    def test_id_match_wins_over_a_differing_type(self):
        """The id proves it is the same node; a type change there is the user's edit."""
        indexes = build_node_indexes(_catalog("tgt"))

        result = resolve_node_ref(
            "tgt-escalation", REF_KIND_ACTION, "Escalation Message", indexes, "routerNode"
        )

        assert result.status == REF_STATUS_RESOLVED
        assert result.resolved_id == "tgt-escalation"
        assert result.note is None

    def test_bundle_without_a_recorded_type_resolves_unchanged(self):
        indexes = build_node_indexes(_catalog("tgt"))

        result = resolve_node_ref(
            "src-escalation", REF_KIND_ACTION, "Escalation Message", indexes, None
        )

        assert result.status == REF_STATUS_RESOLVED
        assert result.resolved_id == "tgt-escalation"

    def test_router_refs_are_unaffected(self):
        """Routers are all routerNode, so no type is indexed and none is compared."""
        indexes = build_node_indexes(_catalog("tgt"))

        result = resolve_node_ref(
            "src-router", REF_KIND_ROUTER, "Intent Router", indexes, "routerNode"
        )

        assert result.status == REF_STATUS_RESOLVED
        assert result.resolved_id == "tgt-router"

    def test_tool_refs_compare_types_too(self):
        indexes = build_node_indexes(_catalog("tgt"))

        result = resolve_node_ref(
            "src-tool-search", REF_KIND_TOOL, "Search Handbook", indexes, "httpNode"
        )

        assert result.status == REF_STATUS_AMBIGUOUS
        assert "knowledgeBaseNode" in result.note


class TestProviderResolution:
    def test_matches_by_model_then_name(self):
        providers = [
            SimpleNamespace(id=uuid4(), name="Azure GPT", llm_model="gpt-4o"),
            SimpleNamespace(id=uuid4(), name="OpenAI GPT", llm_model="gpt-4o"),
        ]
        meta = BundleProviderRef(name="OpenAI GPT", provider="openai", model="gpt-4o")

        result = resolve_provider_ref("old-id", meta, providers)

        assert result.status == REF_STATUS_RESOLVED
        assert result.resolved_id == str(providers[1].id)

    def test_inactive_providers_are_not_matched_by_name(self):
        """The wizard only offers active providers, so a name match must not
        bind the judge to a retired one it cannot later be edited to."""
        retired = SimpleNamespace(
            id=uuid4(), name="Old GPT", llm_model="gpt-4o", is_active=0
        )
        live = SimpleNamespace(
            id=uuid4(), name="New GPT", llm_model="gpt-4o", is_active=1
        )
        meta = BundleProviderRef(name="Old GPT", provider="openai", model="gpt-4o")

        result = resolve_provider_ref("old-id", meta, [retired, live])

        assert result.resolved_id == str(live.id)

    def test_an_exact_provider_id_is_honoured_even_when_inactive(self):
        retired = SimpleNamespace(
            id=uuid4(), name="Old GPT", llm_model="gpt-4o", is_active=0
        )

        result = resolve_provider_ref(str(retired.id), None, [retired])

        assert result.status == REF_STATUS_RESOLVED
        assert result.resolved_id == str(retired.id)

    def test_unmatched_provider_is_missing(self):
        providers = [SimpleNamespace(id=uuid4(), name="Claude", llm_model="claude-sonnet-5")]
        meta = BundleProviderRef(name="Mistral", provider=None, model="mistral-large")

        result = resolve_provider_ref("old-id", meta, providers)

        assert result.status == REF_STATUS_MISSING


class TestRewriting:
    def test_rewrites_every_node_ref(self):
        node_map = {
            "src-tool-search": "tgt-tool-search",
            "src-agent": "tgt-agent",
            "src-router": "tgt-router",
            "src-escalation": "tgt-escalation",
        }
        configs, dropped = rewrite_node_refs(
            _configs("c1", "p1"), lambda ref, kind: node_map[ref]
        )

        rule = configs["tool_used"]["rules"][0]
        assert rule["tool_ids"] == ["tgt-tool-search"]
        assert rule["agent_id"] == "tgt-agent"
        assert list(rule["per_tool"]) == ["tgt-tool-search"]
        assert configs["route_taken"]["rules"][0]["router"] == "tgt-router"
        assert configs["action_taken"]["rules"][0]["node"] == "tgt-escalation"
        assert dropped == []

    def test_unresolved_ref_raises_without_drop_log(self):
        def resolve(ref, kind):
            raise UnresolvedRefError(ref, kind)

        with pytest.raises(UnresolvedRefError):
            rewrite_node_refs({"route_taken": {"rules": [{"router": "x", "expected": "a"}]}}, resolve)

    def test_drop_mode_drops_rule_and_technique(self):
        def resolve(ref, kind):
            raise UnresolvedRefError(ref, kind)

        drop_log = []
        configs, dropped = rewrite_node_refs(
            {"route_taken": {"rules": [{"router": "x", "expected": "a"}]}},
            resolve,
            drop_log,
        )

        assert dropped == ["route_taken"]
        assert "route_taken" not in configs
        assert len(drop_log) == 1

    def test_provider_fallback_removes_field_with_warning(self):
        configs = {"llm_judge": {"rules": [], "llm_provider_id": "old"}}

        rewritten, warnings = rewrite_provider_refs(configs, {"old": None})

        assert "llm_provider_id" not in rewritten["llm_judge"]
        assert len(warnings) == 1

    def test_case_refs_remap_or_fall_back_to_conversation_target(self):
        conversation_id = str(uuid4())
        configs = {
            "tool_used": {
                "rules": [
                    {"id": "r1", "target_case_id": "old-1"},
                    {
                        "id": "r2",
                        "target_case_id": "old-2",
                        "target_source_conversation_id": conversation_id,
                        "target_turn_index": 1,
                    },
                    {"id": "r3", "target_case_id": "old-3"},
                ]
            }
        }

        rewritten, warnings = rewrite_case_refs(configs, {"old-1": "new-1"})

        rules = rewritten["tool_used"]["rules"]
        assert rules[0]["target_case_id"] == "new-1"
        assert "target_case_id" not in rules[1]
        assert rules[2]["target_case_id"] == "old-3"
        assert len(warnings) == 1


def _service(**overrides) -> EvalBundleService:
    service = EvalBundleService(
        suite_service=AsyncMock(),
        workflow_service=AsyncMock(),
        llm_provider_service=AsyncMock(),
        case_repo=AsyncMock(),
    )
    for name, value in overrides.items():
        setattr(service, name, value)
    return service


def _provider(provider_id):
    return SimpleNamespace(
        id=provider_id, name="OpenAI GPT", llm_model_provider="openai", llm_model="gpt-4o"
    )


def _export_fixture():
    suite_id, workflow_id, case_id, provider_id = uuid4(), uuid4(), uuid4(), uuid4()
    evaluation = TestEvaluation(
        id=uuid4(),
        name="HR checks",
        description="desc",
        suite_id=suite_id,
        workflow_id=workflow_id,
        techniques=["tool_used", "route_taken", "llm_judge"],
        technique_configs=_configs(str(case_id), str(provider_id)),
        input_metadata={"channel": "web", "api_key": "leak-me"},
        run_ids=["11111111-1111-1111-1111-111111111111"],
        created_at=NOW,
        updated_at=NOW,
    )
    suite = TestSuiteInDB(
        id=suite_id,
        name="HR dataset",
        description=None,
        workflow_id=workflow_id,
        default_input_metadata=None,
        created_at=NOW,
        updated_at=NOW,
    )
    case = TestCaseInDB(
        id=case_id,
        suite_id=suite_id,
        input_data={"message": "hi"},
        expected_output={"value": "hello"},
        created_at=NOW,
        updated_at=NOW,
    )
    service = _service()
    service.suites.get_evaluation.return_value = evaluation
    service.suites.get_suite.return_value = suite
    service.suites.list_cases_for_suite.return_value = [case]
    service.suites.get_evaluation_tool_catalog.return_value = EvaluationToolCatalog(
        **_catalog("src")
    )
    service.workflows.get_by_id.return_value = SimpleNamespace(
        id=workflow_id, name="HR Assistant", version="1.0"
    )
    service.providers.get_all_minimal.return_value = [_provider(provider_id)]
    return service, evaluation, case_id, provider_id


class TestExport:
    @pytest.mark.asyncio
    async def test_bundle_records_labels_providers_and_case_refs(self):
        service, _, case_id, provider_id = _export_fixture()

        bundle = await service.export_evaluation(uuid4())

        assert bundle.source.workflow_name == "HR Assistant"
        assert bundle.references.nodes["src-tool-search"].label == "Search Handbook"
        assert bundle.references.nodes["src-router"].kind == REF_KIND_ROUTER
        # Types travel so import can refuse a name match onto a different type.
        assert bundle.references.nodes["src-tool-search"].node_type == "knowledgeBaseNode"
        assert bundle.references.nodes["src-agent"].node_type == "reactAgentNode"
        assert bundle.references.nodes["src-escalation"].node_type == "pythonNode"
        assert bundle.references.llm_providers[str(provider_id)].model == "gpt-4o"
        assert bundle.references.cases[str(case_id)] == 1
        assert bundle.dataset.cases[0].local_id == 1

    @pytest.mark.asyncio
    async def test_bundle_never_contains_secrets_or_run_history(self):
        service, _, _, _ = _export_fixture()

        bundle = await service.export_evaluation(uuid4())

        assert "embedding_api_key" not in bundle.evaluation.technique_configs["provenance_eval"]
        assert "api_key" not in bundle.evaluation.input_metadata
        assert "run_ids" not in bundle.evaluation.model_dump()
        assert any("api_key" in note for note in bundle.notes)


def _bundle(case_id: str, provider_id: str) -> EvaluationBundle:
    configs, _ = sanitize_technique_configs(_configs(case_id, provider_id))
    return EvaluationBundle(
        source=BundleSource(workflow_name="HR Assistant", workflow_version="1.0"),
        evaluation=BundleEvaluation(
            name="HR checks",
            techniques=["tool_used", "route_taken", "action_taken", "llm_judge"],
            technique_configs=configs,
        ),
        dataset=BundleDataset(
            name="HR dataset",
            cases=[
                BundleCase(local_id=1, input_data={"message": "hi"}),
                BundleCase(local_id=2, input_data={"message": "bye"}),
            ],
        ),
        references=BundleReferences(
            nodes={
                "src-tool-search": BundleNodeRef(label="Search Handbook", kind=REF_KIND_TOOL),
                "src-agent": BundleNodeRef(label="HR Agent", kind=REF_KIND_AGENT),
                "src-router": BundleNodeRef(label="Intent Router", kind=REF_KIND_ROUTER),
                "src-escalation": BundleNodeRef(label="Escalation Message", kind="action"),
            },
            llm_providers={
                provider_id: BundleProviderRef(name="OpenAI GPT", provider="openai", model="gpt-4o")
            },
            cases={case_id: 1},
        ),
    )


def _import_service(target_provider_id):
    service = _service()
    service.suites.get_evaluation_tool_catalog.return_value = EvaluationToolCatalog(
        **_catalog("tgt")
    )
    service.workflows.get_by_id.return_value = SimpleNamespace(
        id=uuid4(), name="HR Assistant", version="2.0"
    )
    service.providers.get_all_minimal.return_value = [_provider(target_provider_id)]
    service.suites.list_suites.return_value = []
    service.workflows.get_all_minimal.return_value = []
    new_suite_id = uuid4()
    service.suites.create_suite.return_value = SimpleNamespace(id=new_suite_id)
    service.suites.create_evaluation.return_value = SimpleNamespace(id=uuid4())

    def assign_ids(models):
        for model in models:
            model.id = uuid4()
        return models

    service.case_repo.create_many.side_effect = assign_ids
    return service


class TestPreview:
    @pytest.mark.asyncio
    async def test_labels_resolve_against_target_catalog(self):
        provider_id = str(uuid4())
        service = _import_service(uuid4())

        preview = await service.preview_import(
            EvaluationImportPreviewRequest(
                bundle=_bundle(str(uuid4()), provider_id),
                target_workflow_id=uuid4(),
            )
        )

        assert preview.can_import is True
        assert preview.workflow_name_matches is True
        by_ref = {r.ref: r for r in preview.node_refs}
        assert by_ref["src-tool-search"].resolved_id == "tgt-tool-search"
        assert by_ref["src-router"].resolved_id == "tgt-router"

    @pytest.mark.asyncio
    async def test_missing_node_blocks_import(self):
        provider_id = str(uuid4())
        service = _import_service(uuid4())
        bundle = _bundle(str(uuid4()), provider_id)
        bundle.references.nodes["src-router"].label = "Renamed Router"
        bundle.evaluation.technique_configs["route_taken"]["rules"][0]["router"] = "unknown"

        preview = await service.preview_import(
            EvaluationImportPreviewRequest(bundle=bundle, target_workflow_id=uuid4())
        )

        assert preview.can_import is False

    @pytest.mark.asyncio
    async def test_newer_schema_version_is_rejected(self):
        service = _import_service(uuid4())
        bundle = _bundle(str(uuid4()), str(uuid4()))
        bundle.schema_version = EVALUATION_BUNDLE_SCHEMA_VERSION + 1

        with pytest.raises(AppException) as excinfo:
            await service.preview_import(
                EvaluationImportPreviewRequest(bundle=bundle, target_workflow_id=uuid4())
            )
        assert excinfo.value.status_code == 400


class TestImport:
    @pytest.mark.asyncio
    async def test_import_rewrites_configs_to_target_ids(self):
        old_case_id = str(uuid4())
        target_provider_id = uuid4()
        service = _import_service(target_provider_id)

        result = await service.import_bundle(
            EvaluationImportRequest(
                bundle=_bundle(old_case_id, str(uuid4())),
                target_workflow_id=uuid4(),
            )
        )

        created = service.suites.create_evaluation.await_args.args[0]
        configs = created.technique_configs
        rule = configs["tool_used"]["rules"][0]
        assert rule["tool_ids"] == ["tgt-tool-search"]
        assert rule["agent_id"] == "tgt-agent"
        assert configs["route_taken"]["rules"][0]["router"] == "tgt-router"
        assert configs["action_taken"]["rules"][0]["node"] == "tgt-escalation"
        assert rule["target_case_id"] not in (old_case_id, None)
        assert result.case_count == 2

    @pytest.mark.asyncio
    async def test_judge_provider_is_matched_by_model(self):
        target_provider_id = uuid4()
        service = _import_service(target_provider_id)

        await service.import_bundle(
            EvaluationImportRequest(
                bundle=_bundle(str(uuid4()), str(uuid4())),
                target_workflow_id=uuid4(),
            )
        )

        created = service.suites.create_evaluation.await_args.args[0]
        assert created.technique_configs["llm_judge"]["llm_provider_id"] == str(
            target_provider_id
        )

    @pytest.mark.asyncio
    async def test_unresolved_ref_fails_before_creating_anything(self):
        service = _import_service(uuid4())
        bundle = _bundle(str(uuid4()), str(uuid4()))
        bundle.references.nodes["src-router"].label = "Renamed Router"
        bundle.evaluation.technique_configs["route_taken"]["rules"][0]["router"] = "unknown"

        with pytest.raises(AppException) as excinfo:
            await service.import_bundle(
                EvaluationImportRequest(bundle=bundle, target_workflow_id=uuid4())
            )

        assert excinfo.value.status_code == 400
        service.suites.create_suite.assert_not_awaited()
        service.suites.create_evaluation.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_import_is_refused_when_every_check_would_be_dropped(self):
        """An empty technique list makes the run fall back to platform defaults,
        so it would grade with checks nobody chose rather than grade nothing."""
        service = _import_service(uuid4())
        bundle = _bundle(str(uuid4()), str(uuid4()))
        bundle.evaluation.techniques = ["route_taken"]
        bundle.evaluation.technique_configs = {
            "route_taken": {"rules": [{"router": "unknown", "expected": "a"}]}
        }
        bundle.references.nodes = {}

        with pytest.raises(AppException) as excinfo:
            await service.import_bundle(
                EvaluationImportRequest(
                    bundle=bundle,
                    target_workflow_id=uuid4(),
                    drop_unresolved_rules=True,
                )
            )

        assert excinfo.value.status_code == 400
        service.suites.create_suite.assert_not_awaited()
        service.suites.create_evaluation.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_preview_flags_when_dropping_would_leave_no_checks(self):
        """Import refuses that outcome, so the dialog must not offer dropping."""
        service = _import_service(uuid4())
        bundle = _bundle(str(uuid4()), str(uuid4()))
        bundle.evaluation.techniques = ["route_taken"]
        bundle.evaluation.technique_configs = {
            "route_taken": {"rules": [{"router": "unknown", "expected": "a"}]}
        }
        bundle.references.nodes = {}

        preview = await service.preview_import(
            EvaluationImportPreviewRequest(bundle=bundle, target_workflow_id=uuid4())
        )

        assert preview.dropping_all_would_empty is True

    @pytest.mark.asyncio
    async def test_preview_allows_dropping_when_other_checks_survive(self):
        service = _import_service(uuid4())
        bundle = _bundle(str(uuid4()), str(uuid4()))

        preview = await service.preview_import(
            EvaluationImportPreviewRequest(bundle=bundle, target_workflow_id=uuid4())
        )

        assert preview.dropping_all_would_empty is False

    @pytest.mark.asyncio
    async def test_an_oversized_bundle_is_refused_on_import(self):
        from app.schemas.eval_bundle import MAX_BUNDLE_CASES

        service = _import_service(uuid4())
        bundle = _bundle(str(uuid4()), str(uuid4()))
        bundle.dataset.cases = [
            BundleCase(local_id=i, input_data={"message": "x"})
            for i in range(MAX_BUNDLE_CASES + 1)
        ]

        with pytest.raises(AppException) as excinfo:
            await service.import_bundle(
                EvaluationImportRequest(bundle=bundle, target_workflow_id=uuid4())
            )
        assert excinfo.value.status_code == 400

    @pytest.mark.asyncio
    async def test_export_is_not_capped_by_the_import_limit(self):
        """The cap guards inbound payloads; a big dataset must still export."""
        from app.schemas.eval_bundle import MAX_BUNDLE_CASES

        service, _, _, _ = _export_fixture()
        suite_id = service.suites.get_suite.return_value.id
        service.suites.list_cases_for_suite.return_value = [
            TestCaseInDB(
                id=uuid4(),
                suite_id=suite_id,
                input_data={"message": str(i)},
                created_at=NOW,
                updated_at=NOW,
            )
            for i in range(MAX_BUNDLE_CASES + 10)
        ]

        bundle = await service.export_evaluation(uuid4())

        assert len(bundle.dataset.cases) == MAX_BUNDLE_CASES + 10

    @pytest.mark.asyncio
    async def test_drop_unresolved_rules_drops_and_reports(self):
        service = _import_service(uuid4())
        bundle = _bundle(str(uuid4()), str(uuid4()))
        bundle.references.nodes["src-router"].label = "Renamed Router"
        bundle.evaluation.technique_configs["route_taken"]["rules"][0]["router"] = "unknown"

        result = await service.import_bundle(
            EvaluationImportRequest(
                bundle=bundle,
                target_workflow_id=uuid4(),
                drop_unresolved_rules=True,
            )
        )

        assert len(result.dropped_rules) == 1
        created = service.suites.create_evaluation.await_args.args[0]
        assert "route_taken" not in created.techniques
        assert "route_taken" not in created.technique_configs

    @pytest.mark.asyncio
    async def test_manual_resolution_overrides_missing_ref(self):
        service = _import_service(uuid4())
        bundle = _bundle(str(uuid4()), str(uuid4()))
        bundle.references.nodes["src-router"].label = "Renamed Router"
        bundle.evaluation.technique_configs["route_taken"]["rules"][0]["router"] = "src-router"

        await service.import_bundle(
            EvaluationImportRequest(
                bundle=bundle,
                target_workflow_id=uuid4(),
                resolutions={"router:src-router": "tgt-router"},
            )
        )

        created = service.suites.create_evaluation.await_args.args[0]
        assert created.technique_configs["route_taken"]["rules"][0]["router"] == "tgt-router"

    @pytest.mark.asyncio
    async def test_manual_resolution_to_unknown_node_is_rejected(self):
        service = _import_service(uuid4())
        bundle = _bundle(str(uuid4()), str(uuid4()))

        with pytest.raises(AppException) as excinfo:
            await service.import_bundle(
                EvaluationImportRequest(
                    bundle=bundle,
                    target_workflow_id=uuid4(),
                    resolutions={"router:src-router": "not-a-node"},
                )
            )
        assert excinfo.value.status_code == 400

    @pytest.mark.asyncio
    async def test_wrong_kind_is_rejected(self):
        service = _import_service(uuid4())
        bundle = _bundle(str(uuid4()), str(uuid4())).model_dump()
        bundle["kind"] = "genassist.evaluation-bundle"
        request = EvaluationImportRequest(
            bundle=bundle, target_workflow_id=uuid4()
        )
        request.bundle.kind = "something-else"

        with pytest.raises(AppException):
            await service.import_bundle(request)


class TestEnvironmentWarnings:
    def test_nli_model_choice_is_never_flagged(self):
        """Both curated models resolve everywhere, so neither is a portability risk."""
        from app.constants.nli_models import NLI_MODELS
        from app.services.eval_bundle import environment_warnings

        for model in NLI_MODELS:
            warnings = environment_warnings(
                {"nli_eval": {"nli_model_name": model["value"], "min_entail_score": 0.6}}
            )
            assert warnings == []

    def test_hosted_embeddings_are_flagged(self):
        """Unlike NLI, these reach an external service with per-environment credentials."""
        from app.services.eval_bundle import environment_warnings

        for embedding_type in ("openai", "bedrock"):
            warnings = environment_warnings(
                {"provenance_eval": {"embedding_type": embedding_type}}
            )
            assert len(warnings) == 1

    def test_local_embeddings_are_not_flagged(self):
        from app.services.eval_bundle import environment_warnings

        warnings = environment_warnings(
            {"provenance_eval": {"embedding_type": "huggingface"}}
        )

        assert warnings == []


class TestReviewRegressions:
    def test_service_resolves_through_the_injector(self):
        from injector import Injector

        from app.repositories.test_suite import TestCaseRepository
        from app.services.llm_providers import LlmProviderService
        from app.services.test_suite import TestSuiteService
        from app.services.workflow import WorkflowService

        container = Injector()
        container.binder.bind(TestSuiteService, to=AsyncMock())
        container.binder.bind(WorkflowService, to=AsyncMock())
        container.binder.bind(LlmProviderService, to=AsyncMock())
        container.binder.bind(TestCaseRepository, to=AsyncMock())

        assert isinstance(container.get(EvalBundleService), EvalBundleService)

    @pytest.mark.asyncio
    async def test_same_ref_under_two_kinds_resolves_independently(self):
        service = _import_service(uuid4())
        catalog = _catalog("tgt")
        catalog["action_nodes"].append(
            {"id": "tgt-agent-2", "label": "HR Agent", "type": "pythonNode", "workflow_path": []}
        )
        service.suites.get_evaluation_tool_catalog.return_value = EvaluationToolCatalog(
            **catalog
        )
        bundle = _bundle(str(uuid4()), str(uuid4()))
        bundle.evaluation.technique_configs["action_taken"]["rules"][0]["node"] = "src-agent"

        result = await service.import_bundle(
            EvaluationImportRequest(
                bundle=bundle,
                target_workflow_id=uuid4(),
                resolutions={"action:src-agent": "tgt-agent-2"},
            )
        )

        created = service.suites.create_evaluation.await_args.args[0]
        tool_rule = created.technique_configs["tool_used"]["rules"][0]
        action_rule = created.technique_configs["action_taken"]["rules"][0]
        assert tool_rule["agent_id"] == "tgt-agent"
        assert action_rule["node"] == "tgt-agent-2"
        assert result.dropped_rules == []

    @pytest.mark.asyncio
    async def test_ambiguity_in_one_kind_is_not_bypassed_by_the_other(self):
        service = _import_service(uuid4())
        catalog = _catalog("tgt")
        catalog["action_nodes"].append(
            {"id": "tgt-agent-2", "label": "HR Agent", "type": "pythonNode", "workflow_path": []}
        )
        service.suites.get_evaluation_tool_catalog.return_value = EvaluationToolCatalog(
            **catalog
        )
        bundle = _bundle(str(uuid4()), str(uuid4()))
        bundle.evaluation.technique_configs["action_taken"]["rules"][0]["node"] = "src-agent"

        with pytest.raises(AppException) as excinfo:
            await service.import_bundle(
                EvaluationImportRequest(bundle=bundle, target_workflow_id=uuid4())
            )
        assert excinfo.value.status_code == 400

    @pytest.mark.asyncio
    async def test_export_strips_secret_keys_from_case_inputs(self):
        service, _, _, _ = _export_fixture()
        case = service.suites.list_cases_for_suite.return_value[0]
        case.input_data = {"message": "hi", "auth_token": "leak-me"}

        bundle = await service.export_evaluation(uuid4())

        assert "auth_token" not in bundle.dataset.cases[0].input_data
        assert bundle.dataset.cases[0].input_data["message"] == "hi"
        assert any("auth_token" in note for note in bundle.notes)

    @pytest.mark.asyncio
    async def test_per_tool_checks_collapsing_onto_one_tool_are_refused(self):
        service = _import_service(uuid4())
        bundle = _bundle(str(uuid4()), str(uuid4()))
        rule = bundle.evaluation.technique_configs["tool_used"]["rules"][0]
        rule["per_tool"] = {
            "src-tool-search": {"result_not_empty": True},
            "Search Handbook": {"result_contains": "policy"},
        }

        with pytest.raises(AppException) as excinfo:
            await service.import_bundle(
                EvaluationImportRequest(bundle=bundle, target_workflow_id=uuid4())
            )
        assert excinfo.value.status_code == 400

    @pytest.mark.asyncio
    async def test_failed_evaluation_create_cleans_up_the_new_suite(self):
        service = _import_service(uuid4())
        service.suites.create_evaluation.side_effect = RuntimeError("db down")

        with pytest.raises(RuntimeError):
            await service.import_bundle(
                EvaluationImportRequest(
                    bundle=_bundle(str(uuid4()), str(uuid4())),
                    target_workflow_id=uuid4(),
                )
            )

        created_suite = service.suites.create_suite.return_value
        service.suites.delete_suite.assert_awaited_once_with(created_suite.id)


class TestDatasetReuse:
    def _existing_case(self, suite_id, conversation_id, turn_index):
        return TestCaseInDB(
            id=uuid4(),
            suite_id=suite_id,
            input_data={"message": f"turn {turn_index}"},
            source_conversation_id=conversation_id,
            turn_index=turn_index,
            created_at=NOW,
            updated_at=NOW,
        )

    @pytest.mark.asyncio
    async def test_preview_reports_an_existing_dataset_by_name(self):
        service = _import_service(uuid4())
        suite_id, target = uuid4(), uuid4()
        service.suites.list_suites.return_value = [
            SimpleNamespace(id=uuid4(), name="Unrelated", workflow_id=target),
            # Same name but another workflow's — must not be offered.
            SimpleNamespace(id=uuid4(), name="hr dataset", workflow_id=uuid4()),
            SimpleNamespace(id=suite_id, name="hr dataset", workflow_id=target),
        ]
        service.suites.list_cases_for_suite.return_value = [
            self._existing_case(suite_id, uuid4(), 0)
        ]

        preview = await service.preview_import(
            EvaluationImportPreviewRequest(
                bundle=_bundle(str(uuid4()), str(uuid4())),
                target_workflow_id=target,
            )
        )

        assert preview.existing_dataset is not None
        assert preview.existing_dataset.id == suite_id
        assert preview.existing_dataset.case_count == 1

    @pytest.mark.asyncio
    async def test_reuse_attaches_without_creating_a_dataset_or_cases(self):
        service = _import_service(uuid4())
        suite_id, target = uuid4(), uuid4()
        service.suites.get_suite.return_value = SimpleNamespace(
            id=suite_id, name="HR dataset", workflow_id=target
        )
        service.suites.list_cases_for_suite.return_value = [
            self._existing_case(suite_id, uuid4(), 0),
            self._existing_case(suite_id, uuid4(), 1),
        ]

        result = await service.import_bundle(
            EvaluationImportRequest(
                bundle=_bundle(str(uuid4()), str(uuid4())),
                target_workflow_id=target,
                existing_suite_id=suite_id,
            )
        )

        assert result.reused_dataset is True
        assert result.suite_id == suite_id
        service.suites.create_suite.assert_not_awaited()
        service.case_repo.create_many.assert_not_awaited()
        created = service.suites.create_evaluation.await_args.args[0]
        assert created.suite_id == suite_id

    @pytest.mark.asyncio
    async def test_reuse_repoints_turn_targets_at_the_existing_cases(self):
        service = _import_service(uuid4())
        suite_id, conversation_id, old_case_id = uuid4(), uuid4(), str(uuid4())
        target = uuid4()
        existing = self._existing_case(suite_id, conversation_id, 0)
        service.suites.get_suite.return_value = SimpleNamespace(
            id=suite_id, name="HR dataset", workflow_id=target
        )
        service.suites.list_cases_for_suite.return_value = [existing]

        bundle = _bundle(old_case_id, str(uuid4()))
        bundle.dataset.cases = [
            BundleCase(
                local_id=1,
                input_data={"message": "hi"},
                source_conversation_id=conversation_id,
                turn_index=0,
            )
        ]

        await service.import_bundle(
            EvaluationImportRequest(
                bundle=bundle,
                target_workflow_id=target,
                existing_suite_id=suite_id,
            )
        )

        created = service.suites.create_evaluation.await_args.args[0]
        rule = created.technique_configs["tool_used"]["rules"][0]
        assert rule["target_case_id"] == str(existing.id)

    @pytest.mark.asyncio
    async def test_reuse_warns_when_case_counts_differ(self):
        service = _import_service(uuid4())
        suite_id, target = uuid4(), uuid4()
        service.suites.get_suite.return_value = SimpleNamespace(
            id=suite_id, name="HR dataset", workflow_id=target
        )
        service.suites.list_cases_for_suite.return_value = [
            self._existing_case(suite_id, uuid4(), 0)
        ]

        result = await service.import_bundle(
            EvaluationImportRequest(
                bundle=_bundle(str(uuid4()), str(uuid4())),
                target_workflow_id=target,
                existing_suite_id=suite_id,
            )
        )

        assert any("1 case(s)" in w and "bundle has 2" in w for w in result.warnings)

    @pytest.mark.asyncio
    async def test_reuse_of_a_deleted_dataset_is_rejected(self):
        service = _import_service(uuid4())
        service.suites.get_suite.side_effect = AppException(
            status_code=404, error_key=ErrorKey.NOT_FOUND
        )

        with pytest.raises(AppException) as excinfo:
            await service.import_bundle(
                EvaluationImportRequest(
                    bundle=_bundle(str(uuid4()), str(uuid4())),
                    target_workflow_id=uuid4(),
                    existing_suite_id=uuid4(),
                )
            )
        assert excinfo.value.status_code == 400

    @pytest.mark.asyncio
    async def test_a_reused_dataset_is_never_cleaned_up_on_failure(self):
        service = _import_service(uuid4())
        suite_id, target = uuid4(), uuid4()
        service.suites.get_suite.return_value = SimpleNamespace(
            id=suite_id, name="HR dataset", workflow_id=target
        )
        service.suites.list_cases_for_suite.return_value = []
        service.suites.create_evaluation.side_effect = RuntimeError("db down")

        with pytest.raises(RuntimeError):
            await service.import_bundle(
                EvaluationImportRequest(
                    bundle=_bundle(str(uuid4()), str(uuid4())),
                    target_workflow_id=target,
                    existing_suite_id=suite_id,
                )
            )

        service.suites.delete_suite.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_a_dataset_on_another_version_of_the_same_workflow_is_offered(self):
        """Datasets stay attached to the version current when they were made, so
        scoping to one version would keep creating the duplicates we removed."""
        service = _import_service(uuid4())
        agent_id, suite_id = uuid4(), uuid4()
        v1, v2 = uuid4(), uuid4()
        service.workflows.get_all_minimal.return_value = [
            SimpleNamespace(id=v1, agent_id=agent_id),
            SimpleNamespace(id=v2, agent_id=agent_id),
        ]
        service.suites.list_suites.return_value = [
            SimpleNamespace(id=suite_id, name="hr dataset", workflow_id=v1)
        ]
        service.suites.list_cases_for_suite.return_value = [
            self._existing_case(suite_id, uuid4(), 0)
        ]

        preview = await service.preview_import(
            EvaluationImportPreviewRequest(
                bundle=_bundle(str(uuid4()), str(uuid4())),
                target_workflow_id=v2,
            )
        )

        assert preview.existing_dataset is not None
        assert preview.existing_dataset.id == suite_id

    @pytest.mark.asyncio
    async def test_reusing_another_workflows_dataset_is_rejected(self):
        service = _import_service(uuid4())
        suite_id = uuid4()
        service.suites.get_suite.return_value = SimpleNamespace(
            id=suite_id, name="HR dataset", workflow_id=uuid4()
        )

        with pytest.raises(AppException) as excinfo:
            await service.import_bundle(
                EvaluationImportRequest(
                    bundle=_bundle(str(uuid4()), str(uuid4())),
                    target_workflow_id=uuid4(),
                    existing_suite_id=suite_id,
                )
            )
        assert excinfo.value.status_code == 400
        service.suites.create_evaluation.assert_not_awaited()


class TestRoundTrip:
    @pytest.mark.asyncio
    async def test_exported_bundle_imports_with_target_ids(self):
        export_service, _, _, _ = _export_fixture()
        bundle = await export_service.export_evaluation(uuid4())

        import_service = _import_service(uuid4())
        result = await import_service.import_bundle(
            EvaluationImportRequest(bundle=bundle, target_workflow_id=uuid4())
        )

        created = import_service.suites.create_evaluation.await_args.args[0]
        rule = created.technique_configs["tool_used"]["rules"][0]
        assert rule["tool_ids"] == ["tgt-tool-search"]
        assert created.technique_configs["route_taken"]["rules"][0]["router"] == "tgt-router"
        assert result.case_count == 1


def _route_only_evaluation(name: str) -> BundleEvaluation:
    return BundleEvaluation(
        name=name,
        techniques=["route_taken"],
        technique_configs={
            "route_taken": {"rules": [{"router": "src-router", "expected": "hr"}]}
        },
    )


def _bundle_set(case_id: str, provider_id: str) -> EvaluationBundleSet:
    """Two evaluations sharing one dataset: the full single-bundle evaluation
    plus a route-only one."""
    single = _bundle(case_id, provider_id)
    return EvaluationBundleSet(
        source=single.source,
        datasets=[BundleSetDataset(local_id=1, **single.dataset.model_dump())],
        evaluations=[
            BundleSetItem(
                evaluation=single.evaluation,
                dataset_local_id=1,
                references=single.references,
            ),
            BundleSetItem(
                evaluation=_route_only_evaluation("Routing only"),
                dataset_local_id=1,
                references=single.references,
            ),
        ],
    )


def _set_import_service(target_provider_id):
    service = _import_service(target_provider_id)
    service.suites.list_evaluations.return_value = []
    return service


def _wire_batch_dataset_reuse(service, target_workflow_id):
    """Make suites real enough that reusing the WRONG id fails.

    Each create_suite call mints its own id; get_suite only knows ids this batch
    created, so forwarding an evaluation id (or a stale one) raises instead of
    quietly resolving to the single canned suite.
    """
    created = {}

    async def create_suite(data):
        suite = SimpleNamespace(
            id=uuid4(), name=data.name, workflow_id=target_workflow_id
        )
        created[str(suite.id)] = suite
        return suite

    async def get_suite(suite_id):
        suite = created.get(str(suite_id))
        if not suite:
            raise AppException(status_code=404, error_key=ErrorKey.NOT_FOUND)
        return suite

    async def list_cases_for_suite(suite_id):
        assert str(suite_id) in created, f"unknown suite {suite_id}"
        return [
            TestCaseInDB(
                id=uuid4(), suite_id=suite_id, input_data={"message": "hi"},
                created_at=NOW, updated_at=NOW,
            ),
            TestCaseInDB(
                id=uuid4(), suite_id=suite_id, input_data={"message": "bye"},
                created_at=NOW, updated_at=NOW,
            ),
        ]

    async def list_suites():
        # A suite created earlier in the batch is visible to later lookups, as
        # it would be in the database — without this, a name-collision test
        # passes for the wrong reason.
        return list(created.values())

    service.suites.create_suite.side_effect = create_suite
    service.suites.get_suite.side_effect = get_suite
    service.suites.list_cases_for_suite.side_effect = list_cases_for_suite
    service.suites.list_suites.side_effect = list_suites
    return created


def _stored_evaluation(name: str, suite_id, workflow_id) -> TestEvaluation:
    return TestEvaluation(
        id=uuid4(),
        name=name,
        description=None,
        suite_id=suite_id,
        workflow_id=workflow_id,
        techniques=["route_taken"],
        technique_configs={
            "route_taken": {"rules": [{"router": "src-router", "expected": "hr"}]}
        },
        created_at=NOW,
        updated_at=NOW,
    )


class TestBundleSetExport:
    @pytest.mark.asyncio
    async def test_export_set_dedupes_shared_datasets_and_sorts_by_name(self):
        workflow_id, suite_a, suite_b = uuid4(), uuid4(), uuid4()
        evaluations = [
            _stored_evaluation("B checks", suite_a, workflow_id),
            _stored_evaluation("A checks", suite_a, workflow_id),
            _stored_evaluation("C checks", suite_b, workflow_id),
        ]
        suites = {
            suite_a: TestSuiteInDB(
                id=suite_a, name="Shared dataset", workflow_id=workflow_id,
                created_at=NOW, updated_at=NOW,
            ),
            suite_b: TestSuiteInDB(
                id=suite_b, name="Other dataset", workflow_id=workflow_id,
                created_at=NOW, updated_at=NOW,
            ),
        }
        service = _service()
        service.suites.list_evaluations.return_value = evaluations
        service.suites.get_evaluation.side_effect = lambda eid: next(
            e for e in evaluations if e.id == eid
        )
        service.suites.get_suite.side_effect = lambda sid: suites[sid]
        service.suites.list_cases_for_suite.return_value = [
            TestCaseInDB(
                id=uuid4(), suite_id=suite_a, input_data={"message": "hi"},
                created_at=NOW, updated_at=NOW,
            )
        ]
        service.suites.get_evaluation_tool_catalog.return_value = (
            EvaluationToolCatalog(**_catalog("src"))
        )
        service.workflows.get_by_id.return_value = SimpleNamespace(
            id=workflow_id, name="HR Assistant", version="1.0"
        )
        service.workflows.get_all_minimal.return_value = []
        service.providers.get_all_minimal.return_value = []

        bundle_set = await service.export_workflow_evaluations(workflow_id)

        assert bundle_set.kind == EVALUATION_BUNDLE_SET_KIND
        assert [i.evaluation.name for i in bundle_set.evaluations] == [
            "A checks", "B checks", "C checks",
        ]
        assert len(bundle_set.datasets) == 2
        shared, other = bundle_set.evaluations[0], bundle_set.evaluations[1]
        assert shared.dataset_local_id == other.dataset_local_id
        assert bundle_set.evaluations[2].dataset_local_id != shared.dataset_local_id

    @pytest.mark.asyncio
    async def test_export_set_with_no_evaluations_404s(self):
        service = _service()
        service.suites.list_evaluations.return_value = []
        service.workflows.get_by_id.return_value = SimpleNamespace(
            id=uuid4(), name="HR Assistant", version="1.0"
        )
        service.workflows.get_all_minimal.return_value = []

        with pytest.raises(AppException) as excinfo:
            await service.export_workflow_evaluations(uuid4())
        assert excinfo.value.status_code == 404


class TestBundleSetPreview:
    @pytest.mark.asyncio
    async def test_preview_unions_refs_and_flags_existing_names(self):
        target_workflow_id = uuid4()
        service = _set_import_service(uuid4())
        service.suites.list_evaluations.return_value = [
            _stored_evaluation("Routing only", uuid4(), target_workflow_id)
        ]
        bundle_set = _bundle_set(str(uuid4()), str(uuid4()))

        preview = await service.preview_set_import(
            EvaluationSetImportPreviewRequest(
                bundle_set=bundle_set, target_workflow_id=target_workflow_id
            )
        )

        assert preview.can_import is True
        # Both items reference src-router; the union carries it exactly once.
        router_rows = [r for r in preview.node_refs if r.ref == "src-router"]
        assert len(router_rows) == 1
        assert router_rows[0].resolved_id == "tgt-router"
        assert [i.already_exists for i in preview.evaluations] == [False, True]
        assert preview.datasets[0].existing_dataset is None

    @pytest.mark.asyncio
    async def test_single_bundle_file_is_rejected_with_a_clear_message(self):
        service = _set_import_service(uuid4())
        bundle_set = _bundle_set(str(uuid4()), str(uuid4()))
        bundle_set.kind = EVALUATION_BUNDLE_KIND

        with pytest.raises(AppException) as excinfo:
            await service.preview_set_import(
                EvaluationSetImportPreviewRequest(
                    bundle_set=bundle_set, target_workflow_id=uuid4()
                )
            )
        assert excinfo.value.status_code == 400
        assert "single-evaluation" in excinfo.value.error_detail

    @pytest.mark.asyncio
    async def test_dangling_dataset_reference_is_rejected(self):
        service = _set_import_service(uuid4())
        bundle_set = _bundle_set(str(uuid4()), str(uuid4()))
        bundle_set.evaluations[1].dataset_local_id = 99

        with pytest.raises(AppException) as excinfo:
            await service.preview_set_import(
                EvaluationSetImportPreviewRequest(
                    bundle_set=bundle_set, target_workflow_id=uuid4()
                )
            )
        assert excinfo.value.status_code == 400

    @pytest.mark.asyncio
    async def test_empty_set_is_rejected(self):
        service = _set_import_service(uuid4())
        bundle_set = _bundle_set(str(uuid4()), str(uuid4()))
        bundle_set.evaluations = []

        with pytest.raises(AppException) as excinfo:
            await service.preview_set_import(
                EvaluationSetImportPreviewRequest(
                    bundle_set=bundle_set, target_workflow_id=uuid4()
                )
            )
        assert excinfo.value.status_code == 400


class TestBundleSetImport:
    @pytest.mark.asyncio
    async def test_batch_shares_created_dataset_and_skips_existing(self):
        target_workflow_id = uuid4()
        service = _set_import_service(uuid4())
        service.suites.list_evaluations.return_value = [
            _stored_evaluation("Third checks", uuid4(), target_workflow_id)
        ]
        _wire_batch_dataset_reuse(service, target_workflow_id)
        bundle_set = _bundle_set(str(uuid4()), str(uuid4()))
        bundle_set.evaluations.append(
            BundleSetItem(
                evaluation=_route_only_evaluation("Third checks"),
                dataset_local_id=1,
                references=bundle_set.evaluations[0].references,
            )
        )

        result = await service.import_bundle_set(
            EvaluationSetImportRequest(
                bundle_set=bundle_set, target_workflow_id=target_workflow_id
            )
        )

        assert [r.status for r in result.results] == [
            SET_ITEM_IMPORTED, SET_ITEM_IMPORTED, SET_ITEM_SKIPPED,
        ]
        assert (result.imported, result.skipped, result.failed) == (2, 1, 0)
        service.suites.create_suite.assert_awaited_once()
        assert result.results[1].reused_dataset is True
        # Not just "a" reuse: the second item must land on the suite the first
        # one created, which a wrong id in the batch map would not.
        assert result.results[1].suite_id == result.results[0].suite_id

    @pytest.mark.asyncio
    async def test_one_failing_item_does_not_stop_the_batch(self):
        target_workflow_id = uuid4()
        service = _set_import_service(uuid4())
        bundle_set = _bundle_set(str(uuid4()), str(uuid4()))
        broken = bundle_set.evaluations[0]
        broken.evaluation.technique_configs["route_taken"]["rules"][0][
            "router"
        ] = "missing-node"
        broken.references = BundleReferences()

        result = await service.import_bundle_set(
            EvaluationSetImportRequest(
                bundle_set=bundle_set, target_workflow_id=target_workflow_id
            )
        )

        assert [r.status for r in result.results] == [
            SET_ITEM_FAILED, SET_ITEM_IMPORTED,
        ]
        assert result.results[0].detail
        assert (result.imported, result.skipped, result.failed) == (1, 0, 1)

    @pytest.mark.asyncio
    async def test_include_imports_only_the_selected_items(self):
        target_workflow_id = uuid4()
        service = _set_import_service(uuid4())
        bundle_set = _bundle_set(str(uuid4()), str(uuid4()))

        result = await service.import_bundle_set(
            EvaluationSetImportRequest(
                bundle_set=bundle_set,
                target_workflow_id=target_workflow_id,
                include=[1],
            )
        )

        assert len(result.results) == 1
        assert result.results[0].name == "Routing only"
        assert result.results[0].status == SET_ITEM_IMPORTED

    @pytest.mark.asyncio
    async def test_out_of_range_selection_is_rejected(self):
        service = _set_import_service(uuid4())
        bundle_set = _bundle_set(str(uuid4()), str(uuid4()))

        with pytest.raises(AppException) as excinfo:
            await service.import_bundle_set(
                EvaluationSetImportRequest(
                    bundle_set=bundle_set,
                    target_workflow_id=uuid4(),
                    include=[5],
                )
            )
        assert excinfo.value.status_code == 400

    @pytest.mark.asyncio
    async def test_skip_existing_off_imports_duplicates(self):
        target_workflow_id = uuid4()
        service = _set_import_service(uuid4())
        service.suites.list_evaluations.return_value = [
            _stored_evaluation("Routing only", uuid4(), target_workflow_id)
        ]
        _wire_batch_dataset_reuse(service, target_workflow_id)

        result = await service.import_bundle_set(
            EvaluationSetImportRequest(
                bundle_set=_bundle_set(str(uuid4()), str(uuid4())),
                target_workflow_id=target_workflow_id,
                skip_existing=False,
            )
        )

        assert (result.imported, result.skipped, result.failed) == (2, 0, 0)


def _dataset(local_id: int, name: str, case_count: int = 1) -> BundleSetDataset:
    return BundleSetDataset(
        local_id=local_id,
        name=name,
        cases=[
            BundleCase(local_id=i, input_data={"message": f"m{i}"})
            for i in range(1, case_count + 1)
        ],
    )


def _item(name: str, dataset_local_id: int, references=None) -> BundleSetItem:
    return BundleSetItem(
        evaluation=_route_only_evaluation(name),
        dataset_local_id=dataset_local_id,
        references=references or BundleReferences(),
    )


def _router_references() -> BundleReferences:
    return BundleReferences(
        nodes={"src-router": BundleNodeRef(label="Intent Router", kind=REF_KIND_ROUTER)}
    )


class TestBundleSetSameNamedDatasets:
    """Two source suites can legitimately share a name; the file keeps them
    apart by local_id and the import must not collapse them."""

    @pytest.mark.asyncio
    async def test_same_named_datasets_stay_separate(self):
        target_workflow_id = uuid4()
        service = _set_import_service(uuid4())
        created = _wire_batch_dataset_reuse(service, target_workflow_id)
        bundle_set = EvaluationBundleSet(
            source=BundleSource(workflow_name="HR Assistant"),
            datasets=[_dataset(1, "Shared name", 2), _dataset(2, "Shared name", 3)],
            evaluations=[
                _item("First", 1, _router_references()),
                _item("Second", 2, _router_references()),
            ],
        )

        result = await service.import_bundle_set(
            EvaluationSetImportRequest(
                bundle_set=bundle_set, target_workflow_id=target_workflow_id
            )
        )

        assert (result.imported, result.failed) == (2, 0)
        assert result.results[0].suite_id != result.results[1].suite_id
        assert [r.reused_dataset for r in result.results] == [False, False]
        assert len(created) == 2
        # Both datasets' cases were created, not just the first one's.
        assert service.case_repo.create_many.await_count == 2

    @pytest.mark.asyncio
    async def test_dataset_already_on_target_is_still_reused(self):
        """The batch guard must not disable ordinary reuse of a PRE-EXISTING
        dataset, only of one this same batch created."""
        target_workflow_id = uuid4()
        existing_suite_id = uuid4()
        service = _set_import_service(uuid4())
        service.suites.list_suites.return_value = [
            SimpleNamespace(
                id=existing_suite_id,
                name="Shared name",
                workflow_id=target_workflow_id,
            )
        ]
        service.suites.get_suite.return_value = SimpleNamespace(
            id=existing_suite_id, name="Shared name", workflow_id=target_workflow_id
        )
        service.suites.list_cases_for_suite.return_value = [
            TestCaseInDB(
                id=uuid4(), suite_id=existing_suite_id, input_data={"message": "hi"},
                created_at=NOW, updated_at=NOW,
            )
        ]
        bundle_set = EvaluationBundleSet(
            datasets=[_dataset(1, "Shared name", 1)],
            evaluations=[_item("First", 1, _router_references())],
        )

        result = await service.import_bundle_set(
            EvaluationSetImportRequest(
                bundle_set=bundle_set, target_workflow_id=target_workflow_id
            )
        )

        assert result.results[0].status == SET_ITEM_IMPORTED
        assert result.results[0].reused_dataset is True
        assert result.results[0].suite_id == existing_suite_id
        service.suites.create_suite.assert_not_awaited()


class TestBundleSetSharedResolution:
    @pytest.mark.asyncio
    async def test_label_from_a_later_item_resolves_the_whole_set(self):
        """Items are exported against their own version, so only some record a
        label. Resolution uses the best metadata any item has, and the import
        replays it so no item disagrees with the preview."""
        target_workflow_id = uuid4()
        service = _set_import_service(uuid4())
        _wire_batch_dataset_reuse(service, target_workflow_id)
        bundle_set = EvaluationBundleSet(
            datasets=[_dataset(1, "Shared dataset", 2)],
            evaluations=[
                _item("No label recorded", 1, BundleReferences()),
                _item("Label recorded", 1, _router_references()),
            ],
        )

        preview = await service.preview_set_import(
            EvaluationSetImportPreviewRequest(
                bundle_set=bundle_set, target_workflow_id=target_workflow_id
            )
        )
        result = await service.import_bundle_set(
            EvaluationSetImportRequest(
                bundle_set=bundle_set, target_workflow_id=target_workflow_id
            )
        )

        assert preview.can_import is True
        assert preview.node_refs[0].resolved_id == "tgt-router"
        # The label-less item must import too, on the preview's decision.
        assert [r.status for r in result.results] == [
            SET_ITEM_IMPORTED, SET_ITEM_IMPORTED,
        ]

    @pytest.mark.asyncio
    async def test_preview_reports_each_item_s_own_refs(self):
        service = _set_import_service(uuid4())
        bundle_set = EvaluationBundleSet(
            datasets=[_dataset(1, "Shared dataset")],
            evaluations=[
                _item("Uses the router", 1, _router_references()),
                BundleSetItem(
                    evaluation=BundleEvaluation(
                        name="Uses nothing",
                        techniques=["llm_judge"],
                        technique_configs={"llm_judge": {"rules": []}},
                    ),
                    dataset_local_id=1,
                ),
            ],
        )

        preview = await service.preview_set_import(
            EvaluationSetImportPreviewRequest(
                bundle_set=bundle_set, target_workflow_id=uuid4()
            )
        )

        assert preview.evaluations[0].node_ref_keys == ["router:src-router"]
        assert preview.evaluations[1].node_ref_keys == []

    @pytest.mark.asyncio
    async def test_shared_provider_is_resolved_once(self):
        provider_id = str(uuid4())
        service = _set_import_service(uuid4())
        judge = {
            "llm_judge": {
                "rules": [{"rubric": "Grade", "min_score": 0.5}],
                "llm_provider_id": provider_id,
            }
        }
        items = [
            BundleSetItem(
                evaluation=BundleEvaluation(
                    name=name, techniques=["llm_judge"], technique_configs=judge
                ),
                dataset_local_id=1,
                references=BundleReferences(
                    llm_providers={provider_id: BundleProviderRef(model="gpt-4o")}
                ),
            )
            for name in ("First", "Second")
        ]
        bundle_set = EvaluationBundleSet(
            datasets=[_dataset(1, "Shared dataset")], evaluations=items
        )

        preview = await service.preview_set_import(
            EvaluationSetImportPreviewRequest(
                bundle_set=bundle_set, target_workflow_id=uuid4()
            )
        )

        assert len(preview.provider_refs) == 1
        service.providers.get_all_minimal.assert_awaited_once()


class TestBundleSetDuplicateNamesInFile:
    @pytest.mark.asyncio
    async def test_second_copy_of_a_name_inside_the_file_is_skipped(self):
        target_workflow_id = uuid4()
        service = _set_import_service(uuid4())
        _wire_batch_dataset_reuse(service, target_workflow_id)
        bundle_set = EvaluationBundleSet(
            datasets=[_dataset(1, "Shared dataset", 2)],
            evaluations=[
                _item("Same name", 1, _router_references()),
                _item("Same name", 1, _router_references()),
            ],
        )

        result = await service.import_bundle_set(
            EvaluationSetImportRequest(
                bundle_set=bundle_set, target_workflow_id=target_workflow_id
            )
        )

        assert [r.status for r in result.results] == [
            SET_ITEM_IMPORTED, SET_ITEM_SKIPPED,
        ]
        assert (result.imported, result.skipped) == (1, 1)


class TestBundleSetItemFailureDetail:
    @pytest.mark.asyncio
    async def test_only_bundle_messages_reach_the_client(self, monkeypatch):
        """A batch result never passes the exception handler's gate, so an
        internal detail would be returned verbatim inside a 201."""
        target_workflow_id = uuid4()
        service = _set_import_service(uuid4())
        _wire_batch_dataset_reuse(service, target_workflow_id)
        leaked = "ValidationError: 3 validation errors for InternalModel"

        async def explode(_request):
            raise AppException(
                status_code=400,
                error_key=ErrorKey.INVALID_REQUEST,
                error_detail=leaked,
            )

        monkeypatch.setattr(service, "import_bundle", explode)
        bundle_set = EvaluationBundleSet(
            datasets=[_dataset(1, "Shared dataset")],
            evaluations=[_item("Boom", 1, _router_references())],
        )

        result = await service.import_bundle_set(
            EvaluationSetImportRequest(
                bundle_set=bundle_set, target_workflow_id=target_workflow_id
            )
        )

        assert result.results[0].status == SET_ITEM_FAILED
        assert leaked not in (result.results[0].detail or "")
        assert result.results[0].detail == "The evaluation could not be imported."

    @pytest.mark.asyncio
    async def test_bundle_invalid_detail_is_passed_through_and_capped(
        self, monkeypatch
    ):
        target_workflow_id = uuid4()
        service = _set_import_service(uuid4())
        _wire_batch_dataset_reuse(service, target_workflow_id)

        async def explode(_request):
            raise AppException(
                status_code=400,
                error_key=ErrorKey.EVALUATION_BUNDLE_INVALID,
                error_detail="Every check was dropped. " + "x" * 500,
            )

        monkeypatch.setattr(service, "import_bundle", explode)
        bundle_set = EvaluationBundleSet(
            datasets=[_dataset(1, "Shared dataset")],
            evaluations=[_item("Boom", 1, _router_references())],
        )

        result = await service.import_bundle_set(
            EvaluationSetImportRequest(
                bundle_set=bundle_set, target_workflow_id=target_workflow_id
            )
        )

        detail = result.results[0].detail
        assert detail.startswith("Every check was dropped.")
        assert len(detail) <= 300


class TestBundleSetHeaderLimits:
    def _valid_set(self):
        return EvaluationBundleSet(
            datasets=[_dataset(1, "Shared dataset")],
            evaluations=[_item("One", 1)],
        )

    async def _expect_400(self, bundle_set):
        service = _set_import_service(uuid4())
        with pytest.raises(AppException) as excinfo:
            await service.preview_set_import(
                EvaluationSetImportPreviewRequest(
                    bundle_set=bundle_set, target_workflow_id=uuid4()
                )
            )
        assert excinfo.value.status_code == 400
        return excinfo.value

    @pytest.mark.asyncio
    async def test_newer_schema_version_is_rejected(self):
        bundle_set = self._valid_set()
        bundle_set.schema_version = EVALUATION_BUNDLE_SET_SCHEMA_VERSION + 1
        await self._expect_400(bundle_set)

    @pytest.mark.asyncio
    async def test_duplicate_dataset_ids_are_rejected(self):
        bundle_set = self._valid_set()
        bundle_set.datasets.append(_dataset(1, "Another"))
        await self._expect_400(bundle_set)

    @pytest.mark.asyncio
    async def test_datasets_no_evaluation_uses_are_rejected(self):
        bundle_set = self._valid_set()
        bundle_set.datasets.append(_dataset(2, "Unreferenced"))
        error = await self._expect_400(bundle_set)
        assert "no evaluation uses" in error.error_detail

    @pytest.mark.asyncio
    async def test_too_many_evaluations_is_rejected(self):
        bundle_set = self._valid_set()
        bundle_set.evaluations = [
            _item(f"Eval {i}", 1) for i in range(MAX_SET_EVALUATIONS + 1)
        ]
        await self._expect_400(bundle_set)

    @pytest.mark.asyncio
    async def test_too_many_datasets_is_rejected(self):
        bundle_set = self._valid_set()
        bundle_set.datasets = [
            _dataset(i, f"Dataset {i}") for i in range(1, MAX_SET_DATASETS + 2)
        ]
        await self._expect_400(bundle_set)

    @pytest.mark.asyncio
    async def test_oversized_dataset_is_rejected(self, monkeypatch):
        monkeypatch.setattr(eval_bundle, "MAX_BUNDLE_CASES", 1)
        bundle_set = self._valid_set()
        bundle_set.datasets = [_dataset(1, "Big", case_count=2)]
        error = await self._expect_400(bundle_set)
        assert "test cases" in error.error_detail

    @pytest.mark.asyncio
    async def test_too_many_cases_in_total_is_rejected(self, monkeypatch):
        monkeypatch.setattr(eval_bundle, "MAX_SET_TOTAL_CASES", 3)
        bundle_set = self._valid_set()
        bundle_set.datasets = [_dataset(1, "A", 2), _dataset(2, "B", 2)]
        bundle_set.evaluations = [_item("One", 1), _item("Two", 2)]
        error = await self._expect_400(bundle_set)
        assert "in total" in error.error_detail


class TestBundleSetExportLimits:
    @pytest.mark.asyncio
    async def test_export_refuses_a_dataset_the_import_would_reject(
        self, monkeypatch
    ):
        monkeypatch.setattr(eval_bundle, "MAX_BUNDLE_CASES", 1)
        workflow_id, suite_id = uuid4(), uuid4()
        evaluation = _stored_evaluation("Only one", suite_id, workflow_id)
        service = _service()
        service.suites.list_evaluations.return_value = [evaluation]
        service.suites.get_evaluation.return_value = evaluation
        service.suites.get_suite.return_value = TestSuiteInDB(
            id=suite_id, name="Big dataset", workflow_id=workflow_id,
            created_at=NOW, updated_at=NOW,
        )
        service.suites.list_cases_for_suite.return_value = [
            TestCaseInDB(
                id=uuid4(), suite_id=suite_id, input_data={"message": "a"},
                created_at=NOW, updated_at=NOW,
            ),
            TestCaseInDB(
                id=uuid4(), suite_id=suite_id, input_data={"message": "b"},
                created_at=NOW, updated_at=NOW,
            ),
        ]
        service.suites.get_evaluation_tool_catalog.return_value = (
            EvaluationToolCatalog(**_catalog("src"))
        )
        service.workflows.get_by_id.return_value = SimpleNamespace(
            id=workflow_id, name="HR Assistant", version="1.0"
        )
        service.workflows.get_all_minimal.return_value = []
        service.providers.get_all_minimal.return_value = []

        with pytest.raises(AppException) as excinfo:
            await service.export_workflow_evaluations(workflow_id)
        assert excinfo.value.status_code == 400
        assert "Big dataset" in excinfo.value.error_detail


class TestBundleSetResolutionSize:
    @pytest.mark.asyncio
    async def test_large_pick_map_does_not_fail_every_item(self):
        """The union plus the caller's picks can exceed one item's resolution
        cap; each item must only be sent the picks its own refs need."""
        target_workflow_id = uuid4()
        service = _set_import_service(uuid4())
        _wire_batch_dataset_reuse(service, target_workflow_id)
        bundle_set = EvaluationBundleSet(
            datasets=[_dataset(1, "Shared dataset", 2)],
            evaluations=[_item("One", 1, _router_references())],
        )
        # Filled to the cap with picks for refs this item does not use.
        filler = {f"action:node-{i}": "tgt-escalation" for i in range(1000)}

        result = await service.import_bundle_set(
            EvaluationSetImportRequest(
                bundle_set=bundle_set,
                target_workflow_id=target_workflow_id,
                resolutions=filler,
            )
        )

        assert result.results[0].status == SET_ITEM_IMPORTED


class TestBundleSetVerdictIsShared:
    """An item must reach the union's verdict, not its own. Replaying only the
    union's successes let an item quietly resolve what the preview refused."""

    @pytest.mark.asyncio
    async def test_item_cannot_resolve_a_ref_the_preview_refused(self):
        target_workflow_id = uuid4()
        service = _set_import_service(uuid4())
        _wire_batch_dataset_reuse(service, target_workflow_id)
        # Item 1 records a type that contradicts the target node, which
        # downgrades the whole set's ref to "confirm this yourself".
        typed = BundleReferences(
            nodes={
                "src-escalation": BundleNodeRef(
                    label="Escalation Message", kind=REF_KIND_ACTION,
                    node_type="httpNode",
                )
            }
        )
        untyped = BundleReferences(
            nodes={
                "src-escalation": BundleNodeRef(
                    label="Escalation Message", kind=REF_KIND_ACTION
                )
            }
        )
        # A second check keeps each evaluation importable once the action rule
        # is dropped, so the test observes the binding rather than the
        # zero-checks refusal.
        action_config = {
            "action_taken": {"rules": [{"node": "src-escalation", "should_fire": True}]},
            "llm_judge": {"rules": [{"rubric": "Grade", "min_score": 0.5}]},
        }
        items = [
            BundleSetItem(
                evaluation=BundleEvaluation(
                    name=name,
                    techniques=["action_taken", "llm_judge"],
                    technique_configs=action_config,
                ),
                dataset_local_id=1,
                references=references,
            )
            for name, references in (("Typed", typed), ("Untyped", untyped))
        ]
        bundle_set = EvaluationBundleSet(
            datasets=[_dataset(1, "Shared dataset", 2)], evaluations=items
        )

        preview = await service.preview_set_import(
            EvaluationSetImportPreviewRequest(
                bundle_set=bundle_set, target_workflow_id=target_workflow_id
            )
        )
        result = await service.import_bundle_set(
            EvaluationSetImportRequest(
                bundle_set=bundle_set,
                target_workflow_id=target_workflow_id,
                drop_unresolved_rules=True,
            )
        )

        assert preview.can_import is False
        assert preview.node_refs[0].status == REF_STATUS_AMBIGUOUS
        # Neither item may bind the reference the user was told to confirm.
        created = [
            call.args[0] for call in service.suites.create_evaluation.await_args_list
        ]
        for evaluation in created:
            assert evaluation.technique_configs.get("action_taken") is None
        assert all(r.dropped_rules for r in result.results)

    @pytest.mark.asyncio
    async def test_item_is_not_failed_by_a_ref_the_preview_resolved(self):
        """The other direction: the label-less item must still import."""
        target_workflow_id = uuid4()
        service = _set_import_service(uuid4())
        _wire_batch_dataset_reuse(service, target_workflow_id)
        bundle_set = EvaluationBundleSet(
            datasets=[_dataset(1, "Shared dataset", 2)],
            evaluations=[
                _item("No metadata", 1, BundleReferences()),
                _item("Has the label", 1, _router_references()),
            ],
        )

        result = await service.import_bundle_set(
            EvaluationSetImportRequest(
                bundle_set=bundle_set, target_workflow_id=target_workflow_id
            )
        )

        assert [r.status for r in result.results] == [
            SET_ITEM_IMPORTED, SET_ITEM_IMPORTED,
        ]
        assert all(not r.dropped_rules for r in result.results)


class TestBundleSetSameNameWithPreexistingTarget:
    @pytest.mark.asyncio
    async def test_only_the_first_same_named_dataset_reuses_the_target_one(self):
        """Two file datasets share a name AND the target already owns it. The
        first attaches to the existing one; the second keeps its own cases."""
        target_workflow_id = uuid4()
        existing_suite_id = uuid4()
        service = _set_import_service(uuid4())
        existing = SimpleNamespace(
            id=existing_suite_id, name="Regression", workflow_id=target_workflow_id
        )
        created = _wire_batch_dataset_reuse(service, target_workflow_id)
        created[str(existing_suite_id)] = existing

        bundle_set = EvaluationBundleSet(
            datasets=[_dataset(1, "Regression", 1), _dataset(2, "Regression", 5)],
            evaluations=[
                _item("First", 1, _router_references()),
                _item("Second", 2, _router_references()),
            ],
        )

        result = await service.import_bundle_set(
            EvaluationSetImportRequest(
                bundle_set=bundle_set, target_workflow_id=target_workflow_id
            )
        )

        assert (result.imported, result.failed) == (2, 0)
        assert result.results[0].suite_id == existing_suite_id
        assert result.results[0].reused_dataset is True
        # The second dataset is a different dataset; its cases must exist.
        assert result.results[1].suite_id != existing_suite_id
        assert result.results[1].reused_dataset is False
        service.case_repo.create_many.assert_awaited_once()


class TestBundleSetPreviewMatchesImport:
    @pytest.mark.asyncio
    async def test_only_the_first_namesake_is_previewed_as_reused(self):
        """Import gives every later namesake its own dataset, so the preview
        must not promise reuse for all of them."""
        target_workflow_id = uuid4()
        existing_suite_id = uuid4()
        service = _set_import_service(uuid4())
        service.suites.list_suites.return_value = [
            SimpleNamespace(
                id=existing_suite_id, name="Regression",
                workflow_id=target_workflow_id,
            )
        ]
        service.suites.list_cases_for_suite.return_value = []
        bundle_set = EvaluationBundleSet(
            datasets=[_dataset(1, "Regression", 1), _dataset(2, "Regression", 5)],
            evaluations=[
                _item("First", 1, _router_references()),
                _item("Second", 2, _router_references()),
            ],
        )

        preview = await service.preview_set_import(
            EvaluationSetImportPreviewRequest(
                bundle_set=bundle_set, target_workflow_id=target_workflow_id
            )
        )

        assert preview.datasets[0].existing_dataset is not None
        assert preview.datasets[1].existing_dataset is None
