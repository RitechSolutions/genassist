"""Should / Should not checks: the model, sentences and grading, without a run."""
import asyncio
from unittest.mock import AsyncMock

import pytest

from app.services.scenario_checks import (
    UNREADABLE_TURN,
    Check,
    JudgeRequest,
    JudgeVerdict,
    Targets,
    TurnRecord,
    conversation_verdicts,
    describe_check,
    grade_checks,
    judge_expectation,
    judge_requests,
    parse_checks_config,
    resolve_targets,
    run_judge,
    same_value,
    skip_reason,
    tool_calls_from_events,
    transcript,
    turn_fact,
)

CATALOG = {
    "agents": [
        {"id": "agent-1", "label": "Refund agent", "tools": [
            {"id": "tool-1", "name": "save_region", "label": "Save region"},
            {"id": "tool-2", "name": "change_mode", "label": "Change mode"},
        ]},
    ],
    "routers": [{"id": "router-1", "label": "Is allowed?", "branches": [{"value": "true"}, {"value": "false"}]}],
    "action_nodes": [
        {"id": "step-1", "label": "Create ticket"},
        {"id": "step-2", "label": "Log"},
        {"id": "step-3", "label": "Log"},
    ],
}


def check(**fields) -> Check:
    return Check(**{"id": "c1", "kind": "reply_mentions", "text": "London", **fields})


def turn(case_id="t1", conversation="conv-a", position=0, **fields) -> TurnRecord:
    return TurnRecord(
        case_id=case_id,
        conversation_key=conversation,
        turn_index=position,
        position=position,
        message=fields.pop("message", f"message {position}"),
        **fields,
    )


def grade(checks, conversations, verdicts=None, catalog=CATALOG):
    targets = {item.id: resolve_targets(item, catalog) for item in checks}
    return grade_checks(checks, conversations, targets, verdicts or {})


class TestModel:
    def test_a_complete_config_parses(self):
        parsed = parse_checks_config({
            "checks": [
                {"id": "a", "kind": "reply_mentions", "text": "RingGo", "expect": "should_not"},
                {"id": "b", "kind": "tool_called", "tool_name": "save_region", "level": "turn", "case_id": "x"},
            ],
            "llm_provider_id": "p1",
        })
        assert [item.id for item in parsed.checks] == ["a", "b"]
        assert parsed.llm_provider_id == "p1"

    @pytest.mark.parametrize(
        "raw",
        [
            {"id": "a", "kind": "reply_mentions"},
            {"id": "a", "kind": "reply_meets", "rubric": "  "},
            {"id": "a", "kind": "route_taken", "router": "router-1"},
            {"id": "a", "kind": "state_equals", "key": "mode"},
            {"id": "a", "kind": "reply_mentions", "text": "x", "level": "turn"},
            {"id": "a", "kind": "reply_mentions", "text": "x", "level": "conversation"},
            {"id": "a", "kind": "made_up", "text": "x"},
        ],
    )
    def test_an_incomplete_check_is_refused(self, raw):
        with pytest.raises(ValueError):
            parse_checks_config({"checks": [raw]})

    def test_ids_must_be_unique(self):
        with pytest.raises(ValueError):
            parse_checks_config({"checks": [
                {"id": "a", "kind": "reply_mentions", "text": "x"},
                {"id": "a", "kind": "reply_mentions", "text": "y"},
            ]})

    def test_an_empty_state_value_is_a_value(self):
        assert check(kind="state_equals", key="mode", value="").value == ""

    def test_one_conversation_stored_the_older_way_is_chosen(self):
        assert check(level="conversation", conversation_id="a").conversation_ids == ["a"]
        merged = check(level="conversation", conversation_ids=["b", "b", " "], conversation_id="a")
        assert merged.conversation_ids == ["b", "a"]
        assert check(conversation_ids=["a"]).per_turn is False

    def test_chosen_conversations_can_hold_on_every_turn(self):
        assert check(level="conversation", conversation_ids=["a"], when="every_turn").per_turn is True
        assert check(level="conversation", conversation_ids=["a"]).per_turn is False


class TestSentences:
    @pytest.mark.parametrize(
        "fields, sentence",
        [
            ({"level": "turn", "case_id": "x"}, 'The reply should mention "London".'),
            ({"level": "turn", "case_id": "x", "expect": "should_not"}, 'The reply should not mention "London".'),
            ({"level": "conversation", "conversation_id": "a"}, 'At some point, the reply should mention "London".'),
            ({"level": "conversation", "conversation_id": "a", "expect": "should_not"},
             'The reply should never mention "London".'),
            ({"level": "conversation", "conversation_ids": ["a", "b"], "when": "every_turn"},
             'On every turn, the reply should mention "London".'),
            ({"level": "conversation", "conversation_ids": ["a"], "when": "every_turn", "expect": "should_not"},
             'On every turn, the reply should not mention "London".'),
            ({}, 'In every conversation, at some point, the reply should mention "London".'),
            ({"expect": "should_not"}, 'In every conversation, the reply should never mention "London".'),
            ({"when": "every_turn"}, 'On every turn, the reply should mention "London".'),
        ],
    )
    def test_levels_read_as_sentences(self, fields, sentence):
        assert describe_check(check(**fields)) == sentence

    def test_each_kind_reads_as_a_sentence(self):
        turn_level = {"level": "turn", "case_id": "x"}
        assert describe_check(check(kind="tool_called", tool_name="save_region", agent_name="Refund agent",
                                    args={"region": "united-kingdom"}, **turn_level)) == (
            'The tool "save_region" should be called by "Refund agent" with region = united-kingdom.'
        )
        assert describe_check(check(kind="step_runs", step_name="Create ticket", expect="should_not", **turn_level)) == (
            'The step "Create ticket" should not run.'
        )
        assert describe_check(check(kind="route_taken", router_name="Is allowed?", branch="true", **turn_level)) == (
            'The router "Is allowed?" should take "true".'
        )
        assert describe_check(check(kind="state_equals", key="conversation_mode", value="refund", **turn_level)) == (
            'The remembered value "conversation_mode" should be "refund".'
        )
        assert describe_check(check(kind="reply_meets", rubric="List all five regions", **turn_level)) == (
            'The reply should do this: "List all five regions".'
        )
        assert describe_check(check(kind="reply_meets", rubric="Give a phone number", expect="should_not")) == (
            'In every conversation, the agent should never do this: "Give a phone number".'
        )


class TestOneTurn:
    def test_reply_mentions_ignores_case(self):
        assert turn_fact(check(), Targets(), turn(reply="You are in london."))[0] is True
        holds, fact = turn_fact(check(), Targets(), turn(reply="Hello"))
        assert holds is False and fact == 'The reply did not mention "London".'

    def test_a_turn_waiting_for_a_person_cannot_say(self):
        assert turn_fact(check(), Targets(), turn(waiting_for_human=True))[0] is None

    def test_a_tool_call_matches_its_values_with_the_real_arguments(self):
        calls = tool_calls_from_events(
            [{"event_id": "e1", "tool_id": "tool-1", "tool_name": "save_region", "agent_id": "agent-1",
              "arguments": {"email": "[EMAIL]"}, "status": "succeeded"}],
            raw_arguments={"e1": {"email": "Ana@Example.com", "count": 2}},
        )
        item = check(kind="tool_called", tool="tool-1", args={"email": "Ana@Example.com", "count": "2.0"})
        assert turn_fact(item, resolve_targets(item, CATALOG), turn(tool_calls=calls))[0] is True
        # Text compares with its case, as Tool Usage compared it.
        lower = check(kind="tool_called", tool="tool-1", args={"email": "ana@example.com"})
        assert turn_fact(lower, resolve_targets(lower, CATALOG), turn(tool_calls=calls))[0] is False

    def test_a_call_with_other_values_shows_the_stored_ones(self):
        calls = tool_calls_from_events([{"event_id": "e1", "tool_id": "tool-1", "tool_name": "save_region",
                                         "arguments": {"region": "scotland"}, "status": "succeeded"}])
        item = check(kind="tool_called", tool="tool-1", args={"region": "united-kingdom"})
        holds, fact = turn_fact(item, resolve_targets(item, CATALOG), turn(tool_calls=calls))
        assert holds is False and fact == "save_region was called with region = scotland."

    def test_a_refused_call_is_not_a_call_but_is_an_attempt(self):
        calls = tool_calls_from_events([{"event_id": "e1", "tool_id": "tool-1", "tool_name": "save_region",
                                         "status": "failed",
                                         "error": "required parameters are missing or empty: region"}])
        should = check(kind="tool_called", tool="tool-1")
        should_not = check(kind="tool_called", tool="tool-1", expect="should_not")
        assert turn_fact(should, resolve_targets(should, CATALOG), turn(tool_calls=calls))[0] is False
        assert turn_fact(should_not, resolve_targets(should_not, CATALOG), turn(tool_calls=calls))[0] is True

    def test_a_refused_attempt_counts_only_with_the_values_checked(self):
        calls = tool_calls_from_events([{"event_id": "e1", "tool_id": "tool-1", "tool_name": "save_region",
                                         "status": "failed", "arguments": {"region": "france"},
                                         "error": "required parameters are missing or empty: postcode"}])
        other = check(kind="tool_called", tool="tool-1", expect="should_not", args={"region": "united-kingdom"})
        same = check(kind="tool_called", tool="tool-1", expect="should_not", args={"region": "france"})
        assert turn_fact(other, resolve_targets(other, CATALOG), turn(tool_calls=calls))[0] is False
        assert turn_fact(same, resolve_targets(same, CATALOG), turn(tool_calls=calls))[0] is True

    def test_a_tool_called_by_another_agent_does_not_count(self):
        calls = tool_calls_from_events([{"tool_id": "tool-1", "tool_name": "save_region", "agent_id": "agent-2",
                                         "status": "succeeded"}])
        item = check(kind="tool_called", tool="tool-1", agent="agent-1")
        assert turn_fact(item, resolve_targets(item, CATALOG), turn(tool_calls=calls))[0] is False

    def test_a_step_that_should_run_is_judged_by_its_latest_run_of_a_loop(self):
        # As Action Taken did: the step's latest run is the one that counts.
        item = check(kind="step_runs", step="step-1")
        steps = [{"id": "step-1_0", "status": "success"}, {"id": "step-1", "status": "failed", "error": "boom"}]
        assert turn_fact(item, resolve_targets(item, CATALOG), turn(steps=steps)) == (
            False, "The step started but did not finish."
        )
        fixed = [{"id": "step-1_0", "status": "failed", "error": "boom"}, {"id": "step-1", "status": "success"}]
        assert turn_fact(item, resolve_targets(item, CATALOG), turn(steps=fixed))[0] is True
        assert turn_fact(item, resolve_targets(item, CATALOG), turn(steps=[{"id": "step-10", "status": "success"}]))[0] is False

    def test_a_step_that_should_not_run_counts_every_run_of_a_loop(self):
        item = check(kind="step_runs", step="step-1", expect="should_not")
        steps = [{"id": "step-1_0", "status": "success"}, {"id": "step-1", "status": "failed", "error": "boom"}]
        assert turn_fact(item, resolve_targets(item, CATALOG), turn(steps=steps))[0] is True

    def test_a_router_matches_its_branch_by_value_or_label(self):
        item = check(kind="route_taken", router="router-1", branch="case-9", branch_label="Refund")
        targets = resolve_targets(item, CATALOG)
        assert turn_fact(item, targets, turn(routes=[{"id": "router-1", "route": "case-9"}]))[0] is True
        assert turn_fact(item, targets, turn(routes=[{"id": "router-1", "route": "x", "route_label": "refund"}]))[0] is True
        assert turn_fact(item, targets, turn(routes=[{"id": "router-1", "route": "default"}])) == (
            False, 'The router took "default".'
        )
        assert turn_fact(item, targets, turn())[1] == "The router did not run."

    def test_a_state_value_compares_loosely(self):
        item = check(kind="state_equals", key="counter", value="2")
        assert turn_fact(item, Targets(), turn(state={"counter": 2}))[0] is True
        assert turn_fact(item, Targets(), turn(state={})) == (False, "counter was not set.")

    def test_values_compare_without_case_or_number_format(self):
        assert same_value(" Refund ", "refund")
        assert same_value(5, "5.0")
        assert same_value(True, "true")
        assert same_value({"b": 1, "a": 2}, {"a": 2, "b": 1})
        assert not same_value("refund", "standard")

    def test_a_list_or_object_matches_its_json_text(self):
        # The editor stores every value as text.
        assert same_value(["refund"], '["refund"]')
        assert same_value({"a": 2, "b": 1}, '{"b": 1, "a": 2}')
        assert not same_value(["refund"], "refund")


class TestNames:
    def test_ids_win_then_names(self):
        assert resolve_targets(check(kind="step_runs", step="step-1", step_name="Renamed"), CATALOG).node_ids == ["step-1"]
        assert resolve_targets(check(kind="step_runs", step="gone", step_name="create ticket"), CATALOG).node_ids == ["step-1"]
        assert resolve_targets(check(kind="tool_called", tool_name="Save region"), CATALOG).tool_ids == ["tool-1"]

    def test_a_missing_name_did_not_run_and_a_shared_one_is_any_of_them(self):
        missing = resolve_targets(check(kind="step_runs", step_name="Nope"), CATALOG)
        assert missing.problem is None
        assert missing.missing == 'The step "Nope" is not in the workflow that ran, so it did not run.'
        shared = resolve_targets(check(kind="step_runs", step_name="Log"), CATALOG)
        assert shared.problem is None and len(shared.node_ids) == 2
        ran = turn(steps=[{"id": shared.node_ids[1], "status": "success"}])
        assert turn_fact(check(kind="step_runs", step_name="Log"), shared, ran)[0] is True

    def test_a_tool_name_on_several_agents_means_any_of_them(self):
        catalog = {"agents": [
            {"id": "agent-1", "label": "Refund agent", "tools": [{"id": "t1", "name": "log", "label": "Log"}]},
            {"id": "agent-2", "label": "Ticket agent", "tools": [{"id": "t2", "name": "log", "label": "Log"}]},
            {"id": "agent-3", "label": "Region agent", "tools": [{"id": "t3", "name": "save_region", "label": "Save region"}]},
        ]}
        assert resolve_targets(check(kind="tool_called", tool="gone", tool_name="log"), catalog).tool_ids == ["t1", "t2"]
        by_agent = resolve_targets(check(kind="tool_called", tool_name="log", agent_name="Ticket agent"), catalog)
        assert by_agent.tool_ids == ["t2"] and by_agent.agent_id == "agent-2"
        # The agent cannot call a tool it does not have, so the check is graded and a Should misses.
        lacking = check(kind="tool_called", tool_name="log", agent_name="Region agent")
        targets = resolve_targets(lacking, catalog)
        assert targets.problem is None and targets.missing_tools == ["log"]
        ran = turn(steps=[{"id": "agent-3"}])
        assert turn_fact(lacking, targets, ran) == (False, "log was not called. It is not in the workflow that ran.")

    def test_without_a_catalog_names_match_the_events(self):
        item = check(kind="tool_called", tool_name="save_region")
        calls = tool_calls_from_events([{"tool_id": "t9", "tool_name": "save_region", "status": "succeeded"}])
        assert turn_fact(item, resolve_targets(item, None), turn(tool_calls=calls))[0] is True


class TestGrading:
    def test_every_conversation_at_some_point(self):
        conversations = [
            [turn("a1", "a", 0, reply="Hi"), turn("a2", "a", 1, reply="London it is")],
            [turn("b1", "b", 0, reply="Hi"), turn("b2", "b", 1, reply="Bye")],
        ]
        first, second = grade([check()], conversations)
        assert first["result"]["status"] == "passed"
        assert first["result"]["observed"] == 'Turn 2: The reply mentioned "London".'
        assert first["source_conversation_id"] == "a" and first["case_id"] is None
        assert second["result"]["status"] == "failed"
        assert second["result"]["observed"] == 'Not on any of its 2 turns. Turn 2: The reply did not mention "London".'

    def test_on_every_turn_names_the_turns_that_missed(self):
        conversations = [[turn("a1", "a", 0, reply="London"), turn("a2", "a", 1, reply="Paris"),
                          turn("a3", "a", 2, reply="Rome")]]
        (entry,) = grade([check(when="every_turn")], conversations)
        assert entry["result"]["status"] == "failed"
        assert entry["result"]["turns"] == [2, 3]

    def test_says_which_turns_it_read_so_a_page_can_show_where_it_held(self):
        conversations = [[turn("a1", "a", 0, reply="London"), turn("a2", "a", 1, reply="Paris"),
                          turn("a3", "a", 2, reply="London")]]
        broke, held = grade([check(when="every_turn"), check(id="c2", text="Rome", expect="should_not")], conversations)
        assert broke["result"]["turns"] == [2] and broke["result"]["checked"] == [1, 2, 3]
        assert held["result"]["status"] == "passed" and held["result"]["checked"] == [1, 2, 3]
        assert broke["result"]["checked_facts"][1] == 'The reply did not mention "London".'

    def test_should_not_fails_on_the_first_time_it_happens(self):
        conversations = [[turn("a1", "a", 0, reply="Use RingGo"), turn("a2", "a", 1, reply="or RingGo")]]
        (entry,) = grade([check(text="ringgo", expect="should_not", level="conversation", conversation_id="a")],
                         conversations)
        assert entry["result"]["status"] == "failed"
        assert entry["result"]["observed"].startswith("Turn 1:")
        assert entry["result"]["turns"] == [1, 2]

    def test_one_conversation_only_grades_that_conversation(self):
        conversations = [[turn("a1", "a", 0, reply="London")], [turn("b1", "b", 0, reply="London")]]
        entries = grade([check(level="conversation", conversation_id="b")], conversations)
        assert [entry["source_conversation_id"] for entry in entries] == ["b"]

    def test_chosen_conversations_grade_only_those(self):
        conversations = [[turn("a1", "a", 0, reply="London")], [turn("b1", "b", 0, reply="Paris")],
                         [turn("c1", "c", 0, reply="Rome")]]
        entries = grade([check(level="conversation", conversation_ids=["c", "a"])], conversations)
        assert [entry["source_conversation_id"] for entry in entries] == ["a", "c"]
        assert [entry["result"]["status"] for entry in entries] == ["passed", "failed"]
        assert conversation_verdicts(entries, conversations) == {"a": "passed", "b": "not_evaluated", "c": "failed"}

    def test_chosen_conversations_on_every_turn_name_the_turns_that_missed(self):
        conversations = [[turn("a1", "a", 0, reply="London"), turn("a2", "a", 1, reply="Paris")],
                         [turn("b1", "b", 0, reply="London")]]
        first, second = grade([check(level="conversation", conversation_ids=["a", "b"], when="every_turn")],
                              conversations)
        assert first["result"]["status"] == "failed" and first["result"]["turns"] == [2]
        assert second["result"]["status"] == "passed"

    @pytest.mark.parametrize(
        "chosen, comment",
        [
            (["gone"], "The conversation this check is about is no longer in the dataset."),
            (["gone", "lost"], "The conversations this check is about are no longer in the dataset."),
            (["a", "gone"], "1 of the 2 conversations this check is about is no longer in the dataset."),
            (["a", "gone", "lost"], "2 of the 3 conversations this check is about are no longer in the dataset."),
        ],
    )
    def test_chosen_conversations_the_dataset_lost_are_said_once(self, chosen, comment):
        conversations = [[turn("a1", "a", 0, reply="London")]]
        entries = grade([check(level="conversation", conversation_ids=chosen)], conversations)
        lost = [entry for entry in entries if entry["source_conversation_id"] is None]
        assert len(lost) == 1 and lost[0]["case_id"] is None
        assert lost[0]["result"]["status"] == "not_evaluated" and lost[0]["result"]["comment"] == comment
        graded = [entry["source_conversation_id"] for entry in entries if entry["source_conversation_id"]]
        assert graded == (["a"] if "a" in chosen else [])

    def test_a_turn_is_found_by_case_then_by_conversation_and_position(self):
        conversations = [[turn("a1", "a", 0, reply="x", message="Hi"), turn("a2", "a", 1, reply="London", message="I am in London")]]
        by_case = check(level="turn", case_id="a2")
        by_position = check(id="c2", level="turn", case_id="gone", conversation_id="a", turn_index=1,
                            turn_message="I am in  LONDON")
        entries = grade([by_case, by_position], conversations)
        assert [entry["result"]["status"] for entry in entries] == ["passed", "passed"]
        assert entries[0]["case_id"] == "a2" and entries[0]["source_conversation_id"] == "a"

    def test_a_turn_that_changed_or_left_is_not_evaluated(self):
        conversations = [[turn("a1", "a", 0, reply="London", message="Hi")]]
        changed = check(level="turn", conversation_id="a", turn_index=0, turn_message="Something else")
        gone = check(id="c2", level="turn", case_id="nope")
        first, second = grade([changed, gone], conversations)
        assert first["result"]["status"] == "not_evaluated"
        assert "changed" in first["result"]["comment"]
        assert "no longer in the dataset" in second["result"]["comment"]
        # A lost turn stays with its conversation when the check names one.
        assert first["case_id"] is None and first["source_conversation_id"] == "a"
        assert second["case_id"] is None and second["source_conversation_id"] is None

    def test_a_turn_that_did_not_run_says_why(self):
        crashed, waiting, fine = turn(crashed=True), turn(waiting_for_human=True), turn()
        assert skip_reason([fine, crashed]) == "This turn did not run because an earlier turn failed."
        assert skip_reason([waiting]) == "This turn did not run because the conversation was waiting for a person."
        assert skip_reason([fine]) == "This turn did not run."
        skipped = turn("a2", "a", 1, ran=False, skip_reason=skip_reason([waiting]))
        (entry,) = grade([check(level="turn", case_id="a2")], [[waiting, skipped]])
        assert entry["result"]["comment"] == "This turn did not run because the conversation was waiting for a person."

    def test_a_crashed_turn_fails_its_check_and_its_conversation(self):
        conversations = [[turn("a1", "a", 0, crashed=True, error="Execution failed: boom"),
                          turn("a2", "a", 1, ran=False)]]
        crashed = check(level="turn", case_id="a1")
        skipped = check(id="c2", level="turn", case_id="a2")
        first, second = grade([crashed, skipped], conversations)
        assert first["result"]["status"] == "failed"
        assert first["result"]["observed"] == "The turn did not finish: Execution failed: boom"
        assert second["result"]["status"] == "not_evaluated"
        assert conversation_verdicts([first, second], conversations) == {"a": "failed"}

    def test_a_conversation_without_checks_or_crashes_is_not_evaluated(self):
        conversations = [[turn("a1", "a", 0, reply="London")], [turn("b1", "b", 0, reply="Paris")]]
        planned = grade([check(level="conversation", conversation_id="a")], conversations)
        assert conversation_verdicts(planned, conversations) == {"a": "passed", "b": "not_evaluated"}

    def test_a_conversation_that_did_not_run_to_the_end_is_not_a_pass(self):
        conversations = [[
            turn("a1", "a", 0, reply="London"),
            turn("a2", "a", 1, ran=False, skip_reason="This turn did not run because the conversation was waiting for a person."),
        ]]
        planned = grade([check(level="conversation", conversation_id="a")], conversations)
        assert planned[0]["result"]["status"] == "passed"
        assert conversation_verdicts(planned, conversations) == {"a": "not_evaluated"}

    def test_a_turn_that_could_not_be_read_still_played(self):
        conversations = [[
            turn("a1", "a", 0, reply="London"),
            turn("a2", "a", 1, ran=False, skip_reason=UNREADABLE_TURN),
        ]]
        planned = grade([check(level="conversation", conversation_id="a")], conversations)
        assert conversation_verdicts(planned, conversations) == {"a": "passed"}

    def test_a_crash_whose_turn_could_not_be_read_still_fails(self):
        conversations = [[
            turn("a1", "a", 0, reply="London"),
            turn("a2", "a", 1, crashed=True, error="boom", ran=False, skip_reason=UNREADABLE_TURN),
        ]]
        planned = grade([check(level="conversation", conversation_id="a")], conversations)
        assert conversation_verdicts(planned, conversations) == {"a": "failed"}

    def test_a_crash_whose_turn_could_not_be_read_fails_no_step_fails(self):
        conversations = [[
            turn("a1", "a", 0, reply="London"),
            turn("a2", "a", 1, crashed=True, error="boom", ran=False, skip_reason=UNREADABLE_TURN),
        ]]
        (entry,) = grade([check(kind="step_fails", expect="should_not")], conversations)
        assert entry["result"]["status"] == "failed"
        assert entry["result"]["observed"].endswith("Turn 2 did not finish: boom")
        # Any other check says the turn did not finish, not that it could not be read.
        (other,) = grade([check(kind="reply_mentions", text="Paris", expect="should_not")], conversations)
        assert other["result"]["comment"] == "Turn 2 did not finish: boom"

    def test_a_manual_turn_is_its_own_conversation(self):
        conversations = [[turn("m1", "m1", 0, reply="London")]]
        (entry,) = grade([check()], conversations)
        assert entry["case_id"] == "m1" and entry["source_conversation_id"] is None
        assert conversation_verdicts([entry], conversations) == {"m1": "passed"}

    def test_a_step_the_workflow_lacks_did_not_run(self):
        # As Action Taken did, a step that is not there did not complete: a Should fails, a Should not holds.
        conversations = [[turn("a1", "a", 0)]]
        (should,) = grade([check(kind="step_runs", step_name="Nope")], conversations)
        assert should["result"]["status"] == "failed"
        assert should["result"]["observed"].endswith('The step "Nope" is not in the workflow that ran, so it did not run.')
        (should_not,) = grade([check(kind="step_runs", step_name="Nope", expect="should_not")], conversations)
        assert should_not["result"]["status"] == "passed"

    def test_a_turn_check_on_a_missing_step_stays_on_its_turn(self):
        conversations = [[turn("a1", "a", 0)]]
        (entry,) = grade([check(kind="step_runs", step_name="Nope", level="turn", case_id="a1")], conversations)
        assert entry["result"]["status"] == "failed"
        assert entry["case_id"] == "a1" and entry["source_conversation_id"] == "a"


class TestJudge:
    def test_reply_rules_grade_each_reply_and_conversation_rules_the_transcript(self):
        conversations = [[turn("a1", "a", 0, reply="x"), turn("a2", "a", 1, reply="y")]]
        per_turn = check(id="p", kind="reply_meets", rubric="Be polite", when="every_turn")
        whole = check(id="w", kind="reply_meets", rubric="Ask for the plate")
        one = check(id="o", kind="reply_meets", rubric="List regions", level="turn", case_id="a2")
        targets = {item.id: Targets() for item in (per_turn, whole, one)}
        requests = judge_requests([per_turn, whole, one], conversations, targets)
        assert [request.key for request in requests] == [
            ("p", ("a1",)), ("p", ("a2",)), ("w", ("a1", "a2")), ("o", ("a2",)),
        ]

    def test_chosen_conversations_ask_the_grader_only_about_them(self):
        conversations = [[turn("a1", "a", 0, reply="x"), turn("a2", "a", 1, reply="y")],
                         [turn("b1", "b", 0, reply="z")], [turn("c1", "c", 0, reply="w")]]
        per_turn = check(id="p", kind="reply_meets", rubric="Be polite", level="conversation", conversation_ids=["a"],
                         when="every_turn")
        whole = check(id="w", kind="reply_meets", rubric="Ask for the plate", level="conversation",
                      conversation_ids=["b"])
        targets = {item.id: Targets() for item in (per_turn, whole)}
        requests = judge_requests([per_turn, whole], conversations, targets)
        assert [request.key for request in requests] == [("p", ("a1",)), ("p", ("a2",)), ("w", ("b1",))]

    def test_verdicts_become_results(self):
        conversations = [[turn("a1", "a", 0, reply="x"), turn("a2", "a", 1, reply="y")]]
        whole = check(id="w", kind="reply_meets", rubric="Ask for the plate")
        per_turn = check(id="p", kind="reply_meets", rubric="Be polite", when="every_turn")
        verdicts = {
            ("w", ("a1", "a2")): JudgeVerdict(score=0.9, reason="Asked on turn 2."),
            ("p", ("a1",)): JudgeVerdict(score=1.0, reason="Polite."),
            ("p", ("a2",)): JudgeVerdict(score=0.0, reason="Rude."),
        }
        whole_entry, per_turn_entry = grade([whole, per_turn], conversations, verdicts)
        assert whole_entry["result"]["status"] == "passed"
        assert whole_entry["result"]["observed"] == "Asked on turn 2."
        assert whole_entry["result"]["score"] == 0.9
        assert per_turn_entry["result"]["status"] == "failed"
        assert per_turn_entry["result"]["observed"] == "Turn 2: Rude."

    def test_a_grader_that_did_not_answer_is_not_evaluated(self):
        conversations = [[turn("a1", "a", 0, reply="x")]]
        whole = check(id="w", kind="reply_meets", rubric="Ask for the plate")
        (entry,) = grade([whole], conversations, {("w", ("a1",)): JudgeVerdict(error=True, reason="Bad JSON")})
        assert entry["result"]["status"] == "not_evaluated"
        assert entry["result"]["error"] is True

    def test_a_turn_waiting_for_a_person_has_no_reply_to_grade(self):
        waiting = turn("a1", "a", 0, waiting_for_human=True)
        one = check(id="o", kind="reply_meets", rubric="Greet", level="turn", case_id="a1")
        each = check(id="e", kind="reply_meets", rubric="Greet", when="every_turn")
        assert judge_requests([one, each], [[waiting]], {"o": Targets(), "e": Targets()}) == []
        for entry in grade([one, each], [[waiting]]):
            assert entry["result"]["status"] == "not_evaluated"
            assert "error" not in entry["result"]
            assert entry["result"]["comment"] == "The turn was waiting for a person, so there was no reply to grade."

    def test_the_expectation_carries_the_should_or_should_not(self):
        assert judge_expectation(check(kind="reply_meets", rubric="Greet", expect="should_not"), False) == (
            "The reply should not do this: Greet"
        )
        assert judge_expectation(check(kind="reply_meets", rubric="Greet"), True) == (
            "At some point in the conversation, the assistant should do this: Greet"
        )
        assert transcript([turn(message="Hi", reply="Hello"), turn(crashed=True, message="Then?")]) == (
            "USER: Hi\nASSISTANT: Hello\nUSER: Then?\nASSISTANT: (no reply, the turn failed)"
        )

    @pytest.mark.asyncio
    async def test_a_judge_that_raises_gives_an_error_verdict(self):
        async def judge(request: JudgeRequest) -> JudgeVerdict:
            if request.turns[0].case_id == "a2":
                raise TimeoutError()
            return JudgeVerdict(score=1.0)

        item = check(kind="reply_meets", rubric="Greet", when="every_turn")
        requests = [JudgeRequest(item, [turn("a1")]), JudgeRequest(item, [turn("a2")])]
        verdicts = await run_judge(requests, judge)
        assert verdicts[("c1", ("a1",))].met
        assert verdicts[("c1", ("a2",))].error

    @pytest.mark.asyncio
    async def test_gradings_past_the_budget_run_out_of_time(self):
        async def judge(request: JudgeRequest) -> JudgeVerdict:
            if request.turns[0].case_id != "a1":
                await asyncio.sleep(5)
            return JudgeVerdict(score=1.0)

        item = check(kind="reply_meets", rubric="Greet", when="every_turn")
        requests = [JudgeRequest(item, [turn(case_id)]) for case_id in ("a1", "a2", "a3")]
        verdicts = await run_judge(requests, judge, concurrency=1, budget_seconds=0.2)
        assert verdicts[("c1", ("a1",))].met
        for case_id in ("a2", "a3"):
            assert verdicts[("c1", (case_id,))].reason == "The AI grader ran out of time for this run."

    @pytest.mark.asyncio
    async def test_with_no_time_left_nothing_is_sent_to_the_grader(self):
        judge = AsyncMock(return_value=JudgeVerdict(score=1.0))
        item = check(kind="reply_meets", rubric="Greet", when="every_turn")
        verdicts = await run_judge([JudgeRequest(item, [turn("a1")])], judge, budget_seconds=0)
        judge.assert_not_awaited()
        assert verdicts[("c1", ("a1",))].reason == "The AI grader ran out of time for this run."
