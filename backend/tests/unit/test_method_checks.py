"""Older evaluation methods read back as checks, every setting included."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.schemas.test_suite import ChecksPreviewRequest
from app.services.method_checks import (
    OLDER_METHODS_KEY,
    convert_methods,
    converted_evaluation,
    needs_conversion,
)
from app.services.scenario_checks import describe_check, parse_checks_config
from app.services.test_suite import TestSuiteService

CATALOG = {
    "agents": [
        {"id": "agent-1", "label": "Refund agent", "tools": [
            {"id": "tool-1", "name": "save_region", "label": "Save region"},
            {"id": "tool-2", "name": "change_mode", "label": "Change mode"},
        ]},
    ],
    "routers": [{"id": "router-1", "label": "Mode", "branches": [
        {"value": "case-a", "label": "Refund"},
        {"value": "case-b", "label": "Standard"},
    ]}],
    "action_nodes": [
        {"id": "step-1", "label": "Create ticket", "type": "zendeskTicketNode"},
        {"id": "step-2", "label": "Log", "type": "logNode"},
    ],
}


def sentences(conversion):
    return [describe_check(parse_checks_config({"checks": [check]}).checks[0]) for check in conversion.checks]


class TestReplyMethods:
    def test_each_reply_method_becomes_one_check(self):
        conversion = convert_methods(
            ["exact_match", "contains", "json_match", "no_errors", "not_contains"],
            {"not_contains": {"phrases": ["RingGo", "JustPark"]}},
        )
        assert sentences(conversion) == [
            "On every turn, the reply should be exactly the expected reply.",
            "On every turn, the reply should contain the expected reply.",
            # JSON Match compared the whole output with the whole expected output.
            'On every turn, the value at "outputs" should be the expected reply.',
            "In every conversation, no step should ever fail.",
            'In every conversation, the reply should never mention "RingGo".',
            'In every conversation, the reply should never mention "JustPark".',
        ]
        assert conversion.left_out == []

    @pytest.mark.parametrize(
        "technique, config, sentence",
        [
            ("nli_eval", {}, "On every turn, the reply should stick to the expected reply, graded by the NLI model."),
            ("nli_eval", {"evidence_source": "kb_retrievals"},
             "On every turn, the reply should stick to the knowledge base, graded by the NLI model."),
            ("nli_eval", {"evidence_field": "trace.retrievals"},
             "On every turn, the reply should stick to the knowledge base, graded by the NLI model."),
            ("nli_eval", {"evidence_source": "tool_events"},
             "On every turn, the reply should stick to the tool results, graded by the NLI model."),
            ("nli_eval", {"evidence_source": "conversation_context"},
             "On every turn, the reply should stick to the session values, graded by the NLI model."),
            ("nli_eval", {"evidence_field": "trace.nodes.lookup.output"},
             'On every turn, the reply should stick to the value at "trace.nodes.lookup.output", graded by the NLI model.'),
            ("provenance_eval", {"context_source": "expected_output"},
             "On every turn, the reply should stick to the expected reply, graded by text similarity."),
            ("provenance_eval", {"context_source": "expected_output", "provenance_mode": "llm"},
             "On every turn, the reply should stick to the expected reply."),
            ("provenance_eval", {"context_source": "kb_retrievals"},
             "On every turn, the reply should stick to the knowledge base, graded by text similarity."),
        ],
    )
    def test_grounding_methods(self, technique, config, sentence):
        conversion = convert_methods([technique], {technique: config})
        assert sentences(conversion) == [sentence]
        assert conversion.left_out == []

    def test_grounding_keeps_its_pass_score_instruction_and_provider(self):
        conversion = convert_methods(["nli_eval", "provenance_eval"], {
            "nli_eval": {"min_entail_score": 0.8},
            "provenance_eval": {
                "context_source": "kb_retrievals", "use_llm_judge": True, "llm_provider_id": "p2",
                "min_score": 0.9, "llm_judge_system_prompt_suffix": "Numbers must match.",
            },
        })
        assert sentences(conversion) == [
            "On every turn, the reply should stick to the expected reply, graded by the NLI model (passes at 0.8).",
            'On every turn, the reply should stick to the knowledge base, also: "Numbers must match." (passes at 0.9).',
        ]
        assert conversion.llm_provider_id == "p2"
        assert conversion.left_out == []

    def test_nli_and_similarity_keep_every_setting_they_graded_with(self):
        conversion = convert_methods(["nli_eval", "provenance_eval"], {
            "nli_eval": {"min_entail_score": 0.3, "fail_on_contradiction": True, "nli_model_name": "cross-encoder/nli-roberta-base"},
            "provenance_eval": {"context_source": "kb_retrievals", "min_score": 0.85, "embedding_type": "openai",
                                "embedding_model_name": "text-embedding-3-small", "embedding_base_url": "https://e.example"},
        })
        nli, similarity = conversion.checks
        assert (nli["grader"], nli["pass_score"], nli["fail_on_contradiction"], nli["nli_model"]) == (
            "nli", 0.3, True, "cross-encoder/nli-roberta-base",
        )
        assert (similarity["grader"], similarity["pass_score"], similarity["embedding"]) == (
            "similarity", 0.85, {"type": "openai", "model_name": "text-embedding-3-small"},
        )
        assert sentences(conversion)[0] == (
            "On every turn, the reply should stick to the expected reply, graded by the NLI model,"
            " failing any contradiction (passes at 0.3)."
        )
        # The server's key never goes to another address, so the method's own address is left out.
        assert conversion.left_out == ["Provenance Evaluation: its own embedding address. Text similarity uses the server's."]

    def test_settings_that_never_graded_are_listed(self):
        conversion = convert_methods(["nli_eval", "provenance_eval", "llm_judge"], {
            "nli_eval": {"min_entail_score": 1.5},
            "provenance_eval": {"embedding_api_key": "sk-1"},
            "llm_judge": {"rules": [{"rubric": "Greet", "min_score": 1.2}]},
        })
        assert sentences(conversion) == ["On every turn, the reply should stick to the expected reply, graded by text similarity."]
        assert conversion.left_out == [
            "NLI Evaluation: its threshold of 1.5 is outside 0 to 1, so it never graded.",
            "Provenance Evaluation: its own embedding API key. Text similarity uses the server's key.",
            'LLM Judge "Greet": its pass score of 1.2 is above 1, so it could never pass.',
        ]

    def test_a_method_with_nothing_to_grade_is_listed(self):
        conversion = convert_methods(["not_contains", "llm_judge"], {"not_contains": {"phrases": []}, "llm_judge": {}})
        assert conversion.checks == []
        assert conversion.left_out == [
            "Does Not Contain had no words to look for, so it failed every turn.",
            "LLM Judge had no rule to grade, so it failed every turn.",
        ]

    def test_grounding_against_the_reply_itself_always_passed(self):
        conversion = convert_methods(["nli_eval"], {"nli_eval": {"evidence_source": "output"}})
        assert conversion.checks == []
        assert conversion.left_out == []

    def test_field_equals(self):
        assert sentences(convert_methods(["field_equals"], {"field_equals": {}})) == [
            "On every turn, the reply should be exactly the expected reply.",
        ]
        fixed = convert_methods(["field_equals"], {"field_equals": {"expected": "Hello"}})
        assert sentences(fixed) == ['On every turn, the reply should be exactly "Hello".']
        session = convert_methods(["field_equals"], {"field_equals": {"field": "trace.session.mode", "expected": "refund"}})
        assert sentences(session) == ['On every turn, the value at "trace.session.mode" should be "refund".']
        against_reply = convert_methods(["field_equals"], {"field_equals": {"field": "outputs.status"}})
        assert sentences(against_reply) == ['On every turn, the value at "outputs.status" should be the expected reply.']
        assert fixed.left_out == session.left_out == against_reply.left_out == []

    def test_two_methods_asking_the_same_make_one_check(self):
        conversion = convert_methods(["exact_match", "json_match", "field_equals", "nli_eval"], {})
        assert [(check["kind"], check.get("match")) for check in conversion.checks] == [
            ("reply_matches", "exact"), ("value_equals", None), ("reply_grounded", None),
        ]

    def test_an_embedding_threshold_is_the_similarity_it_passes_at(self):
        conversion = convert_methods(["provenance_eval"], {"provenance_eval": {"min_score": 0.3}})
        assert sentences(conversion) == [
            "On every turn, the reply should stick to the expected reply, graded by text similarity (passes at 0.3)."
        ]
        assert conversion.left_out == []

    def test_odd_stored_settings_do_not_stop_the_others(self):
        conversion = convert_methods(["not_contains", "field_equals"], {
            "not_contains": {"phrases": None, "text": "RingGo"},
            "field_equals": {"expected": ""},
        })
        assert sentences(conversion) == ['In every conversation, the reply should never mention "RingGo".']
        assert conversion.left_out == ["Field Equals with no expected value."]
        empty_tool = convert_methods(["tool_used"], {"tool_used": {"rules": [{"id": "r", "tool_ids": ["", "tool-1"]}]}}, CATALOG)
        assert [check["tool"] for check in empty_tool.checks] == ["tool-1"]

    def test_an_evaluation_saved_with_no_method_ran_the_defaults(self):
        assert needs_conversion([])
        assert [check["kind"] for check in convert_methods([], {}).checks] == [
            "reply_matches", "reply_matches", "value_equals", "step_fails", "reply_grounded", "reply_grounded",
        ]
        assert not needs_conversion(["checks"])
        assert needs_conversion(["checks", "contains"])


class TestJudge:
    def test_rubrics_keep_their_source_pass_score_and_provider(self):
        conversion = convert_methods(["llm_judge"], {"llm_judge": {
            "llm_provider_id": "p1",
            "rules": [
                {"rubric": "Be polite"},
                {"rubric": "Agrees with the answer", "source_type": "expected_output"},
                {"rubric": "Quotes passages", "source_type": "kb_retrievals", "min_score": 0.7, "label": "Grounded"},
                {"rubric": "Uses the state", "source_type": "conversation_context"},
                {"rubric": "Names the tool", "source_type": "tool_events"},
                {"rubric": "Uses the step", "source_field": "trace.nodes.step.output"},
            ],
        }})
        assert sentences(conversion) == [
            'On every turn, the reply should do this: "Be polite".',
            'On every turn, the reply should do this: "Agrees with the answer", graded with the expected reply.',
            'On every turn, the reply should do this: "Quotes passages", graded with the knowledge-base passages'
            " (passes at 0.7).",
            'On every turn, the reply should do this: "Uses the state", graded with the session values.',
            'On every turn, the reply should do this: "Names the tool", graded with the tool calls.',
            'On every turn, the reply should do this: "Uses the step", graded with the value at "trace.nodes.step.output".',
        ]
        assert conversion.llm_provider_id == "p1"
        assert conversion.left_out == []

    def test_the_single_rubric_shape(self):
        assert sentences(convert_methods(["llm_judge"], {"llm_judge": {"rubric": "Greet"}})) == [
            'On every turn, the reply should do this: "Greet".',
        ]

    def test_fields_the_screens_never_offered_are_listed(self):
        conversion = convert_methods(["llm_judge"], {"llm_judge": {"rubric": "Greet", "answer_field": "outputs.text"}})
        assert len(conversion.checks) == 1
        assert conversion.left_out == ['LLM Judge: grading "outputs.text" in place of the answer.']


class TestRules:
    def test_tools_by_operator_and_scope(self):
        conversion = convert_methods(["tool_used"], {"tool_used": {"rules": [
            {"id": "r1", "tool_ids": ["tool-1"], "operator": "all", "agent_id": "agent-1",
             "per_tool": {"tool-1": {"expected_args": {"region": "united-kingdom"}}}},
            {"id": "r2", "tool_ids": ["tool-2"], "operator": "none", "scope": "conversation"},
            {"id": "r3", "tool_ids": ["tool-2"], "operator": "all", "scope": "specific_turn",
             "target_source_conversation_id": "conv-1", "target_turn_indexes": [0, 2]},
        ]}}, CATALOG)
        assert sentences(conversion) == [
            'On every turn, the tool "save_region" should be called by "Refund agent" with region = united-kingdom.',
            'In every conversation, the tool "change_mode" should never be called.',
            'The tool "change_mode" should be called.',
            'The tool "change_mode" should be called.',
        ]
        turn_checks = conversion.checks[2:]
        assert [(check["conversation_id"], check["turn_index"]) for check in turn_checks] == [("conv-1", 0), ("conv-1", 2)]
        assert conversion.left_out == []

    def test_every_tool_usage_setting_has_a_check(self):
        conversion = convert_methods(["tool_used"], {"tool_used": {"rules": [
            {"id": "r1", "tool_ids": ["tool-1", "tool-2"], "operator": "any"},
            {"id": "r2", "tool_ids": ["tool-1"], "operator": "only"},
            {"id": "r3", "tool_ids": [], "operator": "only", "scope": "conversation"},
            {"id": "r4", "tool_ids": ["tool-1"], "operator": "all", "max_calls": 2, "require_success": True,
             "per_tool": {"tool-1": {"result_not_empty": True, "result_contains": "saved"}}},
        ]}}, CATALOG)
        assert sentences(conversion) == [
            'On every turn, one of the tools "save_region" or "change_mode" should be called.',
            'On every turn, only the tool "save_region" should be used.',
            "In every conversation, no tool should be used.",
            'On every turn, the tool "save_region" should be called at most 2 times and succeed'
            ' and return a result that contains "saved".',
        ]
        assert conversion.left_out == []

    def test_a_count_over_several_tools_counts_them_together(self):
        conversion = convert_methods(["tool_used"], {"tool_used": {"rules": [
            {"id": "r1", "tool_ids": ["tool-1", "tool-2"], "operator": "all", "min_calls": 3},
        ]}}, CATALOG)
        assert sentences(conversion) == [
            'On every turn, the tool "save_region" should be called.',
            'On every turn, the tool "change_mode" should be called.',
            'On every turn, one of the tools "save_region" or "change_mode" should be called at least 3 times in all.',
        ]

    def test_any_of_several_tools_keeps_what_each_one_checks(self):
        conversion = convert_methods(["tool_used"], {"tool_used": {"rules": [
            {"id": "r1", "tool_ids": ["tool-1", "tool-2"], "operator": "any", "require_success": True, "per_tool": {
                "tool-1": {"expected_args": {"region": "uk"}},
                "tool-2": {"result_contains": "refund"},
            }},
        ]}}, CATALOG)
        [check] = conversion.checks
        assert (check["tool_name"], check["args"]) == ("save_region", {"region": "uk"})
        assert check["tools"] == [{"tool": "tool-2", "tool_name": "change_mode", "result_contains": "refund"}]
        assert sentences(conversion) == [
            'On every turn, one of the tools "save_region" (with region = uk) or "change_mode"'
            ' (returning a result that contains "refund") should be called and succeed.'
        ]
        assert conversion.left_out == []

    def test_a_rule_that_does_not_read_keeps_the_others(self):
        conversion = convert_methods(["tool_used"], {"tool_used": {"rules": [
            {"id": "r1", "tool_ids": ["tool-1"], "operator": "nonsense"},
            {"id": "r2", "tool_ids": ["tool-1"], "operator": "all"},
        ]}}, CATALOG)
        assert len(conversion.checks) == 1
        assert conversion.left_out == ["Tool Usage: a rule that could not be read."]

    def test_routes_match_a_branch_by_value_or_label(self):
        conversion = convert_methods(["route_taken"], {"route_taken": {"rules": [
            {"id": "r1", "router": "Mode", "expected": "Refund"},
            {"id": "r2", "expected": "case-b"},
        ]}}, CATALOG)
        assert sentences(conversion) == [
            'On every turn, the router "Mode" should take "Refund".',
            # No router named stays any router, so one added later counts too.
            'On every turn, a router should take "Standard".',
        ]
        assert conversion.checks[0]["branch"] == "case-a"
        assert conversion.checks[1]["branch"] == "case-b"

    def test_rules_saved_before_ids_read_as_the_runner_reads_them(self):
        conversion = convert_methods(["route_taken", "action_taken"], {
            "route_taken": {"rules": [{"node": "Mode", "expected": "Refund"}]},
            "action_taken": {"rules": [{"node": "Log"}]},
        }, CATALOG)
        assert sentences(conversion) == [
            'On every turn, the router "Mode" should take "Refund".',
            'On every turn, the step "Log" should run.',
        ]
        assert conversion.left_out == []

    def test_a_route_on_any_router(self):
        catalog = {**CATALOG, "routers": CATALOG["routers"] + [{"id": "router-2", "label": "Other", "branches": []}]}
        conversion = convert_methods(["route_taken"], {"route_taken": {"rules": [{"id": "r1", "expected": "Refund"}]}}, catalog)
        assert sentences(conversion) == ['On every turn, a router should take "Refund".']
        assert conversion.checks[0]["branch"] == "case-a"
        assert conversion.left_out == []

    def test_steps_by_name_or_type(self):
        conversion = convert_methods(["action_taken"], {"action_taken": {"rules": [
            {"id": "r1", "node": "Create ticket", "should_fire": False},
            {"id": "r2", "node_type": "zendeskTicketNode"},
        ]}}, CATALOG)
        assert sentences(conversion) == [
            'In every conversation, the step "Create ticket" should never run.',
            'On every turn, a step of type "Zendesk ticket" should run.',
        ]
        assert conversion.checks[1]["step_type"] == "zendeskTicketNode"
        assert conversion.left_out == []

    def test_without_the_workflow_ids_stay(self):
        conversion = convert_methods(["tool_used"], {"tool_used": {"rules": [
            {"id": "r1", "tool_ids": ["tool-9"], "operator": "all"},
        ]}})
        assert conversion.checks[0]["tool"] == "tool-9"
        assert "tool_name" not in conversion.checks[0]


class TestConvertedEvaluation:
    def test_only_checks_remain_and_the_older_methods_are_kept_aside(self):
        configs = {
            "checks": {"checks": [{"id": "own", "kind": "reply_mentions", "text": "Hi"}], "llm_provider_id": "p0"},
            "contains": {},
            "llm_judge": {"llm_provider_id": "p1", "rules": [{"rubric": "Greet", "min_score": 0.8}]},
        }
        techniques, new_configs, conversion = converted_evaluation(["checks", "contains", "llm_judge"], configs)
        assert techniques == ["checks"]
        assert list(new_configs) == ["checks"]
        checks = new_configs["checks"]
        assert [check["id"] for check in checks["checks"]] == ["own", "check-reply-matches-1", "check-reply-meets-1"]
        assert checks["llm_provider_id"] == "p0"
        assert checks[OLDER_METHODS_KEY] == {
            "techniques": ["checks", "contains", "llm_judge"],
            "technique_configs": {"contains": {}, "llm_judge": configs["llm_judge"]},
            "left_out": conversion.left_out,
        }
        parse_checks_config(checks)

    def test_a_converted_check_already_there_is_not_added_twice(self):
        own = {"id": "own", "expect": "should_not", "kind": "step_fails", "level": "every_conversation", "when": "anywhere"}
        _, configs, _ = converted_evaluation(["checks", "no_errors"], {"checks": {"checks": [own]}})
        assert configs["checks"]["checks"] == [own]

    def test_converting_again_keeps_the_first_record(self):
        _, first, _ = converted_evaluation(["contains"], {"contains": {}})
        _, second, _ = converted_evaluation(["checks", "no_errors"], first)
        record = second["checks"][OLDER_METHODS_KEY]
        assert record["techniques"] == ["checks", "no_errors"]
        assert record["earlier"]["techniques"] == ["contains"]
        assert [check["kind"] for check in second["checks"]["checks"]] == ["reply_matches", "step_fails"]

    def test_converting_twice_gives_the_same_checks(self):
        configs = {"contains": {}, "not_contains": {"phrases": ["x"]}}
        first = converted_evaluation(["contains", "not_contains"], configs)[1]
        second = converted_evaluation(["contains", "not_contains"], configs)[1]
        assert first == second


def service(rows):
    instance = TestSuiteService.__new__(TestSuiteService)
    instance.evaluation_repo = MagicMock()
    instance.evaluation_repo.get_by_id = AsyncMock(side_effect=lambda id_: next((r for r in rows if r.id == id_), None))
    instance.evaluation_repo.update = AsyncMock(side_effect=lambda row: row)
    instance._effective_workflow_id = AsyncMock(side_effect=lambda workflow_id, suite_id: workflow_id)
    instance._walk_workflow_catalog = AsyncMock(return_value=CATALOG)
    return instance


def row(techniques, configs=None, workflow_id=None):
    now = "2026-10-13T00:00:00"
    return SimpleNamespace(
        id=uuid4(), name="E", description=None, suite_id=uuid4(), workflow_id=workflow_id or uuid4(),
        techniques=techniques, technique_configs=configs, input_metadata=None, run_ids=[],
        created_at=now, updated_at=now,
    )


class TestService:
    @pytest.mark.asyncio
    async def test_a_preview_reads_older_methods_as_checks_and_saves_nothing(self):
        older = row(["contains", "tool_used"], {"tool_used": {"rules": [{"id": "r", "tool_ids": ["tool-1"]}]}})
        done = row(["checks"], {"checks": {"checks": [{"id": "a", "kind": "step_fails", "expect": "should_not"}]}})
        instance = service([older, done])
        result = await instance.preview_checks(ChecksPreviewRequest(evaluation_ids=[older.id, done.id, older.id]))
        [preview] = result.evaluations
        assert (preview.id, preview.techniques) == (older.id, ["checks"])
        checks = preview.technique_configs["checks"]["checks"]
        assert [check["kind"] for check in checks] == ["reply_matches", "tool_called"]
        assert checks[1]["tool_name"] == "save_region"
        assert older.techniques == ["contains", "tool_used"]
        instance.evaluation_repo.update.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_by_id_and_without_a_catalog(self):
        older = row(["exact_match"])
        instance = service([older])
        instance._walk_workflow_catalog = AsyncMock(side_effect=RuntimeError("gone"))
        result = await instance.preview_checks(ChecksPreviewRequest(evaluation_ids=[older.id, uuid4()]))
        assert [evaluation.techniques for evaluation in result.evaluations] == [["checks"]]


class TestRunStart:
    def start(self, evaluation):
        instance = service([evaluation])
        instance._default_run_workflow_id = AsyncMock(return_value=uuid4())
        instance.create_run = AsyncMock(side_effect=lambda suite_id, data: SimpleNamespace(id=uuid4(), data=data))
        instance.append_run_to_evaluation = AsyncMock()
        dispatch = MagicMock()
        return instance, dispatch

    @pytest.mark.asyncio
    async def test_older_methods_run_as_checks_and_stay_on_the_evaluation(self):
        evaluation = row(["contains"])
        instance, dispatch = self.start(evaluation)
        run = await instance._start_evaluation_run(evaluation, dispatch)
        assert run.data.techniques == ["checks"]
        assert run.data.technique_configs["checks"]["checks"][0]["kind"] == "reply_matches"
        assert dispatch.call_args.args[2] == run.data.technique_configs
        assert evaluation.techniques == ["contains"]
        instance.evaluation_repo.update.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_checks_run_as_they_are(self):
        configs = {"checks": {"checks": [{"id": "a", "kind": "step_fails", "expect": "should_not"}]}}
        evaluation = row(["checks"], configs)
        instance, dispatch = self.start(evaluation)
        run = await instance._start_evaluation_run(evaluation, dispatch)
        assert (run.data.techniques, run.data.technique_configs) == (["checks"], configs)


def test_only_these_tools_keeps_counts_per_turn_and_success():
    conversion = convert_methods(["tool_used"], {"tool_used": {"rules": [
        {"id": "r", "tool_ids": ["tool-1"], "operator": "only", "scope": "every_turn", "max_calls": 2, "require_success": True},
        {"id": "s", "tool_ids": ["tool-1"], "operator": "only", "scope": "every_turn", "require_success": True},
    ]}}, CATALOG)
    first, second = conversion.checks
    assert (first["when"], first["max_calls"], first["succeeds"]) == ("every_turn", 2, True)
    # Without a count, success changes nothing an only rule checks.
    assert "succeeds" not in second
    assert sentences(conversion)[0] == (
        'On every turn, only the tool "save_region" should be used, called successfully at most 2 times.'
    )


def test_values_that_are_not_text_are_stored_as_the_editor_shows_them():
    conversion = convert_methods(["field_equals", "tool_used"], {
        "field_equals": {"field": "outputs.item", "expected": {"b": 2, "a": 1}},
        "tool_used": {"rules": [{"id": "r", "tool_ids": ["tool-1"],
                                 "per_tool": {"tool-1": {"expected_args": {"filters": {"region": "uk"}, "ok": True}}}}]},
    }, CATALOG)
    value_check, tool_check = conversion.checks
    assert value_check["value"] == '{"a": 1, "b": 2}'
    assert tool_check["args"] == {"filters": '{"region": "uk"}', "ok": "True"}


def test_each_method_keeps_its_own_ai_grader():
    techniques, configs, _ = converted_evaluation(["llm_judge", "provenance_eval"], {
        "llm_judge": {"llm_provider_id": "judge", "rules": [{"rubric": "Greet"}]},
        "provenance_eval": {"provenance_mode": "llm", "llm_provider_id": "other", "context_source": "kb_retrievals"},
    })
    checks = configs["checks"]
    assert "llm_provider_id" not in checks
    rule, grounded = checks["checks"]
    assert (rule["llm_provider_id"], grounded["llm_provider_id"]) == ("judge", "other")


def test_one_grader_for_every_method_grades_the_evaluation():
    _, configs, _ = converted_evaluation(["llm_judge", "provenance_eval"], {
        "llm_judge": {"llm_provider_id": "judge", "rules": [{"rubric": "Greet"}]},
        "provenance_eval": {"provenance_mode": "llm", "llm_provider_id": "judge", "context_source": "kb_retrievals"},
    })
    checks = configs["checks"]
    assert checks["llm_provider_id"] == "judge"
    assert all("llm_provider_id" not in check for check in checks["checks"])


def test_a_method_without_a_grader_keeps_the_default_model():
    _, configs, _ = converted_evaluation(["llm_judge", "provenance_eval"], {
        "llm_judge": {"rules": [{"rubric": "Greet"}]},
        "provenance_eval": {"provenance_mode": "llm", "llm_provider_id": "other", "context_source": "kb_retrievals"},
    })
    checks = configs["checks"]
    assert "llm_provider_id" not in checks
    rule, grounded = checks["checks"]
    assert "llm_provider_id" not in rule
    assert grounded["llm_provider_id"] == "other"


def test_the_evaluations_grader_moves_onto_its_own_checks_beside_a_default_one():
    _, configs, _ = converted_evaluation(["checks", "llm_judge"], {
        "checks": {"llm_provider_id": "p0", "checks": [
            {"id": "own", "kind": "reply_meets", "rubric": "Polite"},
            {"id": "mine", "kind": "reply_meets", "rubric": "Short", "llm_provider_id": "p9"},
        ]},
        "llm_judge": {"rules": [{"rubric": "Greet"}]},
    })
    checks = configs["checks"]
    assert "llm_provider_id" not in checks
    own, mine, rule = checks["checks"]
    assert (own["llm_provider_id"], mine["llm_provider_id"]) == ("p0", "p9")
    assert "llm_provider_id" not in rule


def test_the_evaluations_own_checks_keep_the_default_model_beside_one_converted_grader():
    _, configs, _ = converted_evaluation(["checks", "llm_judge"], {
        "checks": {"checks": [{"id": "own", "kind": "reply_meets", "rubric": "Polite"}]},
        "llm_judge": {"llm_provider_id": "judge", "rules": [{"rubric": "Greet"}]},
    })
    checks = configs["checks"]
    # The method's grader stays on its own checks rather than grading the whole evaluation.
    assert "llm_provider_id" not in checks
    own, rule = checks["checks"]
    assert "llm_provider_id" not in own
    assert rule["llm_provider_id"] == "judge"

    # Own checks that no AI grades are not moved by it, so the one grader still grades the evaluation.
    _, configs, _ = converted_evaluation(["checks", "llm_judge"], {
        "checks": {"checks": [{"id": "own", "kind": "reply_mentions", "text": "refund"}]},
        "llm_judge": {"llm_provider_id": "judge", "rules": [{"rubric": "Greet"}]},
    })
    assert configs["checks"]["llm_provider_id"] == "judge"


def test_an_only_rule_keeps_at_least_one_call():
    conversion = convert_methods(["tool_used"], {"tool_used": {"rules": [
        {"id": "r", "tool_ids": ["tool-1"], "operator": "only", "min_calls": 1},
    ]}}, CATALOG)
    assert conversion.checks[0]["min_calls"] == 1


def test_a_rule_whose_shape_cannot_be_read_does_not_stop_the_others():
    conversion = convert_methods(["tool_used", "contains"], {"tool_used": {"tool": ["a", "b"], "result_not_empty": True}})
    assert [check["kind"] for check in conversion.checks] == ["reply_matches"]
    assert conversion.left_out == ["Tool Usage: a rule that could not be read."]


def test_a_setting_that_cannot_become_a_check_says_why():
    conversion = convert_methods(["tool_used"], {"tool_used": {"rules": [
        {"id": "r1", "tool_ids": ["tool-1"], "operator": "all", "max_calls": 0},
    ]}}, CATALOG)
    assert conversion.checks == []
    assert conversion.left_out == [
        'Tool Usage: a rule on "save_region" could not become a check'
        " (a tool that should be called at most 0 times can never pass)."
    ]


def test_an_empty_check_on_one_tool_is_the_same_as_none():
    conversion = convert_methods(["tool_used"], {"tool_used": {"rules": [
        {"id": "r1", "tool_ids": ["tool-1", "tool-2"], "operator": "any", "per_tool": {"tool-1": {}}},
    ]}}, CATALOG)
    assert sentences(conversion) == ['On every turn, one of the tools "save_region" or "change_mode" should be called.']
    assert conversion.left_out == []


def test_a_label_on_several_routers_or_steps_stays_a_name():
    catalog = {
        **CATALOG,
        "routers": [*CATALOG["routers"], {"id": "router-2", "label": "Mode", "branches": [{"value": "case-c", "label": "Refund"}]}],
        "action_nodes": [*CATALOG["action_nodes"], {"id": "step-3", "label": "Log", "type": "logNode"}],
    }
    conversion = convert_methods(["route_taken", "action_taken"], {
        "route_taken": {"rules": [{"id": "r", "router": "Mode", "expected": "Refund"}]},
        "action_taken": {"rules": [{"id": "a", "node": "Log", "should_fire": True}]},
    }, catalog)
    route, step = conversion.checks
    assert (route["router"], route.get("router_name")) == ("Mode", None)
    assert (step["step"], step["step_name"]) == ("Log", "Log")
