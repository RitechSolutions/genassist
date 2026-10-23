"""Each older method next to the checks it becomes, on the same turns: a check never passes what its method failed.

The older methods grade as the runner graded them. Their checks come from the conversion and are graded from
the same turn, read as the run reads it.
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.services import test_suite as ts
from app.services.evaluation_nli import NLIClaimResult, NLIScoreResult
from app.services.method_checks import convert_methods
from app.services.run_conversations import turn_verdict
from app.services.scenario_checks import (
    JudgeRequest,
    JudgeVerdict,
    check_paths,
    conversation_verdicts,
    grade_checks,
    judge_requests,
    parse_checks_config,
    resolve_targets,
)

REGISTRY = ts.SimpleEvaluatorRegistry()

CATALOG = {
    "agents": [
        {"id": "agent-1", "label": "Support", "tools": [
            {"id": "tool-1", "name": "lookup_order", "label": "Lookup order"},
            {"id": "tool-2", "name": "create_ticket", "label": "Create ticket"},
        ]},
    ],
    "action_nodes": [
        {"id": "step-1", "label": "Send email", "type": "emailNode"},
        {"id": "step-2", "label": "Send email", "type": "emailNode"},
        {"id": "step-3", "label": "Log", "type": "logNode"},
    ],
    "routers": [
        {"id": "router-1", "label": "Intent", "branches": [
            {"value": "case-1", "label": "Refund"}, {"value": "case-2", "label": "Refund"}, {"value": "default", "label": "Default"},
        ]},
    ],
}


def case(case_id="c1", expected=None, message="Hi", conversation="conv-1", turn_index=0):
    return SimpleNamespace(
        id=case_id, expected_output=expected, input_data={"message": message},
        source_conversation_id=conversation, turn_index=turn_index,
    )


def trace(output=None, *, nodes=None, errors=None, tool_events=None, routes=None):
    status = dict(nodes or {})
    for node_id, (route, label) in (routes or {}).items():
        status[node_id] = {"type": "switchNode", "name": "Intent", "status": "success",
                           "output": {"route": route, "label": label}}
    return {"output": output, "state": {"errors": errors or [], "nodeExecutionStatus": status, "input": {}},
            "tool_events": tool_events or []}


def event(tool_id, tool_name, *, status="succeeded", arguments=None, error=None, agent="agent-1", result="ok"):
    return {"event_id": f"{tool_id}-{status}-{error}", "tool_id": tool_id, "tool_name": tool_name, "agent_id": agent,
            "arguments": arguments or {}, "status": status, "error": error, "result": result}


def old(technique, config, turn_case, turn_trace):
    """The turn's verdict from one older method, as the run stored and read it."""
    metrics = asyncio.run(REGISTRY.evaluate(
        [technique], inputs={"message": turn_case.input_data["message"]}, outputs=turn_trace.get("output"),
        reference_outputs=turn_case.expected_output, execution_trace=turn_trace,
        technique_configs={technique: config},
    ))
    return turn_verdict("scored", metrics, [])


def records(turns, checks):
    paths = check_paths(checks)
    made = []
    for position, (turn_case, turn_trace) in enumerate(turns):
        record = ts.turn_record(turn_case, turn_trace, {"message": turn_case.input_data["message"]}, {}, paths)
        record.position = position
        made.append(record)
    return made


def new(technique, config, turns, catalog=CATALOG, verdicts=None):
    """The conversation's verdict from the checks the method became."""
    conversion = convert_methods([technique], {technique: config}, catalog)
    checks = parse_checks_config({"checks": conversion.checks}).checks
    group = records(turns, checks)
    targets = {check.id: resolve_targets(check, catalog) for check in checks}
    planned = grade_checks(checks, [group], targets, verdicts or {})
    return conversation_verdicts(planned, [group])[group[0].conversation_key]


def same(technique, config, turn_case, turn_trace, catalog=CATALOG):
    return old(technique, config, turn_case, turn_trace), new(technique, config, [(turn_case, turn_trace)], catalog)


class TestReplies:
    @pytest.mark.parametrize("reply, verdict", [
        ("Refund approved", "passed"), ("  Refund approved ", "passed"), ("refund approved", "failed"),
    ])
    def test_exact_match_keeps_case(self, reply, verdict):
        turn_case = case(expected="Refund approved")
        assert same("exact_match", {}, turn_case, trace({"message": reply})) == (verdict, verdict)

    @pytest.mark.parametrize("reply, verdict", [("Die STRASSE ist zu", "passed"), ("Die Straße ist zu", "passed"), ("Zu", "failed")])
    def test_contains_ignores_case(self, reply, verdict):
        turn_case = case(expected="strasse")
        assert same("contains", {}, turn_case, trace({"message": reply})) == (verdict, verdict)

    @pytest.mark.parametrize("reply", ["Try STRASSE", "Die Straße"])
    def test_does_not_contain_finds_the_words_in_any_case(self, reply):
        assert same("not_contains", {"phrases": ["strasse"]}, case(), trace({"message": reply})) == ("failed", "failed")

    def test_does_not_contain_fails_the_conversation_on_any_turn(self):
        turns = [(case("c1", turn_index=0), trace({"message": "Hello"})),
                 (case("c2", turn_index=1), trace({"message": "Try JustPark"}))]
        assert [old("not_contains", {"phrases": ["JustPark"]}, *turn) for turn in turns] == ["passed", "failed"]
        assert new("not_contains", {"phrases": ["JustPark"]}, turns) == "failed"

    @pytest.mark.parametrize("output, verdict", [
        ({"a": 1}, "passed"),
        ({"a": 1, "debug": "x"}, "failed"),
        ({"message": '{"a": 1}'}, "failed"),
        ("Hello", "failed"),
    ])
    def test_json_match_compares_the_whole_output(self, output, verdict):
        turn_case = case(expected={"a": 1})
        assert same("json_match", {}, turn_case, trace(output)) == (verdict, verdict)

    def test_json_match_tells_true_from_one(self):
        # Python took True for 1; the check does not, which is stricter.
        assert same("json_match", {}, case(expected={"a": 1}), trace({"a": True})) == ("passed", "failed")

    @pytest.mark.parametrize("config, output, verdict", [
        ({"field": "outputs.status", "expected": "ok"}, {"status": "ok"}, "passed"),
        ({"field": "outputs.status", "expected": "ok"}, {"status": "OK"}, "failed"),
        ({"field": "outputs.status", "expected": "ok"}, {}, "failed"),
        ({"field": "reference_outputs", "expected": "Hello"}, {}, "passed"),
    ])
    def test_field_equals(self, config, output, verdict):
        turn_case = case(expected={"value": "Hello"})
        assert same("field_equals", config, turn_case, trace(output)) == (verdict, verdict)

    def test_no_errors_fails_on_a_step_error(self):
        broken = trace({"message": "Hi"}, nodes={"step-3": {"type": "logNode", "name": "Log", "status": "failed", "error": "boom"}})
        assert same("no_errors", {}, case(), broken) == ("failed", "failed")
        assert same("no_errors", {}, case(), trace({"message": "Hi"})) == ("passed", "passed")


def nli(entail_scores, contradiction=0.0):
    claims = tuple(NLIClaimResult(text=f"claim {i}", entail_score=score, contradiction_score=contradiction, verdict="x")
                   for i, score in enumerate(entail_scores))
    return NLIScoreResult(entail_score=min(entail_scores), contradiction_score=contradiction, verdict="x",
                          model_name="nli-test", chunks_evaluated=1, claims_evaluated=len(claims),
                          total_claims=len(claims), pairs_evaluated=len(claims), claim_results=claims)


def locally(technique, config, turn_case, turn_trace):
    """The conversation's verdict when the check is graded as its method graded it."""
    conversion = convert_methods([technique], {technique: config}, CATALOG)
    checks = parse_checks_config({"checks": conversion.checks}).checks
    group = records([(turn_case, turn_trace)], checks)
    targets = {check.id: resolve_targets(check, CATALOG) for check in checks}
    service = SimpleNamespace(evaluators=REGISTRY)
    verdicts = {
        request.key: asyncio.run(ts.TestSuiteService._grade_locally(service, request))
        for request in judge_requests(checks, [group], targets)
    }
    planned = grade_checks(checks, [group], targets, verdicts)
    return conversation_verdicts(planned, [group])[group[0].conversation_key]


class TestGraders:
    @pytest.mark.parametrize("scores, contradiction, config", [
        ([0.9, 0.6], 0.0, {}),
        ([0.9, 0.4], 0.0, {}),
        ([0.9, 0.4], 0.0, {"min_entail_score": 0.3}),
        ([0.9, 0.6], 0.0, {"min_entail_score": 0.8}),
        ([0.9, 0.9], 0.7, {"fail_on_contradiction": True}),
        ([0.9, 0.9], 0.7, {}),
    ])
    def test_nli_grades_each_part_of_the_reply_as_before(self, scores, contradiction, config):
        turn_case = case(expected="It ships on Monday.")
        turn_trace = trace({"message": "It ships Monday. Track it online."})
        with patch.object(ts.evaluation_nli_model, "score_evidence", return_value=nli(scores, contradiction)):
            assert old("nli_eval", config, turn_case, turn_trace) == locally("nli_eval", config, turn_case, turn_trace)

    def test_nli_says_what_it_could_not_grade_as_before(self):
        too_long = nli([0.9])
        too_long = NLIScoreResult(**{**too_long.__dict__, "coverage_complete": False, "total_claims": 12})
        turn_case = case(expected="It ships on Monday.")
        with patch.object(ts.evaluation_nli_model, "score_evidence", return_value=too_long):
            assert old("nli_eval", {}, turn_case, trace({"message": "x"})) == "not_evaluated"
            assert locally("nli_eval", {}, turn_case, trace({"message": "x"})) == "not_evaluated"

    @pytest.mark.parametrize("score, config", [(0.62, {}), (0.62, {"min_score": 0.8}), (0.3, {"min_score": 0.2})])
    def test_similarity_grades_with_its_threshold_as_before(self, score, config):
        turn_case = case(expected="It ships on Monday.")
        turn_trace = trace({"message": "It ships Monday."})
        with patch.object(REGISTRY, "_embedding_provenance_score", AsyncMock(return_value=score)):
            assert old("provenance_eval", config, turn_case, turn_trace) == locally(
                "provenance_eval", config, turn_case, turn_trace
            )

    def test_a_grader_that_did_not_answer_never_passes_the_conversation(self):
        turns = [(case("c1", expected="A", turn_index=0), trace({"message": "A"})),
                 (case("c2", expected="B", turn_index=1), trace({"message": "B"}))]
        config = {"rules": [{"rubric": "Be polite"}]}
        conversion = convert_methods(["llm_judge", "exact_match"], {"llm_judge": config}, CATALOG)
        checks = parse_checks_config({"checks": conversion.checks}).checks
        group = records(turns, checks)
        targets = {check.id: resolve_targets(check, CATALOG) for check in checks}
        judge = next(check for check in checks if check.kind == "reply_meets")
        verdicts = {(judge.id, ("c1",)): JudgeVerdict(score=1.0), (judge.id, ("c2",)): JudgeVerdict(error=True, reason="Timed out.")}
        planned = grade_checks(checks, [group], targets, verdicts)
        rule = next(entry for entry in planned if entry["rule_id"] == judge.id)
        assert rule["result"]["status"] == "not_evaluated" and rule["result"]["error"]
        assert rule["result"]["comment"] == "Turn 2: Timed out."
        assert conversation_verdicts(planned, [group]) == {"conv-1": "not_evaluated"}

    def test_without_any_ai_grader_the_conversation_is_not_passed(self):
        turn_case = case(expected="A")
        conversion = convert_methods(["llm_judge", "exact_match"], {"llm_judge": {"rubric": "Be polite"}}, CATALOG)
        checks = parse_checks_config({"checks": conversion.checks}).checks
        group = records([(turn_case, trace({"message": "A"}))], checks)
        targets = {check.id: resolve_targets(check, CATALOG) for check in checks}
        unreachable = {request.key: JudgeVerdict(error=True, reason="The AI grader could not be reached.")
                       for request in judge_requests(checks, [group], targets)}
        planned = grade_checks(checks, [group], targets, unreachable)
        assert conversation_verdicts(planned, [group]) == {"conv-1": "not_evaluated"}


def tools(*rules):
    return {"rules": [{"id": f"r{index}", **rule} for index, rule in enumerate(rules)]}


AGENT_RAN = {"agent-1": {"type": "agentNode", "name": "Support", "status": "success"}}


class TestRules:
    def test_a_tool_missing_from_the_version_that_ran_fails_a_should(self):
        config = tools({"tool_ids": ["tool-9"], "operator": "all"})
        turn_trace = trace({"message": "Hi"}, nodes=AGENT_RAN, tool_events=[event("tool-1", "lookup_order")])
        catalog = {**CATALOG, "agents": [{**CATALOG["agents"][0], "tools": CATALOG["agents"][0]["tools"][:1]}]}
        assert old("tool_used", config, case(), turn_trace) == "failed"
        assert new("tool_used", config, [(case(), turn_trace)], catalog) == "failed"

    def test_refused_attempts_count_toward_the_most_calls(self):
        config = tools({"tool_ids": ["tool-1"], "operator": "all", "max_calls": 1})
        refused = event("tool-1", "lookup_order", status="failed", error="required parameters are missing or empty: id")
        turn_trace = trace({"message": "Hi"}, nodes=AGENT_RAN, tool_events=[event("tool-1", "lookup_order"), refused])
        assert same("tool_used", config, case(), turn_trace) == ("failed", "failed")

    @pytest.mark.parametrize("value, verdict", [("Paris", "passed"), ("paris", "failed")])
    def test_tool_values_keep_their_case(self, value, verdict):
        config = tools({"tool_ids": ["tool-1"], "operator": "all", "per_tool": {"tool-1": {"expected_args": {"city": "Paris"}}}})
        turn_trace = trace({"message": "Hi"}, nodes=AGENT_RAN, tool_events=[event("tool-1", "lookup_order", arguments={"city": value})])
        assert same("tool_used", config, case(), turn_trace) == (verdict, verdict)

    @pytest.mark.parametrize("calls, verdict", [
        ([("tool-1", "lookup_order", {"id": "7"}, "ok")], "passed"),
        ([("tool-2", "create_ticket", {"subject": "refund"}, "created")], "passed"),
        ([("tool-1", "lookup_order", {"id": "8"}, "ok")], "failed"),
        # Each tool is held to its own values, not to another tool's.
        ([("tool-2", "create_ticket", {"id": "7"}, "created")], "failed"),
        ([("tool-2", "create_ticket", {"subject": "refund"}, "error")], "failed"),
    ])
    def test_any_of_several_tools_holds_each_to_its_own_checks(self, calls, verdict):
        config = tools({"tool_ids": ["tool-1", "tool-2"], "operator": "any", "per_tool": {
            "tool-1": {"expected_args": {"id": "7"}},
            "tool-2": {"expected_args": {"subject": "refund"}, "result_contains": "created"},
        }})
        events = [event(tool, name, arguments=arguments, result=result) for tool, name, arguments, result in calls]
        turn_trace = trace({"message": "Hi"}, nodes=AGENT_RAN, tool_events=events)
        assert same("tool_used", config, case(), turn_trace) == (verdict, verdict)

    def test_only_these_tools_catches_an_agent_in_a_sub_workflow(self):
        config = tools({"tool_ids": ["tool-1"], "operator": "only"})
        turn_trace = trace({"message": "Hi"}, tool_events=[event("tool-2", "create_ticket")])
        assert same("tool_used", config, case(), turn_trace) == ("failed", "failed")

    def test_a_branch_is_matched_by_its_value_before_a_label_it_shares(self):
        config = {"rules": [{"id": "r", "router": "router-1", "expected": "case-1"}]}
        took_other = trace({"message": "Hi"}, routes={"router-1": ("case-2", "Refund")})
        assert same("route_taken", config, case(), took_other) == ("failed", "failed")
        took_it = trace({"message": "Hi"}, routes={"router-1": ("case-1", "Refund")})
        assert same("route_taken", config, case(), took_it) == ("passed", "passed")

    def test_a_label_on_two_steps_means_either(self):
        config = {"rules": [{"id": "r", "node": "Send email", "should_fire": False}]}
        second = trace({"message": "Hi"}, nodes={"step-2": {"type": "emailNode", "name": "Send email", "status": "success"}})
        assert same("action_taken", config, case(), second) == ("failed", "failed")

    def test_a_step_in_a_loop_is_judged_by_its_latest_run(self):
        config = {"rules": [{"id": "r", "node": "step-3", "should_fire": True}]}
        loop = trace({"message": "Hi"}, nodes={
            "step-3_0": {"type": "logNode", "name": "Log", "status": "success"},
            "step-3": {"type": "logNode", "name": "Log", "status": "failed", "error": "boom"},
        })
        assert same("action_taken", config, case(), loop) == ("failed", "failed")

    def test_a_step_that_is_not_of_its_type_is_left_out_as_never_holding(self):
        conversion = convert_methods(["action_taken"], {"action_taken": {"rules": [
            {"id": "r", "node": "step-3", "node_type": "emailNode", "should_fire": True},
        ]}}, CATALOG)
        assert conversion.checks == []
        assert conversion.left_out == ['Action Taken "step-3": it is not a "Email" step, so this rule never held.']
