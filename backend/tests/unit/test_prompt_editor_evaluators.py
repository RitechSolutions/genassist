"""The prompt check's capability boundary: which techniques it accepts, and the
exact configuration each one is allowed to hand the evaluator registry"""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.exceptions.exception_handler import _response_error_detail
from app.schemas.prompt_editor import (
    MAX_JUDGE_RUBRIC_CHARS,
    FieldEqualsConfig,
    JudgeRule,
    LlmJudgeConfig,
    NliEvalConfig,
    NotContainsConfig,
    PromptEvalRequest,
    PromptTechniqueConfigs,
)
from app.services.prompt_editor_evaluators import (
    _EXPECTATION_RULES,
    PROMPT_CHECK_TECHNIQUES,
    build_technique_configs,
    describe_expectations,
    validate_prompt_check_techniques,
)


def _configs(**overrides) -> PromptTechniqueConfigs:
    return PromptTechniqueConfigs(**overrides)


def _request(**overrides) -> PromptEvalRequest:
    payload = {"prompt_content": "p", "provider_id": uuid4(), "techniques": ["contains"]}
    payload.update(overrides)
    return PromptEvalRequest(**payload)


class TestValidatePromptCheckTechniques:
    @pytest.mark.parametrize("technique", ["no_errors", "tool_used", "route_taken", "action_taken"])
    def test_a_trace_technique_is_rejected(self, technique):
        with pytest.raises(AppException) as exc_info:
            validate_prompt_check_techniques([technique], _configs())

        assert exc_info.value.status_code == 400
        assert exc_info.value.error_key is ErrorKey.PROMPT_EVAL_TECHNIQUE_UNSUPPORTED
        assert "execution trace" in exc_info.value.error_detail

    @pytest.mark.parametrize("technique", ["provenance_eval"])
    def test_deferred_techniques_are_rejected_until_d9(self, technique):
        with pytest.raises(AppException) as exc_info:
            validate_prompt_check_techniques([technique], _configs())

        assert exc_info.value.status_code == 400
        assert exc_info.value.error_key is ErrorKey.PROMPT_EVAL_TECHNIQUE_UNSUPPORTED
        assert exc_info.value.error_detail == f"'{technique}' is not available in prompt checks yet."

    def test_an_unknown_technique_is_rejected_rather_than_silently_skipped(self):
        with pytest.raises(AppException) as exc_info:
            validate_prompt_check_techniques(["exact_match", "bogus"], _configs())

        assert exc_info.value.error_key is ErrorKey.PROMPT_EVAL_TECHNIQUE_UNSUPPORTED
        assert "bogus" in exc_info.value.error_detail
        assert "not available in prompt checks yet" not in exc_info.value.error_detail

    def test_a_config_for_an_unselected_technique_is_rejected_with_the_key_named(self):
        with pytest.raises(AppException) as exc_info:
            validate_prompt_check_techniques(
                ["contains"], _configs(not_contains={"phrases": ["refund"]})
            )

        assert exc_info.value.status_code == 400
        assert "not_contains" in exc_info.value.error_detail

    def test_the_judge_receives_its_rule_and_the_checks_own_provider(self):
        provider_id = uuid4()
        built = validate_prompt_check_techniques(
            ["llm_judge"],
            _configs(
                llm_judge={"rules": [{"rubric": "  grade it  ", "min_score": 0.7, "source_type": "expected_output"}]}
            ),
            judge_provider_id=provider_id,
        )

        assert built["llm_judge"] == {
            "rules": [{"rubric": "grade it", "min_score": 0.7, "source_type": "expected_output"}],
            "llm_provider_id": str(provider_id),
        }

    def test_the_rewrite_builds_the_judge_config_without_a_provider(self):
        built = build_technique_configs(["llm_judge"], _configs(llm_judge={"rules": [{"rubric": "grade it"}]}))

        assert built["llm_judge"] == {"rules": [{"rubric": "grade it", "min_score": 0.5, "source_type": "none"}]}

    @pytest.mark.parametrize("build", [validate_prompt_check_techniques, build_technique_configs])
    def test_a_judge_with_no_rubric_is_refused_on_both_routes(self, build):
        with pytest.raises(AppException) as exc_info:
            build(["contains", "llm_judge"], _configs())

        assert exc_info.value.status_code == 400
        assert "rubric" in exc_info.value.error_detail

    def test_a_judge_config_sent_for_an_unselected_judge_is_rejected(self):
        with pytest.raises(AppException) as exc_info:
            validate_prompt_check_techniques(["contains"], _configs(llm_judge={"rules": [{"rubric": "grade it"}]}))

        assert exc_info.value.status_code == 400
        assert "llm_judge" in exc_info.value.error_detail

    def test_the_expectation_based_techniques_receive_an_empty_config(self):
        built = validate_prompt_check_techniques(
            ["exact_match", "contains", "json_match"], _configs()
        )

        assert built == {"exact_match": {}, "contains": {}, "json_match": {}}

    def test_nli_eval_receives_a_fixed_evidence_source(self):
        built = validate_prompt_check_techniques(["nli_eval"], _configs())

        assert built["nli_eval"] == {"evidence_source": "expected_output"}

    def test_not_contains_without_phrases_is_rejected(self):
        with pytest.raises(AppException) as exc_info:
            validate_prompt_check_techniques(["contains", "not_contains"], _configs())

        assert exc_info.value.status_code == 400
        assert exc_info.value.error_key is ErrorKey.PROMPT_EVAL_TECHNIQUE_UNSUPPORTED
        assert "forbidden phrase" in exc_info.value.error_detail

    def test_field_equals_without_a_config_is_still_allowed(self):
        assert validate_prompt_check_techniques(["field_equals"], _configs()) == {"field_equals": {}}

    def test_not_contains_receives_only_the_phrases_key(self):
        built = validate_prompt_check_techniques(
            ["not_contains"], _configs(not_contains={"phrases": ["  refund  ", "chargeback"]})
        )

        assert built["not_contains"] == {"phrases": ["refund", "chargeback"]}

    def test_field_equals_without_an_expected_omits_the_key(self):
        built = validate_prompt_check_techniques(
            ["field_equals"], _configs(field_equals={"field": "outputs"})
        )

        assert built["field_equals"] == {"field": "outputs"}

    def test_field_equals_with_an_expected_carries_it(self):
        built = validate_prompt_check_techniques(
            ["field_equals"], _configs(field_equals={"field": "inputs.message", "expected": "hi"})
        )

        assert built["field_equals"] == {"field": "inputs.message", "expected": "hi"}


class TestLenientBuilder:

    def test_not_contains_without_phrases_builds_an_empty_config(self):
        assert build_technique_configs(["not_contains"], _configs()) == {"not_contains": {}}

    def test_the_check_still_refuses_what_the_builder_allows(self):
        with pytest.raises(AppException) as exc_info:
            validate_prompt_check_techniques(["not_contains"], _configs())

        assert exc_info.value.error_detail == (
            "'not_contains' needs at least one forbidden phrase. Add one or clear the check."
        )

    def test_a_configured_not_contains_builds_the_same_config_either_way(self):
        configs = _configs(not_contains={"phrases": ["refund"]})

        assert build_technique_configs(["not_contains"], configs) == validate_prompt_check_techniques(
            ["not_contains"], configs
        )


class TestRejectionDetailReachesTheUser:
    def test_the_technique_detail_survives_outside_dev(self, monkeypatch):
        monkeypatch.delenv("ENV", raising=False)
        with pytest.raises(AppException) as exc_info:
            validate_prompt_check_techniques(["tool_used"], _configs())

        assert _response_error_detail(exc_info.value) == exc_info.value.error_detail

    def test_a_key_outside_the_safe_set_still_withholds_its_detail(self, monkeypatch):
        monkeypatch.delenv("ENV", raising=False)
        error = AppException(
            status_code=502,
            error_key=ErrorKey.PROMPT_MODEL_CALL_FAILED,
            error_detail="internal provider wiring",
        )

        assert _response_error_detail(error) is None


class TestTechniqueConfigContract:
    @pytest.mark.parametrize("key", ["provenance_eval"])
    def test_a_deferred_evaluator_has_no_config_model_at_all(self, key):
        with pytest.raises(ValidationError) as exc_info:
            PromptTechniqueConfigs(**{key: {}})

        assert exc_info.value.errors()[0]["type"] == "extra_forbidden"

    def test_nli_eval_config_carries_a_threshold_and_nothing_else(self):
        assert set(NliEvalConfig.model_fields) == {"min_entail_score"}

        with pytest.raises(ValidationError) as exc_info:
            PromptTechniqueConfigs(nli_eval={"min_entail_score": 0.5, "nli_model_name": "attacker/model"})

        assert exc_info.value.errors()[0]["type"] == "extra_forbidden"

    @pytest.mark.parametrize("score", [-0.1, 1.1])
    def test_an_out_of_range_entail_score_is_rejected(self, score):
        with pytest.raises(ValidationError):
            NliEvalConfig(min_entail_score=score)

    def test_a_judge_rule_carries_a_rubric_a_threshold_and_a_source_and_nothing_else(self):
        assert set(JudgeRule.model_fields) == {"rubric", "min_score", "source_type"}

        with pytest.raises(ValidationError) as exc_info:
            PromptTechniqueConfigs(llm_judge={"rules": [{"rubric": "grade it", "source_field": "trace.x"}]})

        assert exc_info.value.errors()[0]["type"] == "extra_forbidden"

    @pytest.mark.parametrize("key", ["label", "source_field", "llm_provider_id", "answer_field", "question_field"])
    def test_a_registry_selector_cannot_ride_along_on_a_judge_rule(self, key):
        with pytest.raises(ValidationError) as exc_info:
            JudgeRule(rubric="grade it", **{key: "anything"})

        assert exc_info.value.errors()[0]["type"] == "extra_forbidden"

    def test_the_judge_config_cannot_choose_its_own_provider(self):
        with pytest.raises(ValidationError) as exc_info:
            LlmJudgeConfig(rules=[{"rubric": "grade it"}], llm_provider_id=str(uuid4()))

        assert exc_info.value.errors()[0]["type"] == "extra_forbidden"

    @pytest.mark.parametrize("rules, error", [([], "too_short"), ([{"rubric": "a"}, {"rubric": "b"}], "too_long")])
    def test_the_judge_grades_exactly_one_rule(self, rules, error):
        with pytest.raises(ValidationError) as exc_info:
            LlmJudgeConfig(rules=rules)

        assert exc_info.value.errors()[0]["type"] == error

    @pytest.mark.parametrize("rubric", ["", "   ", "x" * (MAX_JUDGE_RUBRIC_CHARS + 1)])
    def test_a_rubric_the_judge_could_not_grade_with_is_rejected(self, rubric):
        with pytest.raises(ValidationError):
            JudgeRule(rubric=rubric)

    def test_a_rubric_at_the_bound_is_accepted_and_stripped(self):
        rule = JudgeRule(rubric=f"  {'x' * MAX_JUDGE_RUBRIC_CHARS}  ")

        assert rule.rubric == "x" * MAX_JUDGE_RUBRIC_CHARS

    def test_a_rule_grades_the_rubric_alone_until_a_source_is_chosen(self):
        rule = JudgeRule(rubric="grade it")

        assert (rule.source_type, rule.min_score) == ("none", 0.5)

    def test_a_source_the_editor_does_not_offer_is_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            JudgeRule(rubric="grade it", source_type="output")

        assert exc_info.value.errors()[0]["type"] == "literal_error"

    @pytest.mark.parametrize("score", [-0.1, 1.1])
    def test_an_out_of_range_judge_threshold_is_rejected(self, score):
        with pytest.raises(ValidationError):
            JudgeRule(rubric="grade it", min_score=score)

    @pytest.mark.parametrize("key", ["nli_model_name", "evidence_source", "answer_field"])
    def test_a_registry_option_cannot_ride_along_on_a_config_that_does_exist(self, key):
        with pytest.raises(ValidationError) as exc_info:
            NotContainsConfig(phrases=["a"], **{key: "anything"})

        assert exc_info.value.errors()[0]["type"] == "extra_forbidden"

    def test_a_fifty_first_phrase_is_rejected(self):
        with pytest.raises(ValidationError):
            NotContainsConfig(phrases=[f"p{index}" for index in range(51)])

    def test_an_over_long_phrase_is_rejected(self):
        with pytest.raises(ValidationError):
            NotContainsConfig(phrases=["x" * 201])

    def test_a_blank_phrase_is_rejected(self):
        with pytest.raises(ValidationError):
            NotContainsConfig(phrases=["   "])

    def test_case_insensitive_duplicate_phrases_are_accepted(self):
        assert NotContainsConfig(phrases=["refund", "REFUND"]).phrases == ["refund", "REFUND"]

    @pytest.mark.parametrize("field", ["outputs.foo", "trace.output", "workflow", "_usage_ref"])
    def test_a_field_path_outside_the_readable_roots_is_rejected(self, field):
        with pytest.raises(ValidationError) as exc_info:
            FieldEqualsConfig(field=field, expected="x")

        assert exc_info.value.errors()[0]["type"] == "string_pattern_mismatch"

    @pytest.mark.parametrize("field", ["reference_outputs", "inputs", "reference_outputs.status"])
    def test_only_the_bare_outputs_field_may_omit_an_expected(self, field):
        with pytest.raises(ValidationError):
            FieldEqualsConfig(field=field)

    def test_bare_outputs_keeps_the_expectation_fallback(self):
        assert FieldEqualsConfig(field="outputs").expected is None

    def test_a_non_outputs_root_stays_reachable_with_an_expected(self):
        assert FieldEqualsConfig(field="reference_outputs", expected="x").field == "reference_outputs"

    @pytest.mark.parametrize("blank", ["", " ", "\t", " \n ", "\xa0"])
    def test_a_blank_or_whitespace_only_expected_is_rejected(self, blank):
        with pytest.raises(ValidationError):
            FieldEqualsConfig(field="inputs.x", expected=blank)

    def test_an_expected_is_stored_the_way_the_evaluator_grades_it(self):
        assert FieldEqualsConfig(field="inputs.x", expected="  hello  ").expected == "hello"

    def test_an_over_long_expected_is_rejected(self):
        assert len(FieldEqualsConfig(field="inputs.x", expected="a" * 2_000).expected) == 2_000
        with pytest.raises(ValidationError):
            FieldEqualsConfig(field="inputs.x", expected="a" * 2_001)


class TestPromptEvalRequestContract:
    def test_an_over_long_technique_id_is_rejected(self):
        assert len(_request(techniques=["x" * 64]).techniques[0]) == 64
        with pytest.raises(ValidationError) as exc_info:
            _request(techniques=["x" * 65])

        assert exc_info.value.errors()[0]["type"] == "string_too_long"

    def test_duplicate_techniques_are_rejected(self):
        with pytest.raises(ValidationError):
            _request(techniques=["contains", "contains"])

    def test_duplicate_case_ids_are_rejected(self):
        case_id = uuid4()
        with pytest.raises(ValidationError):
            _request(case_ids=[case_id, case_id])

    def test_an_empty_case_id_list_is_rejected_so_absent_means_server_picks(self):
        with pytest.raises(ValidationError):
            _request(case_ids=[])

    def test_techniques_are_required(self):
        with pytest.raises(ValidationError):
            PromptEvalRequest(prompt_content="p", provider_id=uuid4())

    def test_max_cases_defaults_to_ten_and_is_capped(self):
        assert _request().max_cases == 10
        with pytest.raises(ValidationError):
            _request(max_cases=26)


class TestExpectationRules:

    def test_a_new_technique_cannot_be_added_without_deciding_what_it_expects(self):
        assert set(_EXPECTATION_RULES) | {
            "not_contains",
            "field_equals",
            "llm_judge",
        } == set(PROMPT_CHECK_TECHNIQUES)

    def test_a_technique_with_no_settled_meaning_describes_nothing(self):
        assert describe_expectations(["not_contains", "field_equals"]) == ""
        assert describe_expectations(["llm_judge"]) == ""
        assert describe_expectations([]) == ""

    def test_contains_is_described_as_a_fragment_not_the_whole_reply(self):
        described = describe_expectations(["contains"])

        assert described.startswith("- contains: ")
        assert "not the whole reply" in described

    def test_the_order_techniques_were_toggled_in_does_not_change_the_text(self):
        assert describe_expectations(["nli_eval", "contains"]) == describe_expectations(
            ["contains", "nli_eval"]
        )

    def test_forbidden_phrases_are_described_from_the_built_config(self):
        described = describe_expectations(
            ["not_contains"], {"not_contains": {"phrases": ["refund", "chargeback"]}}
        )

        assert described == (
            "- not_contains: the reply must not contain any of these phrases, "
            'case-insensitively: "refund", "chargeback"'
        )

    def test_a_not_contains_with_no_phrases_describes_nothing(self):
        assert describe_expectations(["not_contains"], {"not_contains": {}}) == ""

    def test_field_equals_is_described_with_the_value_it_compares(self):
        described = describe_expectations(
            ["field_equals"], {"field_equals": {"field": "inputs.message", "expected": "hi"}}
        )

        assert described == "- field_equals: the reply field 'inputs.message' must equal \"hi\""

    def test_field_equals_without_an_expected_points_at_the_case(self):
        described = describe_expectations(["field_equals"], {"field_equals": {"field": "outputs"}})

        assert described == "- field_equals: the reply field 'outputs' must equal the expected output"

    def test_the_entailment_threshold_the_grader_runs_at_is_described(self):
        described = describe_expectations(
            ["nli_eval"], {"nli_eval": {"evidence_source": "expected_output", "min_entail_score": 0.2}}
        )

        assert described.startswith("- nli_eval: ")
        assert "per claim" in described
        assert "0.2 or higher" in described

    def test_an_nli_eval_without_a_threshold_keeps_the_settled_reading(self):
        assert describe_expectations(
            ["nli_eval"], {"nli_eval": {"evidence_source": "expected_output"}}
        ) == describe_expectations(["nli_eval"])

    def test_the_rubric_the_judge_runs_is_quoted_with_its_threshold(self):
        described = describe_expectations(
            ["llm_judge"],
            {"llm_judge": {"rules": [{"rubric": "Is it polite?", "min_score": 0.7}]}},
        )

        assert described == (
            "- llm_judge: an LLM judge scores the reply from 0 to 1 against this rubric "
            'and it passes at 0.7 or higher: "Is it polite?"'
        )

    def test_the_judges_source_is_described_only_once_it_is_chosen(self):
        with_source = describe_expectations(
            ["llm_judge"],
            {"llm_judge": {"rules": [{"rubric": "r", "source_type": "expected_output"}]}},
        )
        without = describe_expectations(
            ["llm_judge"], {"llm_judge": {"rules": [{"rubric": "r", "source_type": "none"}]}}
        )

        assert "shown to the judge as its source" in with_source
        assert "source" not in without

    def test_a_judge_with_no_rule_describes_nothing(self):
        assert describe_expectations(["llm_judge"], {"llm_judge": {}}) == ""
        assert describe_expectations(["llm_judge"], {"llm_judge": {"rules": []}}) == ""

    def test_configured_lines_keep_the_allow_list_order(self):
        described = describe_expectations(
            ["nli_eval", "not_contains", "contains"], {"not_contains": {"phrases": ["x"]}}
        )

        assert [line.split(":")[0] for line in described.splitlines()] == [
            "- contains",
            "- not_contains",
            "- nli_eval",
        ]
