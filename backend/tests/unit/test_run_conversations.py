from datetime import datetime, timedelta
from types import SimpleNamespace

from app.services.run_conversations import (
    FAILED,
    NOT_EVALUATED,
    PASSED,
    StoredResult,
    as_text,
    build_run_outcome,
    message_of,
    reply_of,
    turn_reason,
    turn_verdict,
)

T0 = datetime(2026, 10, 1)


def _case(case_id, conversation=None, turn_index=None, *, minutes=0, message="Hi", expected=None, deleted=0):
    return SimpleNamespace(
        id=case_id,
        source_conversation_id=conversation,
        turn_index=turn_index,
        created_at=T0 + timedelta(minutes=minutes),
        input_data={"message": message},
        expected_output=expected,
        is_deleted=deleted,
    )


def _rule(status, *, case_id=None, conversation=None, scope="turn", comment=None, error=False):
    return SimpleNamespace(
        case_id=case_id,
        source_conversation_id=conversation,
        scope=scope,
        status=status,
        details={**({"comment": comment} if comment else {}), **({"error": True} if error else {})},
    )


def _metric(passed, **extra):
    return {"score": 1.0 if passed else 0.0, "passed": passed, **extra}


class TestTurnVerdict:
    def test_a_crash_fails_the_turn(self):
        assert turn_verdict("execution_failed", None, []) == FAILED

    def test_a_failed_check_fails_the_turn(self):
        assert turn_verdict("scored", {"contains": _metric(True)}, ["passed", "failed"]) == FAILED

    def test_a_turn_that_did_not_run_or_could_not_be_graded_is_not_evaluated(self):
        assert turn_verdict("skipped", None, ["passed"]) == NOT_EVALUATED
        assert turn_verdict("scoring_failed", None, []) == NOT_EVALUATED

    def test_a_failed_method_fails_the_turn(self):
        assert turn_verdict("scored", {"contains": _metric(True), "exact_match": _metric(False)}, []) == FAILED

    def test_methods_that_all_pass_pass_the_turn(self):
        assert turn_verdict("scored", {"contains": _metric(True)}, []) == PASSED

    def test_a_broken_method_leaves_the_turn_ungraded_unless_another_failed(self):
        broken = {"score": None, "passed": False, "error": True}
        assert turn_verdict("scored", {"nli_eval": broken, "contains": _metric(True)}, []) == NOT_EVALUATED
        assert turn_verdict("scored", {"nli_eval": broken, "contains": _metric(False)}, []) == FAILED
        assert turn_verdict("scored", {"nli_eval": broken}, ["passed"]) == NOT_EVALUATED

    def test_methods_with_nothing_to_compare_do_not_grade(self):
        skipped = {"score": None, "passed": False, "not_evaluated": True}
        assert turn_verdict("scored", {"contains": skipped}, []) == NOT_EVALUATED
        assert turn_verdict("scored", {"contains": skipped}, ["passed"]) == PASSED

    def test_a_passed_check_passes_a_turn_no_method_graded(self):
        assert turn_verdict("scored", {}, ["passed", "not_evaluated"]) == PASSED
        assert turn_verdict("scored", None, ["not_evaluated"]) == NOT_EVALUATED

    def test_results_from_before_statuses_are_graded_by_their_metrics(self):
        assert turn_verdict(None, {"contains": _metric(False)}, []) == FAILED


class TestBuildRunOutcome:
    def test_turns_are_grouped_and_ordered_as_the_run_played_them(self):
        cases = [
            _case("c3", "conv-b", 0),
            _case("c2", "conv-a", 1),
            _case("c1", "conv-a", 0),
            _case("c4"),  # a hand-written turn is a conversation of its own
        ]
        results = [StoredResult(case_id=case.id, status="scored") for case in cases]

        outcome = build_run_outcome(cases, results, [])

        assert [c.key for c in outcome.conversations] == ["conv-a", "conv-b", "c4"]
        assert [(t.case.id, t.number) for t in outcome.conversations[0].turns] == [("c1", 1), ("c2", 2)]

    def test_conversations_come_back_in_the_order_the_runner_plays_them(self):
        from app.services.test_suite import _group_cases_into_conversations

        cases = [
            _case("c2", "conv-a", 0),  # a first turn added after the conversation's second
            _case("c1", "conv-a", 1),
            _case("c3", "conv-b", 0),
            _case("c0"),
        ]
        # The runner reads the dataset ordered by id and plays the conversations as it groups them.
        played = _group_cases_into_conversations(sorted(cases, key=lambda case: case.id))

        outcome = build_run_outcome(list(reversed(cases)), [], [])

        assert [[t.case.id for t in c.turns] for c in outcome.conversations] == [
            [case.id for case in group] for group in played
        ]
        assert [[t.case.id for t in c.turns] for c in outcome.conversations] == [["c0"], ["c2", "c1"], ["c3"]]

    def test_rows_sit_on_their_turn_or_conversation(self):
        cases = [_case("c1", "conv", 0), _case("c2", "conv", 1), _case("m1")]
        results = [StoredResult(case_id=case.id, status="scored") for case in cases]
        on_turn = _rule("passed", case_id="c2", scope="every_turn")
        on_conversation = _rule("passed", conversation="conv", scope="conversation")
        on_manual = _rule("passed", case_id="m1", scope="every_conversation")
        lost = _rule("not_evaluated", scope="conversation")

        outcome = build_run_outcome(cases, results, [on_turn, on_conversation, on_manual, lost])

        conv, manual = outcome.conversations
        assert conv.turns[1].rules == [on_turn]
        assert conv.rules == [on_conversation]
        assert manual.rules == [on_manual] and manual.turns[0].rules == []
        assert outcome.unplaced == [lost]

    def test_a_failed_turn_or_whole_conversation_check_fails_the_conversation(self):
        cases = [_case("c1", "a", 0), _case("c2", "b", 0)]
        results = [
            StoredResult(case_id="c1", status="scored", metrics={"contains": _metric(False)}),
            StoredResult(case_id="c2", status="scored", metrics={"contains": _metric(True)}),
        ]
        whole = _rule("failed", conversation="b", scope="every_conversation")

        outcome = build_run_outcome(cases, results, [whole])

        assert [c.verdict for c in outcome.conversations] == [FAILED, FAILED]

    def test_a_whole_conversation_check_fails_the_turns_it_names(self):
        cases = [_case("c1", "a", 0), _case("c2", "a", 1), _case("c3", "a", 2)]
        results = [StoredResult(case_id=case.id, status="scored") for case in cases]
        missed = _rule("failed", conversation="a", scope="every_conversation")
        missed.details = {"turns": [2, 3]}
        held = _rule("passed", conversation="a", scope="every_conversation")
        held.details = {"turns": [1]}

        outcome = build_run_outcome(cases, results, [missed, held])

        assert [turn.verdict for turn in outcome.conversations[0].turns] == [NOT_EVALUATED, FAILED, FAILED]

    def test_a_half_run_is_not_a_pass(self):
        cases = [_case("c1", "a", 0), _case("c2", "a", 1)]
        results = [
            StoredResult(case_id="c1", status="scored", metrics={"contains": _metric(True)}),
            StoredResult(case_id="c2", status="skipped", error="Skipped: an earlier turn is waiting for human input"),
        ]

        (conversation,) = build_run_outcome(cases, results, []).conversations

        assert [turn.verdict for turn in conversation.turns] == [PASSED, NOT_EVALUATED]
        assert conversation.verdict == NOT_EVALUATED

    def test_a_crashed_turn_fails_its_conversation(self):
        cases = [_case("c1", "a", 0), _case("c2", "a", 1)]
        results = [
            StoredResult(case_id="c1", status="execution_failed", error="Execution failed: boom"),
            StoredResult(case_id="c2", status="skipped", error="Skipped: an earlier turn was not persisted to memory"),
        ]

        (conversation,) = build_run_outcome(cases, results, []).conversations

        assert conversation.verdict == FAILED

    def test_turns_nothing_checks_do_not_stop_a_pass(self):
        cases = [_case("c1", "a", 0), _case("c2", "a", 1)]
        results = [
            StoredResult(case_id="c1", status="scored", metrics={}),
            StoredResult(case_id="c2", status="scored", metrics={}),
        ]
        whole = _rule("passed", conversation="a", scope="conversation")

        (conversation,) = build_run_outcome(cases, results, [whole]).conversations

        assert [turn.verdict for turn in conversation.turns] == [NOT_EVALUATED, NOT_EVALUATED]
        assert conversation.verdict == PASSED

    def test_counts(self):
        cases = [_case("c1", "a", 0), _case("c2", "b", 0), _case("c3", "c", 0)]
        results = [
            StoredResult(case_id="c1", status="scored", metrics={"contains": _metric(True)}),
            StoredResult(case_id="c2", status="scored", metrics={"contains": _metric(False)}),
            StoredResult(case_id="c3", status="scored", metrics={}),
        ]

        outcome = build_run_outcome(cases, results, [])

        assert outcome.counts() == {"total": 3, "passed": 1, "failed": 1, "not_evaluated": 1}

    def test_a_turn_its_methods_could_not_grade_keeps_the_conversation_from_passing(self):
        cases = [_case("c1", "a", 0), _case("c2", "a", 1)]
        results = [
            StoredResult(case_id="c1", status="scored", metrics={"contains": _metric(True)}),
            StoredResult(case_id="c2", status="scoring_failed", error="Scoring failed: boom"),
        ]

        (conversation,) = build_run_outcome(cases, results, []).conversations

        assert conversation.turns[1].verdict == NOT_EVALUATED
        assert conversation.verdict == NOT_EVALUATED

    def test_checks_grade_a_turn_whose_result_could_not_be_stored(self):
        cases = [_case("c1", "a", 0), _case("c2", "a", 1)]
        results = [
            StoredResult(case_id="c1", status="scored", metrics={}),
            StoredResult(case_id="c2", status="scoring_failed", error="Scoring failed: boom"),
        ]
        rules = [_rule(PASSED, conversation="a", scope="every_conversation")]

        (conversation,) = build_run_outcome(cases, results, rules, methods=False).conversations

        assert conversation.verdict == PASSED

    def test_a_method_that_broke_on_one_turn_keeps_the_conversation_from_passing(self):
        cases = [_case("c1", "a", 0), _case("c2", "a", 1)]
        broken = {"key": "llm_judge", "score": None, "passed": False, "error": True}
        results = [
            StoredResult(case_id="c1", status="scored", metrics={"contains": _metric(True)}),
            StoredResult(case_id="c2", status="scored", metrics={"contains": _metric(True), "llm_judge": broken}),
        ]

        (conversation,) = build_run_outcome(cases, results, []).conversations

        assert [turn.verdict for turn in conversation.turns] == [PASSED, NOT_EVALUATED]
        assert conversation.verdict == NOT_EVALUATED

    def test_a_check_the_grader_could_not_grade_keeps_the_conversation_from_passing(self):
        cases = [_case("c1")]
        results = [StoredResult(case_id="c1", status="scored", metrics={})]
        rules = [
            _rule(PASSED, conversation="c1", scope="every_conversation"),
            _rule(NOT_EVALUATED, conversation="c1", scope="every_conversation", error=True),
        ]

        (conversation,) = build_run_outcome(cases, results, rules, methods=False).conversations

        assert conversation.verdict == NOT_EVALUATED

    def test_an_old_result_without_a_status_or_metrics_did_not_provably_run(self):
        cases = [_case("c1", "a", 0), _case("c2", "a", 1)]
        results = [
            StoredResult(case_id="c1", status="scored", metrics={"contains": _metric(True)}),
            StoredResult(case_id="c2", status=None, error="Execution failed: boom"),
        ]

        (conversation,) = build_run_outcome(cases, results, []).conversations

        assert conversation.verdict == NOT_EVALUATED
        assert turn_reason(conversation.turns[1]) == "Execution failed: boom"

    def test_every_placement_of_a_rule_row(self):
        cases = [_case("c1", "conv", 0), _case("c2", "conv", 1), _case("m1")]
        results = [StoredResult(case_id=case.id, status="scored") for case in cases]
        found = _rule("passed", case_id="c2", scope="specific_turn")
        missing = _rule("not_evaluated", scope="specific_turn", comment="Turn 3 is no longer in the dataset.")
        manual_conversation = _rule("failed", case_id="m1", scope="conversation")
        lost_turn = _rule("not_evaluated", conversation="conv", scope="turn", comment="The turn is gone.")

        outcome = build_run_outcome(cases, results, [found, missing, manual_conversation, lost_turn])

        conv, manual = outcome.conversations
        assert conv.turns[1].rules == [found]
        assert conv.rules == [lost_turn]
        assert manual.rules == [manual_conversation] and manual.verdict == FAILED
        assert outcome.unplaced == [missing]

    def test_a_turn_with_no_result_is_not_evaluated(self):
        (conversation,) = build_run_outcome([_case("c1", "a", 0)], [], []).conversations
        assert conversation.turns[0].verdict == NOT_EVALUATED
        assert conversation.verdict == NOT_EVALUATED


class TestTurnReason:
    def _turn(self, result, rules=()):
        cases = [_case("c1")]
        (conversation,) = build_run_outcome(cases, [result] if result else [], list(rules)).conversations
        return conversation.turns[0]

    def test_a_crash_says_what_broke(self):
        turn = self._turn(StoredResult(case_id="c1", status="execution_failed", error="Execution failed: boom"))
        assert turn_reason(turn) == "Execution failed: boom"

    def test_a_skipped_turn_says_why_in_plain_words(self):
        turn = self._turn(StoredResult(
            case_id="c1", status="skipped", error="Skipped: an earlier turn is waiting for human input"))
        assert turn_reason(turn) == "This turn did not run because the conversation was waiting for a person."

    def test_a_turn_that_could_not_be_graded(self):
        turn = self._turn(StoredResult(case_id="c1", status="scoring_failed", error="Scoring failed: KeyError"))
        assert turn_reason(turn) == "The turn ran, but it could not be graded."

    def test_a_not_evaluated_turn_gives_the_method_or_check_reason(self):
        skipped = {"score": None, "passed": False, "not_evaluated": True,
                   "comment": "Not evaluated: this turn has no expected reply."}
        assert turn_reason(self._turn(StoredResult(case_id="c1", status="scored", metrics={"contains": skipped}))) == (
            "Not evaluated: this turn has no expected reply."
        )
        rule = _rule("not_evaluated", case_id="c1", comment="The AI grader ran out of time for this run.")
        assert turn_reason(self._turn(StoredResult(case_id="c1", status="scored", metrics={}), [rule])) == (
            "The AI grader ran out of time for this run."
        )
        assert turn_reason(self._turn(StoredResult(case_id="c1", status="scored", metrics={}))) is None

    def test_a_graded_turn_needs_no_reason(self):
        turn = self._turn(StoredResult(case_id="c1", status="scored", metrics={"contains": _metric(False)}))
        assert turn_reason(turn) is None


class TestTexts:
    def test_stored_values_read_as_text(self):
        assert as_text({"value": " It's on its way. "}) == "It's on its way."
        assert as_text({"value": ""}) is None
        assert as_text({"order": 1}) == '{"order": 1}'
        assert as_text(None) is None

    def test_the_reply_is_what_live_chat_shows(self):
        assert reply_of({"message": "Hello", "steps": []}) == "Hello"
        assert reply_of({"value": "Hello"}) == "Hello"

    def test_the_message_is_what_the_run_sent(self):
        case = _case("c1", message="Edited later")
        assert message_of(case, "Hi there") == "Hi there"
        assert message_of(case, {"message": "Hi", "region": "uk"}) == "Hi"
        assert message_of(case, None) == "Edited later"
