"""How metrics become a verdict and a summary"""

from uuid import uuid4

import pytest

from app.schemas.prompt_editor import MAX_ACTUAL_CHARS, PromptEvalCaseResult
from app.services.prompt_editor import (
    TRUNCATION_MARKER,
    PromptUsageRef,
    _case_input_text,
    _case_outcome,
    _for_wire,
    _metric_outcome,
    _summarise,
    _usage_total,
)


def _metric(key="contains", **overrides):
    metric = {"key": key, "score": True, "passed": True, "comment": None}
    metric.update(overrides)
    return metric


def _row(status="scored", metrics=None, **overrides):
    payload = {
        "case_id": uuid4(),
        "status": status,
        "metrics": metrics or {},
        **(_case_outcome(metrics) if metrics is not None else {}),
    }
    payload.update(overrides)
    return PromptEvalCaseResult(**payload)


class TestMetricOutcome:
    def test_our_own_gap_marker_wins_over_the_registry_flags(self):
        assert _metric_outcome({"not_applicable": True, "error": True, "score": None}) == "not_applicable"

    def test_an_errored_metric_is_not_a_zero(self):
        assert _metric_outcome({"error": True, "score": None}) == "errored"

    def test_a_not_evaluated_metric_is_its_own_outcome(self):
        assert _metric_outcome({"not_evaluated": True, "score": None}) == "not_evaluated"

    def test_a_scoreless_metric_with_neither_flag_is_errored(self):
        assert _metric_outcome({"key": "contains", "score": None, "passed": False}) == "errored"

    @pytest.mark.parametrize("score", [True, False, 0.0, 1.0, 0.42])
    def test_a_real_number_or_boolean_is_scored(self, score):
        assert _metric_outcome({"score": score, "passed": bool(score)}) == "scored"


class TestCaseOutcome:
    def test_one_expectation_mismatch_reads_failed(self):
        outcome = _case_outcome({"contains": _metric(score=False, passed=False)})

        assert outcome["verdict"] == "failed"
        assert (outcome["failed_metrics"], outcome["scored_metrics"]) == (1, 1)
        assert outcome["passed"] is False

    def test_a_case_whose_only_metric_errored_is_inconclusive(self):
        outcome = _case_outcome({"nli_eval": _metric("nli_eval", score=None, passed=False, error=True)})

        assert outcome["verdict"] == "inconclusive"
        assert outcome["failed_metrics"] == 0
        assert outcome["errored_metrics"] == 1

    def test_a_scored_pass_beside_a_not_evaluated_metric_is_inconclusive(self):
        outcome = _case_outcome(
            {
                "contains": _metric(),
                "nli_eval": _metric("nli_eval", score=None, passed=False, not_evaluated=True),
            }
        )

        assert outcome["verdict"] == "inconclusive"

    def test_an_inapplicable_check_beside_a_passing_one_still_reads_passed(self):
        outcome = _case_outcome(
            {
                "not_contains": _metric("not_contains"),
                "contains": {"key": "contains", "score": None, "passed": False, "not_applicable": True},
            }
        )

        assert outcome["verdict"] == "passed"
        assert outcome["passed"] is True
        assert outcome["not_applicable_metrics"] == 1

    def test_a_case_where_nothing_was_applicable_is_inconclusive(self):
        outcome = _case_outcome(
            {"contains": {"key": "contains", "score": None, "passed": False, "not_applicable": True}}
        )

        assert outcome["verdict"] == "inconclusive"
        assert outcome["case_score"] is None

    def test_booleans_average_as_one_and_zero(self):
        outcome = _case_outcome({"a": _metric("a", score=True), "b": _metric("b", score=False, passed=False)})

        assert outcome["case_score"] == 0.5


class TestSummarise:
    def test_the_six_outcome_counts_sum_to_total(self):
        rows = [
            _row(metrics={"contains": _metric()}),
            _row(metrics={"contains": _metric(score=False, passed=False)}),
            _row(metrics={"contains": _metric(score=None, passed=False, error=True)}),
            _row(status="execution_failed"),
            _row(status="scoring_failed"),
            _row(status="skipped"),
        ]

        summary = _summarise(rows)

        assert summary.total == 6
        counted = (
            summary.passed
            + summary.failed
            + summary.inconclusive
            + summary.execution_failed
            + summary.scoring_failed
            + summary.skipped
        )
        assert counted == summary.total

    def test_scored_is_the_denominator_and_excludes_metric_less_cases(self):
        rows = [
            _row(metrics={"contains": _metric(score=1.0)}),
            _row(metrics={"contains": _metric(score=0.0, passed=False)}),
            _row(status="execution_failed"),
        ]

        summary = _summarise(rows)

        assert summary.scored == 2
        assert summary.avg_score == 0.5

    def test_a_run_that_scored_nothing_reports_no_average(self):
        summary = _summarise([_row(status="skipped"), _row(status="execution_failed")])

        assert summary.scored == 0
        assert summary.avg_score is None
        assert summary.total == 2


class TestWireHelpers:
    def test_a_long_value_is_cut_so_the_marker_fits_inside_the_bound(self):
        # Cutting to the bound and then appending would breach the response model's
        # max_length, which Pydantic raises at construction.
        cut = _for_wire("x" * (MAX_ACTUAL_CHARS + 5_000))

        assert len(cut) == MAX_ACTUAL_CHARS
        assert cut.endswith(TRUNCATION_MARKER)

    def test_a_value_at_the_bound_is_untouched(self):
        assert _for_wire("x" * MAX_ACTUAL_CHARS) == "x" * MAX_ACTUAL_CHARS

    def test_a_case_without_a_message_key_falls_back_to_the_whole_payload(self):
        assert _case_input_text({"prompt": "hi"}) == "{'prompt': 'hi'}"
        assert _case_input_text({"message": "hi"}) == "hi"
        assert _case_input_text("raw") == "raw"


class TestUsageTotal:
    def test_a_response_without_usage_is_counted_not_dropped(self):
        ref = PromptUsageRef(execution_id="e")
        ref.entries = [
            {"usage": {"input_tokens": 3, "output_tokens": 4, "total_tokens": 7}},
            {"usage": None},
        ]

        assert _usage_total(ref) == {
            "input_tokens": 3,
            "output_tokens": 4,
            "total_tokens": 7,
            "responses_without_usage": 1,
        }
