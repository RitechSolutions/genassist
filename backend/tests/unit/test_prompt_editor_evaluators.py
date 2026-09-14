"""The prompt check's capability boundary: which techniques it accepts, and the
exact configuration each one is allowed to hand the evaluator registry"""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.exceptions.exception_handler import _response_error_detail
from app.schemas.prompt_editor import (
    FieldEqualsConfig,
    NotContainsConfig,
    PromptEvalRequest,
    PromptTechniqueConfigs,
)
from app.services.prompt_editor_evaluators import validate_prompt_check_techniques


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

    @pytest.mark.parametrize("technique", ["llm_judge", "provenance_eval"])
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
    @pytest.mark.parametrize("key", ["llm_judge", "provenance_eval"])
    def test_a_deferred_evaluator_has_no_config_model_at_all(self, key):
        with pytest.raises(ValidationError) as exc_info:
            PromptTechniqueConfigs(**{key: {}})

        assert exc_info.value.errors()[0]["type"] == "extra_forbidden"

    def test_nli_eval_has_no_config_object_to_carry_a_model_name(self):
        assert "nli_eval" not in PromptTechniqueConfigs.model_fields

        with pytest.raises(ValidationError) as exc_info:
            PromptTechniqueConfigs(nli_eval={"nli_model_name": "attacker/model"})

        assert exc_info.value.errors()[0]["type"] == "extra_forbidden"

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
