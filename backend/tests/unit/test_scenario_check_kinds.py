"""The checks that replace the older methods: the expected reply, the knowledge base and failed steps."""
import pytest

from app.services.scenario_checks import (
    NO_EXPECTED_REPLY,
    NO_PASSAGES,
    UNREADABLE_TURN,
    Check,
    JudgeRequest,
    JudgeVerdict,
    Targets,
    TurnRecord,
    conversation_verdicts,
    describe_check,
    grade_checks,
    judge_prompt,
    judge_requests,
    matches_exactly,
    parse_checks_config,
    turn_fact,
)


def check(**fields) -> Check:
    return Check(**{"id": "c1", "kind": "reply_matches", "match": "exact", **fields})


def turn(case_id="t1", conversation="conv-a", position=0, **fields) -> TurnRecord:
    return TurnRecord(
        case_id=case_id,
        conversation_key=conversation,
        turn_index=position,
        position=position,
        message=fields.pop("message", f"message {position}"),
        **fields,
    )


def grade(checks, conversations, verdicts=None):
    return grade_checks(checks, conversations, {item.id: Targets() for item in checks}, verdicts or {})


class TestModel:
    @pytest.mark.parametrize("kind", ["reply_matches", "reply_grounded"])
    @pytest.mark.parametrize("expect", ["should", "should_not"])
    def test_every_turn_kinds_are_graded_on_each_turn(self, kind, expect):
        item = check(kind=kind, match="contains", expect=expect)
        assert item.when == "every_turn"
        assert item.per_turn
        assert check(kind=kind, match="contains", expect=expect, level="conversation", conversation_id="a").per_turn

    @pytest.mark.parametrize(
        "fields",
        [
            {"kind": "reply_matches", "match": "exact"},
            {"kind": "reply_matches", "match": "meaning"},
            {"kind": "reply_grounded"},
            {"kind": "step_fails"},
            {"kind": "only_tools", "tools": [{"tool": "tool-1"}]},
            {"kind": "value_equals", "path": "outputs.status", "value": "ok"},
        ],
    )
    def test_every_kind_can_say_what_should_not_happen(self, fields):
        assert Check(id="c", expect="should_not", **fields).expect == "should_not"

    def test_a_failed_step_is_any_step_at_some_point_or_on_every_turn(self):
        assert check(kind="step_fails").when == "anywhere"
        assert check(kind="step_fails", when="every_turn").per_turn

    def test_the_expected_reply_needs_how_closely(self):
        with pytest.raises(ValueError, match="fill in"):
            parse_checks_config({"checks": [{"id": "a", "kind": "reply_matches"}]})

    @pytest.mark.parametrize("placement", [{}, {"level": "conversation", "conversation_ids": ["a"]}])
    def test_only_a_rule_on_each_turn_reads_more_than_the_reply(self, placement):
        assert check(kind="reply_meets", rubric="Quote prices", context="knowledge_base", when="every_turn",
                     **placement).context
        with pytest.raises(ValueError, match="only a rule graded on each turn"):
            check(kind="reply_meets", rubric="Quote prices", context="knowledge_base", **placement)
        with pytest.raises(ValueError, match="cannot read"):
            check(kind="reply_mentions", text="x", context="expected_reply")

    def test_which_kinds_the_ai_grades(self):
        assert check(match="meaning").ai_graded
        assert not check(match="exact").ai_graded
        assert check(kind="reply_grounded").ai_graded
        assert not check(kind="step_fails").ai_graded


class TestSentences:
    @pytest.mark.parametrize(
        "fields, sentence",
        [
            ({"match": "exact"}, "On every turn, the reply should be exactly the expected reply."),
            ({"match": "contains"}, "On every turn, the reply should contain the expected reply."),
            ({"match": "meaning", "level": "conversation", "conversation_id": "a"},
             "On every turn, the reply should say the same as the expected reply."),
            ({"match": "meaning", "level": "turn", "case_id": "x"}, "The reply should say the same as the expected reply."),
            ({"kind": "reply_grounded"}, "On every turn, the reply should stick to the knowledge base."),
            ({"match": "contains", "expect": "should_not"}, "On every turn, the reply should not contain the expected reply."),
            ({"kind": "reply_grounded", "expect": "should_not"},
             "On every turn, the reply should not stick to the knowledge base."),
            ({"kind": "step_fails", "expect": "should_not"}, "In every conversation, no step should ever fail."),
            ({"kind": "step_fails", "expect": "should_not", "level": "turn", "case_id": "x"}, "No step should fail."),
            ({"kind": "step_fails"}, "In every conversation, at some point, a step should fail."),
            ({"kind": "reply_meets", "rubric": "Quote prices", "context": "knowledge_base", "when": "every_turn"},
             'On every turn, the reply should do this: "Quote prices", graded with the knowledge-base passages.'),
            ({"kind": "reply_meets", "rubric": "Agree", "context": "expected_reply", "level": "turn", "case_id": "x"},
             'The reply should do this: "Agree", graded with the expected reply.'),
        ],
    )
    def test_sentences(self, fields, sentence):
        assert describe_check(check(**fields)) == sentence


class TestExpectedReply:
    def test_exact_and_contains(self):
        same = turn(reply="Your refund is on its way.", expected="Your refund is on its way.")
        inside = turn(reply="Thanks! Your refund is on its way.", expected="your refund is on its way.")
        assert turn_fact(check(match="exact"), Targets(), same) == (True, "The reply was exactly the expected reply.")
        assert turn_fact(check(match="exact"), Targets(), inside)[0] is False
        assert turn_fact(check(match="contains"), Targets(), inside) == (True, "The reply contained the expected reply.")

    def test_a_turn_without_an_expected_reply_is_not_graded(self):
        assert turn_fact(check(match="exact"), Targets(), turn(reply="Hi")) == (None, NO_EXPECTED_REPLY)

    def test_json_compares_as_json(self):
        expected = {"status": "ok", "count": 2}
        assert matches_exactly(turn(output={"count": 2, "status": "ok"}, expected="x", expected_value=expected))
        assert matches_exactly(turn(reply='{"count": 2, "status": "ok"}', expected="x", expected_value=expected))
        assert matches_exactly(turn(reply='{"count":2,"status":"ok"}', expected="x", expected_value={"text": '{"status": "ok", "count": 2}'}))
        assert not matches_exactly(turn(reply='{"count": 3, "status": "ok"}', expected="x", expected_value=expected))

    def test_json_values_compare_as_values(self):
        expected = {"amount": 10, "items": [1, 2]}
        assert matches_exactly(turn(output={"items": [1, 2], "amount": 10.0}, expected="x", expected_value=expected))

    def test_contains_reads_a_json_reply_as_json(self):
        record = turn(output={"status": "ok", "id": 5}, reply='{"status": "ok", "id": 5}',
                      expected='{"id": 5, "status": "ok"}', expected_value={"id": 5, "status": "ok"})
        assert turn_fact(check(match="contains"), Targets(), record)[0] is True

    def test_a_wrapped_text_is_text(self):
        record = turn(reply="Hello", expected="Hello", expected_value={"text": "Hello"})
        assert matches_exactly(record)

    def test_only_turns_with_an_expected_reply_count(self):
        conversations = [[
            turn("a1", "a", 0, reply="Hi there", expected="Hi"),
            turn("a2", "a", 1, reply="Anything"),
            turn("a3", "a", 2, reply="Bye", expected="Goodbye"),
        ]]
        (entry,) = grade([check(match="contains")], conversations)
        assert entry["result"]["status"] == "failed"
        assert entry["result"]["turns"] == [3]
        assert entry["result"]["facts"] == ["The reply did not contain the expected reply."]

    def test_no_expected_reply_anywhere_is_said_of_the_conversation(self):
        (entry,) = grade([check(match="exact")], [[turn("a1", "a", 0, reply="x"), turn("a2", "a", 1, reply="y")]])
        assert entry["result"]["status"] == "not_evaluated"
        assert entry["result"]["comment"] == "No turn of this conversation has an expected reply in the dataset."

    def test_same_meaning_asks_the_grader_only_where_there_is_an_expected_reply(self):
        item = check(match="meaning")
        conversations = [[turn("a1", "a", 0, reply="x", expected="y"), turn("a2", "a", 1, reply="z")]]
        requests = judge_requests([item], conversations, {"c1": Targets()})
        assert [request.key for request in requests] == [("c1", ("a1",))]
        (entry,) = grade([item], conversations, {("c1", ("a1",)): JudgeVerdict(score=0.2, reason="Different window.")})
        assert entry["result"]["status"] == "failed"
        assert entry["result"]["observed"] == "Turn 1: Different window."
        assert entry["result"]["facts"] == ["Different window."]

    def test_a_turn_level_check_without_an_expected_reply_is_not_graded(self):
        item = check(match="meaning", level="turn", case_id="a1")
        (entry,) = grade([item], [[turn("a1", "a", 0, reply="x")]])
        assert entry["result"]["status"] == "not_evaluated"
        assert entry["result"]["comment"] == NO_EXPECTED_REPLY

    def test_a_crashed_turn_fails_a_turn_level_check(self):
        item = check(match="exact", level="turn", case_id="a1")
        (entry,) = grade([item], [[turn("a1", "a", 0, crashed=True, error="boom", expected="x")]])
        assert entry["result"]["status"] == "failed"


class TestKnowledgeBase:
    def test_turns_without_passages_are_not_graded(self):
        item = check(kind="reply_grounded")
        conversations = [[turn("a1", "a", 0, reply="x", passages="Refunds take 5 days."), turn("a2", "a", 1, reply="y")]]
        requests = judge_requests([item], conversations, {"c1": Targets()})
        assert [request.key for request in requests] == [("c1", ("a1",))]
        (entry,) = grade([item], conversations, {("c1", ("a1",)): JudgeVerdict(score=1.0, reason="Supported.")})
        assert entry["result"]["status"] == "passed"
        assert entry["result"]["observed"] == "Met on the one turn checked; the other turn could not be checked."

    def test_no_passages_anywhere_is_said_of_the_conversation(self):
        (entry,) = grade([check(kind="reply_grounded")], [[turn("a1", "a", 0, reply="x")]])
        assert entry["result"]["comment"] == "No turn of this conversation found knowledge-base passages to check against."

    def test_a_rule_reading_the_knowledge_base_needs_passages(self):
        item = check(kind="reply_meets", rubric="Quote prices", context="knowledge_base", level="turn", case_id="a1")
        (entry,) = grade([item], [[turn("a1", "a", 0, reply="x")]])
        assert entry["result"]["comment"] == NO_PASSAGES


class TestFailedSteps:
    def test_a_step_error_fails_a_step_that_should_not_fail(self):
        conversations = [[
            turn("a1", "a", 0, reply="x"),
            turn("a2", "a", 1, reply="y", step_errors='The step "Search" failed: timed out.'),
        ]]
        (entry,) = grade([check(kind="step_fails", expect="should_not")], conversations)
        assert entry["result"]["status"] == "failed"
        assert entry["result"]["observed"] == 'Turn 2: The step "Search" failed: timed out.'

    def test_no_errors_passes(self):
        (entry,) = grade([check(kind="step_fails", expect="should_not")], [[turn("a1", "a", 0, reply="x")]])
        assert entry["result"]["status"] == "passed"
        assert entry["result"]["observed"] == "Not on its one turn."

    def test_no_errors_says_how_many_turns(self):
        conversations = [[turn("a1", "a", 0, reply="x"), turn("a2", "a", 1, reply="y")]]
        (entry,) = grade([check(kind="step_fails", expect="should_not")], conversations)
        assert entry["result"]["observed"] == "Not on any of its 2 turns."

    def test_a_step_that_should_fail(self):
        failing = [[turn("a1", "a", 0, reply="x"), turn("a2", "a", 1, step_errors='The step "Pay" failed: declined.')]]
        (entry,) = grade([check(kind="step_fails")], failing)
        assert entry["result"]["status"] == "passed"
        assert entry["result"]["observed"] == 'Turn 2: The step "Pay" failed: declined.'
        (entry,) = grade([check(kind="step_fails")], [[turn("a1", "a", 0, reply="x")]])
        assert entry["result"]["status"] == "failed"
        assert entry["result"]["observed"] == "Not on its one turn. Turn 1: No step failed."

    def test_a_crash_is_a_failed_step(self):
        assert turn_fact(check(kind="step_fails"), Targets(), turn(crashed=True, error="boom")) == (
            True, "The turn did not finish: boom",
        )


class TestAgentTools:
    @pytest.mark.parametrize("placement", [{}, {"level": "conversation", "conversation_ids": ["a"]}])
    def test_on_every_turn_only_turns_the_agent_ran_count(self, placement):
        item = Check(id="t", kind="tool_called", tool="lookup", tool_name="lookup", agent="billing",
                     agent_name="Billing", when="every_turn", **placement)
        targets = {"t": Targets(tool_ids=["lookup"], agent_id="billing", name="lookup")}
        conversations = [[
            turn("a1", "a", 0, steps=[{"id": "billing"}],
                 tool_calls=[{"tool_id": "lookup", "agent_id": "billing", "arguments": {}}]),
            turn("a2", "a", 1, steps=[{"id": "support"}]),
        ]]
        (entry,) = grade_checks([item], conversations, targets, {})
        assert entry["result"]["status"] == "passed"
        assert entry["result"]["observed"] == "Held on the one turn checked; the other turn could not be checked."

    def test_an_agent_that_never_ran_is_said_of_the_conversation(self):
        item = Check(id="t", kind="tool_called", tool="lookup", agent="billing", agent_name="Billing", when="every_turn")
        targets = {"t": Targets(tool_ids=["lookup"], agent_id="billing")}
        (entry,) = grade_checks([item], [[turn("a1", "a", 0, steps=[{"id": "support"}])]], targets, {})
        assert entry["result"]["status"] == "not_evaluated"
        assert entry["result"]["comment"] == 'The agent "Billing" did not run in this conversation.'

    def test_on_its_turn_an_agent_that_did_not_run_fails_and_says_why(self):
        item = Check(id="t", kind="tool_called", tool="lookup", tool_name="lookup", agent="billing",
                     agent_name="Billing", level="turn", case_id="a1")
        targets = {"t": Targets(tool_ids=["lookup"], agent_id="billing", name="lookup")}
        (entry,) = grade_checks([item], [[turn("a1", "a", 0, steps=[{"id": "support"}])]], targets, {})
        assert entry["result"]["status"] == "failed"
        assert entry["result"]["observed"] == '"Billing" did not run, so lookup was not called.'


class TestPrompts:
    def test_same_meaning_shows_the_expected_reply(self):
        request = JudgeRequest(check(match="meaning"), [turn(message="When?", reply="In 5 days.", expected="Within a week.")])
        system, user = judge_prompt(request)
        assert "EXPECTED REPLY is the reply the dataset expects" in system
        assert "say the same as the EXPECTED REPLY" in system
        assert user == "QUESTION:\nWhen?\n\nEXPECTED REPLY:\nWithin a week.\n\nANSWER:\nIn 5 days."

    def test_the_knowledge_base_shows_its_passages(self):
        request = JudgeRequest(check(kind="reply_grounded"), [turn(message="Q", reply="A", passages="P")])
        system, user = judge_prompt(request)
        assert "KNOWLEDGE-BASE PASSAGES are what the assistant found" in system
        assert user == "QUESTION:\nQ\n\nKNOWLEDGE-BASE PASSAGES:\nP\n\nANSWER:\nA"

    def test_should_not_asks_the_ai_grader_the_other_way(self):
        request = JudgeRequest(check(match="meaning", expect="should_not"), [turn(reply="A", expected="B")])
        assert "EXPECTATION:\nThe reply should not say the same as the EXPECTED REPLY" in judge_prompt(request)[0]
        grounded = JudgeRequest(check(kind="reply_grounded", expect="should_not"), [turn(reply="A", passages="P")])
        assert "The reply should not stick to the KNOWLEDGE-BASE PASSAGES" in judge_prompt(grounded)[0]

    def test_a_plain_rule_reads_only_the_reply(self):
        item = check(kind="reply_meets", rubric="Greet", when="every_turn")
        system, user = judge_prompt(JudgeRequest(item, [turn(message="Hi", reply="Hello")]))
        assert "EXPECTATION:\nThe reply should do this: Greet" in system
        assert "applies only in some situations is met when this reply is not one of them" in system
        assert user == "QUESTION:\nHi\n\nANSWER:\nHello"

    def test_a_whole_conversation_rule_reads_the_transcript(self):
        item = check(kind="reply_meets", rubric="Ask for the plate")
        system, user = judge_prompt(JudgeRequest(item, [turn(message="Hi", reply="Hello")]))
        assert "CONVERSATION lists every turn" in system
        assert user == "CONVERSATION:\nUSER: Hi\nASSISTANT: Hello"


class TestTurnFacts:
    def test_each_listed_turn_says_what_it_did(self):
        item = Check(id="m", kind="reply_mentions", text="RingGo", expect="should_not")
        conversations = [[
            turn("a1", "a", 0, reply="Try RingGo"),
            turn("a2", "a", 1, reply="No"),
            turn("a3", "a", 2, reply="ringgo again"),
        ]]
        (entry,) = grade([item], conversations)
        assert entry["result"]["turns"] == [1, 3]
        assert entry["result"]["facts"] == ['The reply mentioned "RingGo".', 'The reply mentioned "RingGo".']


# ---- every older-method setting as a check ------------------------------------------------

from app.services.scenario_checks import (  # noqa: E402
    check_paths,
    only_tools_fact,
    read_path,
    resolve_targets,
    tool_fact,
)

TOOLS = {
    "agents": [{"id": "agent-1", "label": "Refund agent", "tools": [
        {"id": "tool-1", "name": "save_region", "label": "Save region"},
        {"id": "tool-2", "name": "change_mode", "label": "Change mode"},
        {"id": "tool-3", "name": "lookup", "label": "Lookup"},
    ]}],
    "routers": [{"id": "router-1", "label": "Mode", "branches": [{"value": "a", "label": "Refund"}]}],
    "action_nodes": [{"id": "step-1", "label": "Create ticket", "type": "zendeskTicketNode"}],
}


def call(tool_id, name, status="succeeded", result="done", agent="agent-1", **fields):
    return {"tool_id": tool_id, "tool_name": name, "agent_id": agent, "status": status, "result": result,
            "arguments": fields.get("arguments", {}), "refused": False}


def tool_check(**fields):
    return Check(**{"id": "t", "kind": "tool_called", "tool": "tool-1", "tool_name": "save_region", **fields})


class TestModelForEverySetting:
    @pytest.mark.parametrize(
        "fields",
        [
            {"expect": "should_not", "succeeds": True},
            {"expect": "should_not", "min_calls": 2},
            {"expect": "should_not", "tools": [{"tool": "tool-2"}]},
            {"min_calls": 3, "max_calls": 2},
            {"tools": [{}]},
        ],
    )
    def test_tool_settings_that_cannot_hold(self, fields):
        with pytest.raises(ValueError):
            tool_check(**fields)

    def test_only_tools_on_every_turn_or_overall(self):
        item = Check(id="o", kind="only_tools", tools=[{"tool": "tool-1"}], when="every_turn", max_calls=1, succeeds=True)
        assert item.when == "every_turn" and item.per_turn
        assert describe_check(item) == 'On every turn, only the tool "tool-1" should be used, called successfully at most 1 time.'

    def test_tools_that_should_not_be_used(self):
        item = Check(id="o", kind="only_tools", expect="should_not", tools=[{"tool_name": "a"}, {"tool_name": "b"}])
        assert describe_check(item) == 'In every conversation, none of the tools "a" and "b" should ever be used.'
        one = Check(id="o", kind="only_tools", expect="should_not", tools=[{"tool_name": "a"}], level="turn", case_id="x")
        assert describe_check(one) == 'The tool "a" should not be used.'
        with pytest.raises(ValueError, match="fill in"):
            Check(id="o", kind="only_tools", expect="should_not")
        with pytest.raises(ValueError, match="only apply to what should happen"):
            Check(id="o", kind="only_tools", expect="should_not", tools=[{"tool": "tool-1"}], max_calls=1)

    def test_a_tool_that_should_be_called_at_most_0_times_cannot_pass(self):
        with pytest.raises(ValueError, match="can never pass"):
            tool_check(max_calls=0)

    def test_grading_settings(self):
        with pytest.raises(ValueError, match="only a check graded by AI has a pass score"):
            Check(id="m", kind="reply_mentions", text="x", pass_score=0.7)
        with pytest.raises(ValueError, match="name the value"):
            Check(id="g", kind="reply_grounded", context="run_value")
        with pytest.raises(ValueError, match="cannot read"):
            Check(id="g", kind="reply_matches", match="meaning", context="session")
        assert describe_check(Check(id="g", kind="reply_grounded", context="expected_reply")) == (
            "On every turn, the reply should stick to the expected reply."
        )
        with pytest.raises(ValueError, match="only a check graded by AI has an AI grader"):
            Check(id="m", kind="reply_mentions", text="x", llm_provider_id="p1")
        with pytest.raises(ValueError, match="words can be mentioned"):
            Check(id="m", kind="reply_mentions", text="x", match="meaning")
        assert Check(id="v", kind="value_equals", path="outputs.status").value is None

    def test_sentences(self):
        assert describe_check(Check(id="m", kind="reply_mentions", text="Hi", match="exact", when="every_turn")) == (
            'On every turn, the reply should be exactly "Hi".'
        )
        assert describe_check(Check(id="r", kind="route_taken", branch="a", branch_label="Refund", when="every_turn")) == (
            'On every turn, a router should take "Refund".'
        )
        assert describe_check(Check(id="s", kind="step_runs", step_type="zendeskTicketNode", step_name="Zendesk ticket")) == (
            'In every conversation, at some point, a step of type "Zendesk ticket" should run.'
        )
        assert describe_check(Check(id="o", kind="only_tools", tools=[{"tool_name": "a"}, {"tool_name": "b"}],
                                    max_calls=3, level="conversation", conversation_id="c")) == (
            'Only the tools "a" and "b" should be used, called at most 3 times.'
        )


class TestTools:
    def test_a_tool_that_was_not_called_says_so(self):
        targets = resolve_targets(tool_check(), TOOLS)
        assert tool_fact(tool_check(), targets, [turn()]) == (False, "save_region was not called.")

    def test_any_of_several_tools(self):
        item = tool_check(tools=[{"tool": "tool-2", "tool_name": "change_mode"}], when="every_turn")
        targets = resolve_targets(item, TOOLS)
        assert targets.tool_ids == ["tool-1", "tool-2"]
        assert tool_fact(item, targets, [turn(tool_calls=[call("tool-2", "change_mode")])]) == (
            True, "change_mode was called."
        )
        assert tool_fact(item, targets, [turn()]) == (False, 'None of "save_region" or "change_mode" was called.')

    def test_each_of_several_tools_has_its_own_values_and_result(self):
        item = tool_check(args={"region": "uk"}, tools=[
            {"tool": "tool-2", "tool_name": "change_mode", "args": {"mode": "refund"}, "result_contains": "saved"},
        ])
        targets = resolve_targets(item, TOOLS)

        def change(mode, result="Mode saved"):
            return {**call("tool-2", "change_mode", result=result, arguments={"mode": mode}), "shown_arguments": {"mode": mode}}

        # The other tool is held to its own values and result, not to the first tool's.
        assert tool_fact(item, targets, [turn(tool_calls=[change("refund")])]) == (
            True, "change_mode was called with mode = refund."
        )
        assert tool_fact(item, targets, [turn(tool_calls=[change("standard")])]) == (
            False, "change_mode was called with mode = standard."
        )
        assert tool_fact(item, targets, [turn(tool_calls=[change("refund", result="Nothing")])]) == (
            False, 'change_mode did not return a result that contains "saved".'
        )
        region = {**call("tool-1", "save_region", arguments={"region": "uk"}), "shown_arguments": {"region": "uk"}}
        assert tool_fact(item, targets, [turn(tool_calls=[region])]) == (True, "save_region was called with region = uk.")
        assert describe_check(item) == (
            'In every conversation, at some point, one of the tools "save_region" (with region = uk) or "change_mode"'
            ' (with mode = refund, returning a result that contains "saved") should be called.'
        )

    def test_only_a_tool_that_should_be_called_has_values(self):
        with pytest.raises(ValueError, match="only a tool that should be called"):
            Check(id="o", kind="only_tools", tools=[{"tool": "tool-1", "args": {"a": "b"}}])

    def test_a_missing_extra_tool_cannot_be_called_but_the_others_can(self):
        item = tool_check(tools=[{"tool": "tool-9", "tool_name": "gone"}])
        targets = resolve_targets(item, TOOLS)
        assert targets.problem is None and targets.missing_tools == ["gone"]
        assert tool_fact(item, targets, [turn(tool_calls=[call("tool-1", "save_region")])])[0] is True
        assert tool_fact(item, targets, [turn()]) == (
            False, 'None of "save_region" or "gone" was called. "gone" is not in the workflow that ran.'
        )

    def test_success_result_and_counts(self):
        targets = resolve_targets(tool_check(), TOOLS)
        failed = turn(tool_calls=[call("tool-1", "save_region", status="failed")])
        assert tool_fact(tool_check(succeeds=True), targets, [failed]) == (
            False, "save_region was called but did not succeed."
        )
        empty = turn(tool_calls=[call("tool-1", "save_region", result="No results found.")])
        assert tool_fact(tool_check(result_not_empty=True), targets, [empty]) == (False, "save_region returned no result.")
        saved = turn(tool_calls=[call("tool-1", "save_region", result="Region saved")])
        assert tool_fact(tool_check(result_contains="saved"), targets, [saved])[0] is True
        assert tool_fact(tool_check(result_contains="Saved"), targets, [saved]) == (
            False, 'save_region did not return a result that contains "Saved".'
        )
        twice = turn(tool_calls=[call("tool-1", "save_region"), call("tool-1", "save_region")])
        assert tool_fact(tool_check(max_calls=1), targets, [twice]) == (False, "save_region was called 2 times.")
        assert tool_fact(tool_check(min_calls=2), targets, [twice]) == (True, "save_region was called 2 times.")

    def test_a_count_anywhere_is_over_the_whole_conversation(self):
        item = tool_check(min_calls=2)
        targets = {"t": resolve_targets(item, TOOLS)}
        conversations = [[
            turn("a1", "a", 0, tool_calls=[call("tool-1", "save_region")]),
            turn("a2", "a", 1, tool_calls=[call("tool-1", "save_region")]),
        ]]
        (entry,) = grade_checks([item], conversations, targets, {})
        assert entry["result"]["status"] == "passed"
        assert entry["result"]["observed"] == "save_region was called 2 times."

    def test_only_these_tools(self):
        item = Check(id="o", kind="only_tools", tools=[{"tool": "tool-1"}], agent="agent-1", agent_name="Refund agent")
        targets = resolve_targets(item, TOOLS)
        ran = [{"id": "agent-1"}]
        assert only_tools_fact(item, targets, [turn(steps=ran, tool_calls=[call("tool-1", "save_region")])]) == (
            True, "Only these tools were used."
        )
        outside = turn(steps=ran, tool_calls=[call("tool-1", "save_region"), call("tool-3", "lookup")])
        assert only_tools_fact(item, targets, [outside]) == (False, '"lookup" was used too.')
        assert only_tools_fact(item, targets, [turn(steps=[{"id": "other"}])]) == (
            None, 'The agent "Refund agent" did not run on this turn.'
        )
        none = Check(id="n", kind="only_tools")
        none_targets = resolve_targets(none, TOOLS)
        assert only_tools_fact(none, none_targets, [turn(steps=ran)]) == (True, "No tool was used.")
        # As Tool Usage did: a turn no agent worked on has no tool calls to judge.
        assert only_tools_fact(none, none_targets, [turn()]) == (None, "No agent ran on this turn.")

    def test_tools_that_should_not_be_used_on_a_turn(self):
        item = Check(id="o", kind="only_tools", expect="should_not", tools=[{"tool": "tool-1"}, {"tool": "tool-3"}])
        targets = resolve_targets(item, TOOLS)
        assert turn_fact(item, targets, turn(tool_calls=[call("tool-3", "lookup")])) == (True, '"lookup" was used.')
        refused = {**call("tool-1", "save_region"), "refused": True}
        assert turn_fact(item, targets, turn(tool_calls=[refused])) == (
            True, '"save_region" was attempted but refused for missing details.'
        )
        assert turn_fact(item, targets, turn(tool_calls=[call("tool-2", "change_mode")])) == (
            False, 'None of "tool-1" and "tool-3" was used.'
        )

    def test_tools_that_should_not_be_used_over_a_conversation(self):
        item = Check(id="o", kind="only_tools", expect="should_not", tools=[{"tool": "tool-3", "tool_name": "lookup"}])
        targets = {"o": resolve_targets(item, TOOLS)}
        used = [[turn("a1", "a", 0), turn("a2", "a", 1, tool_calls=[call("tool-3", "lookup")])]]
        (entry,) = grade_checks([item], used, targets, {})
        assert entry["result"]["status"] == "failed"
        assert entry["result"]["observed"] == 'Turn 2: "lookup" was used.'
        (entry,) = grade_checks([item], [[turn("a1", "a", 0)]], targets, {})
        assert entry["result"]["status"] == "passed"

    def test_only_these_tools_over_a_conversation_whose_agent_never_ran(self):
        item = Check(id="o", kind="only_tools", tools=[{"tool": "tool-1"}], agent="agent-1", agent_name="Refund agent")
        (entry,) = grade_checks([item], [[turn("a1", "a", 0, steps=[{"id": "x"}])]], {"o": resolve_targets(item, TOOLS)}, {})
        assert entry["result"]["status"] == "not_evaluated"
        assert entry["result"]["comment"] == 'The agent "Refund agent" did not run in this conversation.'


class TestStepsRoutesAndValues:
    def test_any_step_of_a_type(self):
        item = Check(id="s", kind="step_runs", step_type="zendeskTicketNode", step_name="Zendesk ticket")
        targets = resolve_targets(item, TOOLS)
        assert targets.node_type == "zendeskTicketNode" and targets.problem is None
        ran = turn(steps=[{"id": "step-9", "type": "zendeskTicketNode", "status": "success"}])
        assert turn_fact(item, targets, ran) == (True, "The step ran.")
        missing = Check(id="s", kind="step_runs", step_type="smsNode", step_name="Sms")
        assert turn_fact(missing, resolve_targets(missing, TOOLS), ran) == (
            False, 'No step of type "Sms" is in the workflow that ran, so none ran.'
        )

    def test_any_router(self):
        item = Check(id="r", kind="route_taken", branch="a", branch_label="Refund")
        targets = resolve_targets(item, TOOLS)
        assert targets.problem is None and targets.node_ids == [] and targets.branch_known
        taken = turn(routes=[{"id": "router-7", "route": "a", "route_label": "Refund"}])
        assert turn_fact(item, targets, taken) == (True, 'The router took "Refund".')
        assert turn_fact(item, targets, turn()) == (False, "No router ran.")

    def test_a_value_in_the_run(self):
        item = Check(id="v", kind="value_equals", path="outputs.status", value="ok")
        assert turn_fact(item, Targets(), turn(values={"outputs.status": "ok"})) == (True, 'The value at "outputs.status" was "ok".')
        assert turn_fact(item, Targets(), turn(values={})) == (False, 'There was no value at "outputs.status".')
        against_reply = Check(id="v", kind="value_equals", path="outputs.status")
        assert turn_fact(against_reply, Targets(), turn(values={"outputs.status": "ok"}, expected_value={"text": "ok"}))[0] is True
        assert turn_fact(against_reply, Targets(), turn(values={"outputs.status": "ok"})) == (None, NO_EXPECTED_REPLY)

    def test_values_compare_as_field_equals_did(self):
        flag = Check(id="v", kind="value_equals", path="outputs.ok", value=True)
        assert turn_fact(flag, Targets(), turn(values={"outputs.ok": True}))[0] is True
        typed = Check(id="v", kind="value_equals", path="outputs.ok", value="true")
        assert turn_fact(typed, Targets(), turn(values={"outputs.ok": True}))[0] is True
        nested = Check(id="v", kind="value_equals", path="outputs.item", value='{"b":2,"a":1}')
        assert turn_fact(nested, Targets(), turn(values={"outputs.item": {"a": 1, "b": 2}}))[0] is True
        same = Check(id="v", kind="value_equals", path="outputs.item", value={"b": 2, "a": 1})
        assert turn_fact(same, Targets(), turn(values={"outputs.item": {"a": 1, "b": 2}}))[0] is True
        cased = Check(id="v", kind="value_equals", path="outputs.status", value="OK")
        assert turn_fact(cased, Targets(), turn(values={"outputs.status": "ok"}))[0] is False

    def test_paths_are_read_from_the_turn(self):
        checks = [
            Check(id="v", kind="value_equals", path=" outputs.status "),
            Check(id="g", kind="reply_grounded", context="run_value", context_path="trace.nodes.a.output"),
        ]
        assert check_paths(checks) == ["outputs.status", "trace.nodes.a.output"]
        payload = {"outputs": {"status": "ok", "items": [{"id": 4}]}}
        assert read_path(payload, "outputs.status") == "ok"
        assert read_path(payload, "outputs.items.0.id") == 4
        assert read_path(payload, "outputs.missing") is None


class TestGradedByAi:
    def test_a_pass_score(self):
        item = check(kind="reply_meets", rubric="Greet", when="every_turn", pass_score=0.8)
        conversations = [[turn("a1", "a", 0, reply="Hi")]]
        (entry,) = grade([item], conversations, {("c1", ("a1",)): JudgeVerdict(score=0.7, reason="Almost.")})
        assert entry["result"]["status"] == "failed"
        (entry,) = grade([item], conversations, {("c1", ("a1",)): JudgeVerdict(score=0.8, reason="Good.")})
        assert entry["result"]["status"] == "passed"

    @pytest.mark.parametrize(
        "context, fields, title",
        [
            ("tool_calls", {"tool_text": "[lookup -> 5 days]"}, "TOOL CALLS"),
            ("session", {"session_text": '{"region": "uk"}'}, "SESSION VALUES"),
            ("run_value", {"values": {"trace.nodes.a.output": "Refund in 5 days"}}, "VALUE"),
        ],
    )
    def test_what_else_the_grader_reads(self, context, fields, title):
        extra = {"context_path": "trace.nodes.a.output"} if context == "run_value" else {}
        item = check(kind="reply_grounded", context=context, rubric="Numbers must match", **extra)
        record = turn(message="Q", reply="A", **fields)
        system, user = judge_prompt(JudgeRequest(item, [record]))
        assert f"supported by the {title}" in system
        assert "Also: Numbers must match" in system
        assert f"{title}:\n" in user

    def test_a_missing_source_is_not_graded(self):
        item = check(kind="reply_grounded", context="tool_calls", level="turn", case_id="a1")
        (entry,) = grade([item], [[turn("a1", "a", 0, reply="x")]])
        assert entry["result"]["comment"] == "This turn called no tools to check against."


class TestAsTheOlderMethodsDid:
    @pytest.mark.parametrize("placement", [{}, {"level": "conversation", "conversation_ids": ["a"]}])
    def test_a_tool_check_for_any_agent_skips_turns_no_agent_ran(self, placement):
        item = tool_check(tool=None, tool_name="save_region", when="every_turn", **placement)
        targets = {"t": resolve_targets(item, TOOLS)}
        conversations = [[
            turn("a1", "a", 0, steps=[{"id": "agent-1"}], tool_calls=[call("tool-1", "save_region")]),
            turn("a2", "a", 1, steps=[{"id": "llm-node"}]),
        ]]
        (entry,) = grade_checks([item], conversations, targets, {})
        assert entry["result"]["status"] == "passed"

    def test_a_value_against_an_object_expected_reply(self):
        item = Check(id="v", kind="value_equals", path="outputs")
        expected = {"intent": "refund", "priority": "high"}
        record = turn(values={"outputs": {"priority": "high", "intent": "refund"}}, expected_value=expected)
        assert turn_fact(item, Targets(), record)[0] is True

    def test_an_output_is_not_read_while_a_person_is_awaited(self):
        item = Check(id="v", kind="value_equals", path="outputs.order_id", value="5")
        assert turn_fact(item, Targets(), turn(waiting_for_human=True)) == (
            None, "The turn was waiting for a person, so there was no output to read."
        )
        inputs = Check(id="v", kind="value_equals", path="inputs.region", value="uk")
        assert turn_fact(inputs, Targets(), turn(waiting_for_human=True, values={"inputs.region": "uk"}))[0] is True

    def test_a_count_over_several_tools_is_said_of_them_together(self):
        item = tool_check(tools=[{"tool": "tool-2", "tool_name": "change_mode"}], min_calls=3)
        targets = resolve_targets(item, TOOLS)
        calls = [call("tool-2", "change_mode"), call("tool-1", "save_region"), call("tool-1", "save_region")]
        assert tool_fact(item, targets, [turn(tool_calls=calls)]) == (
            True, '"save_region" or "change_mode" were called 3 times in all.'
        )

    def test_a_long_value_is_cut_for_the_grader(self):
        item = check(kind="reply_grounded", context="run_value", context_path="trace.big")
        record = turn(message="Q", reply="A", values={"trace.big": "x" * 20000})
        _, user = judge_prompt(JudgeRequest(item, [record]))
        assert user.count("x") == 16000


class TestNliAndSimilarity:
    def test_a_reply_can_stick_to_its_source_by_the_nli_model_or_similarity(self):
        nli = check(kind="reply_grounded", grader="nli", nli_model="cross-encoder/nli-roberta-base",
                    fail_on_contradiction=True, pass_score=0.7)
        assert nli.scored and not nli.ai_graded
        assert describe_check(nli) == (
            "On every turn, the reply should stick to the knowledge base, graded by the NLI model,"
            " failing any contradiction (passes at 0.7)."
        )
        similar = check(kind="reply_grounded", grader="similarity", embedding={"type": "openai", "model_name": "m"})
        assert describe_check(similar) == "On every turn, the reply should stick to the knowledge base, graded by text similarity."

    @pytest.mark.parametrize("fields, message", [
        ({"kind": "reply_meets", "rubric": "x", "grader": "nli"}, "another grader"),
        ({"kind": "reply_grounded", "grader": "nli", "rubric": "Prices"}, "extra instruction"),
        ({"kind": "reply_grounded", "grader": "nli", "llm_provider_id": "p"}, "AI grader"),
        ({"kind": "reply_grounded", "fail_on_contradiction": True}, "NLI model"),
        ({"kind": "reply_grounded", "grader": "nli", "embedding": {"type": "openai"}}, "text similarity"),
        ({"kind": "reply_grounded", "grader": "similarity", "embedding": {"type": "cohere"}}, "embedding model"),
        ({"kind": "reply_grounded", "grader": "similarity", "embedding": {"api_key": "sk"}}, "embedding model"),
    ])
    def test_each_grader_takes_only_its_own_settings(self, fields, message):
        with pytest.raises(ValueError, match=message):
            Check(id="c", **fields)

    def test_an_empty_reply_has_nothing_to_hold_to_its_source(self):
        item = check(kind="reply_grounded", context="expected_reply")
        conversations = [[turn("a1", "a", 0, reply="", expected="Monday")]]
        assert judge_requests([item], conversations, {"c1": Targets()}) == []
        (entry,) = grade([item], conversations)
        assert entry["result"]["status"] == "not_evaluated"
        assert entry["result"]["comment"] == "The reply was empty, so there was nothing to check."

    def test_a_grader_that_decides_itself_overrides_the_score(self):
        item = check(kind="reply_grounded", grader="nli", context="expected_reply")
        conversations = [[turn("a1", "a", 0, reply="x", expected="y")]]
        failed = JudgeVerdict(score=0.9, passed=False, reason="1/2 answer sections supported.")
        (entry,) = grade([item], conversations, {("c1", ("a1",)): failed})
        assert entry["result"]["status"] == "failed"
        skipped = JudgeVerdict(skipped="Not evaluated: the answer requires 12 claim groups.")
        (entry,) = grade([item], conversations, {("c1", ("a1",)): skipped})
        assert entry["result"]["status"] == "not_evaluated" and not entry["result"].get("error")


class TestGradingThatBroke:
    def test_a_turn_the_grader_did_not_answer_keeps_the_check_from_passing(self):
        item = check(kind="reply_meets", rubric="Be polite", when="every_turn")
        conversations = [[turn("a1", "a", 0, reply="x"), turn("a2", "a", 1, reply="y")]]
        verdicts = {("c1", ("a1",)): JudgeVerdict(score=1.0), ("c1", ("a2",)): JudgeVerdict(error=True, reason="Timed out.")}
        (entry,) = grade([item], conversations, verdicts)
        assert entry["result"]["status"] == "not_evaluated" and entry["result"]["error"]
        assert entry["result"]["comment"] == "Turn 2: Timed out."

    def test_a_failure_stands_whatever_the_grader_missed(self):
        item = check(kind="reply_meets", rubric="Be polite", when="every_turn")
        conversations = [[turn("a1", "a", 0, reply="x"), turn("a2", "a", 1, reply="y")]]
        verdicts = {("c1", ("a1",)): JudgeVerdict(score=0.0), ("c1", ("a2",)): JudgeVerdict(error=True)}
        (entry,) = grade([item], conversations, verdicts)
        assert entry["result"]["status"] == "failed"

    def test_a_check_that_broke_keeps_its_conversation_from_passing(self):
        broke = check(id="judge", kind="reply_meets", rubric="Be polite", when="every_turn")
        passes = check(id="words", kind="reply_mentions", text="x", match=None)
        conversations = [[turn("a1", "a", 0, reply="x")]]
        planned = grade([broke, passes], conversations, {("judge", ("a1",)): JudgeVerdict(error=True)})
        assert [entry["result"]["status"] for entry in planned] == ["not_evaluated", "passed"]
        assert conversation_verdicts(planned, conversations) == {"a": "not_evaluated"}

    def test_an_unread_turn_keeps_a_check_it_could_change_from_passing(self):
        unread = TurnRecord(case_id="a2", conversation_key="a", turn_index=1, position=1, message="m",
                            ran=False, skip_reason=UNREADABLE_TURN)
        conversations = [[turn("a1", "a", 0, reply="Try RingGo"), unread]]
        # Seen at some point stands; never or on every turn could hide in the unread turn.
        (seen,) = grade([check(kind="reply_mentions", text="RingGo", match=None)], conversations)
        assert seen["result"]["status"] == "passed"
        (never,) = grade([check(kind="reply_mentions", text="JustPark", match=None, expect="should_not")], conversations)
        assert never["result"]["status"] == "not_evaluated" and never["result"]["error"]
        assert never["result"]["comment"] == f"Turn 2: {UNREADABLE_TURN}"
