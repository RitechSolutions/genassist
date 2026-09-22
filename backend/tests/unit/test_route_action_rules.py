"""Unit tests for route/action rule evaluation and scoping (pure logic)."""

import pytest

from app.services.route_action_rules import (
    ActionRule,
    RouteRule,
    ScopeSlice,
    action_observations,
    describe_action_rule,
    describe_route_rule,
    grade_action_rule,
    grade_route_rule,
    parse_action_config,
    parse_route_config,
    plan_action_results,
    plan_route_results,
    route_observations,
)
from app.services.rule_scopes import RULE_FAILED, RULE_NOT_EVALUATED, RULE_PASSED


def _router(route, *, node_id="router-1", label="Escalation Router"):
    return {"id": node_id, "label": label, "route": route}


def _node(node_id="zendesk-1", *, label="Create Ticket", node_type="httpNode",
          status="success", error=None):
    return {"id": node_id, "label": label, "type": node_type, "status": status, "error": error}


def _slice(*turns, total=None):
    return ScopeSlice(turns=list(turns), total_turns=total if total is not None else len(turns))


# ---- config parsing --------------------------------------------------------

def test_legacy_single_route_config_becomes_one_every_turn_rule():
    cfg = parse_route_config({"router": "router-1", "expected": "escalate"})
    assert len(cfg.rules) == 1
    rule = cfg.rules[0]
    assert rule.router == "router-1"
    assert rule.expected == "escalate"
    assert rule.scope == "every_turn"
    assert rule.id == "route-1"


def test_legacy_route_config_accepts_node_as_the_router():
    cfg = parse_route_config({"node": "router-1", "expected": "escalate"})
    assert cfg.rules[0].router == "router-1"


def test_route_rules_keep_their_stored_ids_and_scopes():
    cfg = parse_route_config({"rules": [
        {"id": "abc", "router": "r1", "expected": "yes", "scope": "conversation"},
        {"router": "r2", "expected": "no"},
    ]})
    assert [rule.id for rule in cfg.rules] == ["abc", "route-2"]
    assert [rule.scope for rule in cfg.rules] == ["conversation", "every_turn"]


def test_route_rule_without_expected_is_dropped():
    cfg = parse_route_config({"rules": [{"router": "r1", "expected": "  "}]})
    assert cfg.rules == []


def test_action_config_requires_a_node_or_node_type():
    assert parse_action_config({"should_fire": True}).rules == []
    assert len(parse_action_config({"node_type": "httpNode"}).rules) == 1


def test_specific_turn_rule_requires_a_target():
    with pytest.raises(ValueError):
        parse_route_config({"rules": [
            {"router": "r1", "expected": "yes", "scope": "specific_turn"},
        ]})


def test_specific_turn_rule_accepts_a_conversation_turn_target():
    cfg = parse_action_config({"rules": [{
        "node": "zendesk-1", "scope": "specific_turn",
        "target_source_conversation_id": "conv-1", "target_turn_index": 2,
    }]})
    assert cfg.rules[0].scope == "specific_turn"


def test_unknown_scope_rejected():
    with pytest.raises(ValueError):
        parse_route_config({"rules": [{"router": "r1", "expected": "yes", "scope": "sometimes"}]})


def test_duplicate_rule_ids_rejected():
    with pytest.raises(ValueError):
        parse_route_config({"rules": [
            {"id": "x", "router": "r1", "expected": "a"},
            {"id": "x", "router": "r2", "expected": "b"},
        ]})


# ---- trace observations ----------------------------------------------------

def test_route_observations_read_the_branch_each_router_took():
    trace = {"nodes_by_type": {"routerNode": [
        {"id": "router-1", "label": "Escalation Router", "output": {"route": "escalate"}},
    ]}}
    assert route_observations(trace) == [
        {"id": "router-1", "label": "Escalation Router", "route": "escalate"}
    ]


def test_action_observations_keep_status_and_error():
    trace = {"nodes": {"n1": {"id": "n1", "label": "Create Ticket", "type": "httpNode",
                             "status": "failed", "error": "boom", "output": {"big": "payload"}}}}
    assert action_observations(trace) == [
        {"id": "n1", "label": "Create Ticket", "type": "httpNode",
         "status": "failed", "error": "boom"}
    ]


# ---- route grading ---------------------------------------------------------

def test_route_passes_when_the_expected_branch_was_taken():
    rule = RouteRule(id="r", router="router-1", expected="escalate")
    result = grade_route_rule(rule, _slice([_router("escalate")]), {}, 1)
    assert result["status"] == RULE_PASSED
    assert result["observed"] == "escalate"


def test_route_fails_and_names_the_branch_that_was_taken():
    rule = RouteRule(id="r", router="router-1", expected="escalate")
    result = grade_route_rule(rule, _slice([_router("answer")]), {}, 1)
    assert result["status"] == RULE_FAILED
    assert "'answer'" in result["comment"]


def test_route_reports_a_router_that_never_ran():
    rule = RouteRule(id="r", router="router-1", expected="escalate")
    result = grade_route_rule(rule, _slice([]), {"router-1": "Escalation Router"}, 1)
    assert result["status"] == RULE_FAILED
    assert result["comment"] == "Router 'Escalation Router' did not run."


def test_route_over_a_conversation_passes_on_a_single_hit():
    rule = RouteRule(id="r", router="router-1", expected="escalate", scope="conversation")
    scope = _slice([_router("answer")], [_router("escalate")], [_router("answer")])
    result = grade_route_rule(rule, scope, {}, 1)
    assert result["status"] == RULE_PASSED
    assert "1 of 3 turns" in result["comment"]


def test_route_over_a_conversation_fails_when_never_taken():
    rule = RouteRule(id="r", router="router-1", expected="escalate", scope="conversation")
    result = grade_route_rule(rule, _slice([_router("answer")], [_router("answer")]), {}, 1)
    assert result["status"] == RULE_FAILED
    assert "in this conversation" in result["comment"]


def test_route_names_an_unlabelled_router_that_ran_from_the_graph():
    """A router with no label in the trace still reports what it took, not "did not run"."""
    rule = RouteRule(id="r", router="router-1", expected="escalate")
    unlabelled = {"id": "router-1", "label": None, "route": "answer"}
    result = grade_route_rule(rule, _slice([unlabelled]), {"router-1": "Escalation Router"}, 1)
    assert result["status"] == RULE_FAILED
    assert result["comment"] == (
        "Expected route 'escalate' on router 'Escalation Router', took 'answer'."
    )


def test_route_without_a_router_matches_any_router():
    rule = RouteRule(id="r", expected="escalate")
    result = grade_route_rule(rule, _slice([_router("escalate", node_id="other")]), {}, 1)
    assert result["status"] == RULE_PASSED


def test_route_not_evaluated_when_no_turn_in_scope_produced_a_trace():
    rule = RouteRule(id="r", router="router-1", expected="escalate", scope="conversation")
    result = grade_route_rule(rule, ScopeSlice(turns=[], total_turns=3), {}, 1)
    assert result["status"] == RULE_NOT_EVALUATED
    assert result["passed"] is False


# ---- action grading --------------------------------------------------------

def test_action_passes_when_the_node_completed():
    rule = ActionRule(id="a", node="zendesk-1")
    result = grade_action_rule(rule, _slice([_node()]), {}, 1)
    assert result["status"] == RULE_PASSED
    assert result["observed"] == "completed"


def test_action_fails_when_the_node_did_not_run():
    rule = ActionRule(id="a", node="zendesk-1")
    result = grade_action_rule(rule, _slice([]), {"zendesk-1": "Create Ticket"}, 1)
    assert result["status"] == RULE_FAILED
    assert result["observed"] == "did not run"


def test_action_reports_a_node_that_errored():
    rule = ActionRule(id="a", node="zendesk-1")
    result = grade_action_rule(rule, _slice([_node(status="failed", error="boom")]), {}, 1)
    assert result["status"] == RULE_FAILED
    assert result["observed"] == "ran with an error"


def test_ticket_created_once_per_conversation_passes():
    """The motivating case: a side effect that must happen once, not every turn."""
    rule = ActionRule(id="a", node="zendesk-1", scope="conversation")
    scope = _slice([_node(status="skipped")], [_node()], [_node(status="skipped")])
    result = grade_action_rule(rule, scope, {}, 1)
    assert result["status"] == RULE_PASSED
    assert "1 of 3 turns" in result["comment"]


def test_action_over_a_conversation_fails_when_it_never_completed():
    rule = ActionRule(id="a", node="zendesk-1", scope="conversation")
    result = grade_action_rule(rule, _slice([_node(status="skipped")], [_node(status="skipped")]), {}, 1)
    assert result["status"] == RULE_FAILED
    assert "at least once" in result["comment"]


def test_must_not_fire_over_a_conversation_fails_on_any_completion():
    rule = ActionRule(id="a", node="zendesk-1", should_fire=False, scope="conversation")
    result = grade_action_rule(rule, _slice([_node(status="skipped")], [_node()]), {}, 1)
    assert result["status"] == RULE_FAILED


def test_must_not_fire_passes_and_explains_a_node_that_never_ran():
    rule = ActionRule(id="a", node="zendesk-1", should_fire=False)
    result = grade_action_rule(rule, _slice([]), {"zendesk-1": "Create Ticket"}, 1)
    assert result["status"] == RULE_PASSED
    assert result["show_comment_on_pass"] is True


def test_action_matches_by_node_type():
    rule = ActionRule(id="a", node_type="httpNode")
    result = grade_action_rule(rule, _slice([_node(node_id="other", node_type="httpNode")]), {}, 1)
    assert result["status"] == RULE_PASSED


def test_action_not_evaluated_when_no_turn_in_scope_produced_a_trace():
    rule = ActionRule(id="a", node="zendesk-1", scope="conversation")
    result = grade_action_rule(rule, ScopeSlice(turns=[], total_turns=2), {}, 1)
    assert result["status"] == RULE_NOT_EVALUATED


# ---- scope planning --------------------------------------------------------

_TURNS = [
    {"id": "case-1", "source_conversation_id": "conv-1", "turn_index": 0},
    {"id": "case-2", "source_conversation_id": "conv-1", "turn_index": 1},
]
_GROUPS = [["case-1", "case-2"]]


def test_every_turn_rule_is_graded_once_per_turn():
    rules = parse_action_config({"rules": [{"node": "zendesk-1"}]}).rules
    planned = plan_action_results(
        rules, _TURNS, _GROUPS, {"case-1": [_node()], "case-2": []}, {}
    )
    assert [entry["case_id"] for entry in planned] == ["case-1", "case-2"]
    assert [entry["result"]["status"] for entry in planned] == [RULE_PASSED, RULE_FAILED]


def test_conversation_rule_is_graded_once_for_the_whole_conversation():
    rules = parse_action_config({"rules": [{"node": "zendesk-1", "scope": "conversation"}]}).rules
    planned = plan_action_results(
        rules, _TURNS, _GROUPS, {"case-1": [], "case-2": [_node()]}, {}
    )
    assert len(planned) == 1
    entry = planned[0]
    assert entry["case_id"] is None
    assert entry["source_conversation_id"] == "conv-1"
    assert entry["result"]["status"] == RULE_PASSED


def test_conversation_rule_is_not_evaluated_when_no_turn_ran():
    rules = parse_route_config(
        {"rules": [{"router": "router-1", "expected": "escalate", "scope": "conversation"}]}
    ).rules
    planned = plan_route_results(rules, _TURNS, _GROUPS, {}, {})
    assert planned[0]["result"]["status"] == RULE_NOT_EVALUATED


def test_specific_turn_rule_targets_one_turn_by_conversation_and_index():
    rules = parse_route_config({"rules": [{
        "router": "router-1", "expected": "escalate", "scope": "specific_turn",
        "target_source_conversation_id": "conv-1", "target_turn_index": 1,
    }]}).rules
    planned = plan_route_results(
        rules, _TURNS, _GROUPS,
        {"case-1": [_router("answer")], "case-2": [_router("escalate")]}, {},
    )
    assert len(planned) == 1
    assert planned[0]["case_id"] == "case-2"
    assert planned[0]["result"]["status"] == RULE_PASSED


def test_specific_turn_rule_reports_a_target_missing_from_the_run():
    rules = parse_route_config({"rules": [{
        "router": "router-1", "expected": "escalate", "scope": "specific_turn",
        "target_source_conversation_id": "conv-9", "target_turn_index": 0,
    }]}).rules
    planned = plan_route_results(rules, _TURNS, _GROUPS, {}, {})
    assert planned[0]["result"]["status"] == RULE_NOT_EVALUATED
    assert planned[0]["result"]["comment"] == "Target turn 1 not found in this run."


def test_specific_turn_rule_can_target_several_turns():
    """The multi-select case: one rule, one result per turn it named."""
    rules = parse_action_config({"rules": [{
        "node": "zendesk-1", "scope": "specific_turn",
        "target_source_conversation_id": "conv-1", "target_turn_indexes": [0, 1],
    }]}).rules
    planned = plan_action_results(
        rules, _TURNS, _GROUPS, {"case-1": [_node()], "case-2": []}, {}
    )
    assert [entry["case_id"] for entry in planned] == ["case-1", "case-2"]
    assert [entry["result"]["status"] for entry in planned] == [RULE_PASSED, RULE_FAILED]


def test_multi_turn_targets_report_only_the_turn_that_is_missing():
    rules = parse_route_config({"rules": [{
        "router": "router-1", "expected": "escalate", "scope": "specific_turn",
        "target_source_conversation_id": "conv-1", "target_turn_indexes": [1, 7],
    }]}).rules
    planned = plan_route_results(
        rules, _TURNS, _GROUPS, {"case-2": [_router("escalate")]}, {}
    )
    assert [entry["result"]["status"] for entry in planned] == [RULE_PASSED, RULE_NOT_EVALUATED]
    assert planned[1]["result"]["comment"] == "Target turn 8 not found in this run."


def test_case_ids_and_turn_indexes_for_the_same_turns_grade_once():
    """The builder writes both shapes; a turn must not be graded twice."""
    rules = parse_action_config({"rules": [{
        "node": "zendesk-1", "scope": "specific_turn",
        "target_source_conversation_id": "conv-1",
        "target_case_ids": ["case-1", "case-2"],
        "target_turn_indexes": [0, 1],
    }]}).rules
    planned = plan_action_results(
        rules, _TURNS, _GROUPS, {"case-1": [_node()], "case-2": [_node()]}, {}
    )
    assert [entry["case_id"] for entry in planned] == ["case-1", "case-2"]


def test_re_imported_turns_resolve_through_the_conversation_pair():
    """Stale case ids from an import still grade via (conversation, turn)."""
    rules = parse_action_config({"rules": [{
        "node": "zendesk-1", "scope": "specific_turn",
        "target_source_conversation_id": "conv-1",
        "target_case_ids": ["gone-1", "gone-2"],
        "target_turn_indexes": [0, 1],
    }]}).rules
    planned = plan_action_results(
        rules, _TURNS, _GROUPS, {"case-1": [_node()], "case-2": [_node()]}, {}
    )
    assert [entry["case_id"] for entry in planned] == ["case-1", "case-2"]
    assert all(entry["result"]["status"] == RULE_PASSED for entry in planned)


def test_multi_turn_rule_needs_at_least_one_turn():
    with pytest.raises(ValueError):
        parse_route_config({"rules": [{
            "router": "r1", "expected": "yes", "scope": "specific_turn",
            "target_source_conversation_id": "conv-1", "target_turn_indexes": [],
        }]})


def test_manual_cases_place_a_conversation_result_on_the_first_turn():
    turns = [{"id": "case-1", "source_conversation_id": None, "turn_index": None}]
    rules = parse_action_config({"rules": [{"node": "zendesk-1", "scope": "conversation"}]}).rules
    planned = plan_action_results(rules, turns, [["case-1"]], {"case-1": [_node()]}, {})
    assert planned[0]["case_id"] == "case-1"
    assert planned[0]["source_conversation_id"] is None


# ---- descriptions ----------------------------------------------------------

def test_description_names_every_targeted_turn():
    rule = ActionRule(
        id="a", node="zendesk-1", scope="specific_turn",
        target_source_conversation_id="conv-1", target_turn_indexes=[0, 2],
    )
    assert describe_action_rule(rule, {"zendesk-1": "Create Ticket"}) == (
        '"Create Ticket" must complete on turns 1, 3.'
    )


def test_route_description_uses_labels_and_scope():
    rule = RouteRule(id="r", router="router-1", expected="escalate", scope="conversation")
    assert describe_route_rule(rule, {"router-1": "Escalation Router"}) == (
        'Router "Escalation Router" must take route "escalate" during the conversation.'
    )


def test_action_description_reads_as_a_sentence():
    rule = ActionRule(id="a", node="zendesk-1", should_fire=False)
    assert describe_action_rule(rule, {"zendesk-1": "Create Ticket"}) == (
        '"Create Ticket" must not complete on every turn.'
    )
