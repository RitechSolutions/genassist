"""Unit tests for tool-usage rule evaluation (pure logic)."""

import pytest

from app.services.tool_usage_rules import (
    RULE_FAILED,
    RULE_NOT_EVALUATED,
    RULE_PASSED,
    PerToolCheck,
    ToolUsageRule,
    canonicalize_tool_usage_config,
    describe_tool_rule,
    evaluate_rule,
    evaluate_rules,
    parse_tool_usage_config,
    plan_tool_rule_results,
    summarize_planned_results,
)


def _event(tool_id, *, agent_id="agent-1", status="succeeded", tool_name=None, result="ok", arguments=None):
    return {
        "agent_id": agent_id,
        "tool_id": tool_id,
        "tool_name": tool_name or tool_id,
        "arguments": arguments or {},
        "result": result,
        "status": status,
    }


def _rule(**kw):
    kw.setdefault("id", "r1")
    kw.setdefault("agent_id", "agent-1")
    return ToolUsageRule(**kw)


# ---- operators -------------------------------------------------------------

def test_all_passes_when_every_tool_called():
    rule = _rule(tool_ids=["a", "b"], operator="all")
    res = evaluate_rule(rule, [_event("a"), _event("b")], {"agent-1"})
    assert res["status"] == RULE_PASSED


def test_all_fails_with_missing_tool():
    rule = _rule(tool_ids=["a", "b"], operator="all")
    res = evaluate_rule(rule, [_event("a")], {"agent-1"})
    assert res["status"] == RULE_FAILED
    assert res["missing_tools"] == ["b"]


def test_any_passes_with_one_tool():
    rule = _rule(tool_ids=["a", "b"], operator="any")
    res = evaluate_rule(rule, [_event("b")], {"agent-1"})
    assert res["status"] == RULE_PASSED


def test_none_fails_on_forbidden_attempt_even_if_call_failed():
    # Forbidden tool attempted, and it failed — must still fail the rule.
    rule = _rule(tool_ids=["danger"], operator="none")
    res = evaluate_rule(rule, [_event("danger", status="failed")], {"agent-1"})
    assert res["status"] == RULE_FAILED
    assert res["forbidden_tools"] == ["danger"]


def test_none_passes_when_not_attempted():
    rule = _rule(tool_ids=["danger"], operator="none")
    res = evaluate_rule(rule, [_event("safe")], {"agent-1"})
    assert res["status"] == RULE_PASSED


def test_require_success_checks_only_successful_events():
    # One successful call with the wrong result, one failed call with the expected
    # result. With require_success, only the successful (wrong) event is inspected,
    # so the per-tool result check must FAIL.
    rule = _rule(
        tool_ids=["a"], operator="all", require_success=True,
        per_tool={"a": PerToolCheck(result_contains="expected")},
    )
    events = [
        _event("a", status="succeeded", result="wrong value"),
        _event("a", status="failed", result="the expected value"),
    ]
    res = evaluate_rule(rule, events, {"agent-1"})
    assert res["status"] == RULE_FAILED
    assert "result" in res["comment"]


def test_per_tool_reason_distinguishes_missing_result_from_empty():
    used_but_none = _rule(
        tool_ids=["a"], operator="all",
        per_tool={"a": PerToolCheck(result_not_empty=True)},
    )
    res = evaluate_rule(used_but_none, [_event("a", result=None)], {"agent-1"})
    assert res["status"] == RULE_FAILED
    assert "does not record" in res["comment"]


def test_min_calls_greater_than_max_calls_rejected():
    with pytest.raises(ValueError, match="min_calls"):
        _rule(tool_ids=["a"], min_calls=3, max_calls=1)


# ---- canonicalization (editing an old evaluation) --------------------------

def test_canonicalize_resolves_names_inside_rules():
    # The frontend can save legacy names into tool_ids/agent_id; canonicalize maps
    # them to ids (and leaves real ids unchanged).
    tool_map = {"search": "tool-1", "tool-1": "tool-1"}
    agent_map = {"researcher": "agent-1", "agent-1": "agent-1"}
    raw = {"rules": [{"id": "r1", "tool_ids": ["search"], "operator": "all", "agent_id": "researcher"}]}
    out = canonicalize_tool_usage_config(
        raw,
        resolve_tool_id=lambda name: tool_map.get(name),
        resolve_agent_id=lambda label: agent_map.get(label),
    )
    assert out["rules"][0]["tool_ids"] == ["tool-1"]
    assert out["rules"][0]["agent_id"] == "agent-1"


def test_canonicalize_converts_legacy_shape():
    # Idempotent resolver (id -> id), mirroring the real catalogue resolver.
    tool_map = {"search": "tool-1", "tool-1": "tool-1"}
    out = canonicalize_tool_usage_config(
        {"tool": "search", "should_call": False},
        resolve_tool_id=lambda name: tool_map.get(name),
        resolve_agent_id=lambda label: None,
    )
    assert out["rules"][0]["tool_ids"] == ["tool-1"]
    assert out["rules"][0]["operator"] == "none"


def test_canonicalize_raises_on_unknown_name():
    with pytest.raises(ValueError):
        canonicalize_tool_usage_config(
            {"rules": [{"id": "r1", "tool_ids": ["ghost"], "operator": "all"}]},
            resolve_tool_id=lambda name: None,
            resolve_agent_id=lambda label: None,
        )


def test_only_fails_when_outside_tool_used():
    rule = _rule(tool_ids=["a"], operator="only")
    res = evaluate_rule(rule, [_event("a"), _event("b")], {"agent-1"})
    assert res["status"] == RULE_FAILED
    assert res["forbidden_tools"] == ["b"]


def test_only_passes_when_all_within_set():
    rule = _rule(tool_ids=["a", "b"], operator="only")
    res = evaluate_rule(rule, [_event("a")], {"agent-1"})
    assert res["status"] == RULE_PASSED


# ---- require_success -------------------------------------------------------

def test_paused_call_counts_as_used_when_success_is_not_required():
    rule = _rule(tool_ids=["a"], operator="all", require_success=False)
    res = evaluate_rule(rule, [_event("a", status="paused")], {"agent-1"})

    assert res["status"] == RULE_PASSED
    assert res["observed_tools"] == ["a"]
    assert res["missing_tools"] == []
    assert res["call_counts"]["a"] == 1
    assert res["successful_call_counts"].get("a", 0) == 0


def test_paused_call_does_not_satisfy_must_succeed():
    rule = _rule(tool_ids=["a"], operator="all", require_success=True)
    res = evaluate_rule(rule, [_event("a", status="paused")], {"agent-1"})

    assert res["status"] == RULE_FAILED
    assert res["missing_tools"] == []
    assert res["failed_tools"] == ["a"]
    assert "called but did not succeed" in res["comment"]


def test_require_success_fails_when_only_failed_calls():
    rule = _rule(tool_ids=["a"], operator="all", require_success=True)
    res = evaluate_rule(rule, [_event("a", status="failed")], {"agent-1"})
    assert res["status"] == RULE_FAILED


def test_require_success_passes_on_success():
    rule = _rule(tool_ids=["a"], operator="all", require_success=True)
    res = evaluate_rule(rule, [_event("a", status="succeeded")], {"agent-1"})
    assert res["status"] == RULE_PASSED


# ---- not-called vs called-but-failed vs check-mismatch ----------------------

def test_called_but_failed_reported_separately_from_missing():
    # require_success on: "a" was attempted but only failed; "b" was never attempted.
    rule = _rule(tool_ids=["a", "b"], operator="all", require_success=True)
    res = evaluate_rule(rule, [_event("a", status="failed")], {"agent-1"})
    assert res["status"] == RULE_FAILED
    assert res["failed_tools"] == ["a"]   # called but never succeeded
    assert res["missing_tools"] == ["b"]  # never called
    assert "called but did not succeed" in res["comment"]


def test_check_mismatch_is_neither_missing_nor_failed():
    # The tool was called and succeeded, but its result check did not match.
    rule = _rule(tool_ids=["a"], operator="all", per_tool={"a": PerToolCheck(result_contains="xyz")})
    res = evaluate_rule(rule, [_event("a", result="nope")], {"agent-1"})
    assert res["status"] == RULE_FAILED
    assert "a" in res["check_failures"]
    assert res["missing_tools"] == []
    assert res["failed_tools"] == []


# ---- three-state / not_evaluated ------------------------------------------

def test_required_rule_not_evaluated_when_agent_never_ran():
    rule = _rule(tool_ids=["a"], operator="all")
    res = evaluate_rule(rule, [], executed_agent_ids=set())
    assert res["status"] == RULE_NOT_EVALUATED


def test_forbidden_attempt_fails_even_when_agent_not_in_executed_set():
    # Execution stopped, but a forbidden attempt was already observed -> fail.
    rule = _rule(tool_ids=["danger"], operator="none")
    res = evaluate_rule(rule, [_event("danger")], executed_agent_ids=set())
    assert res["status"] == RULE_FAILED


# ---- multi-agent -----------------------------------------------------------

def test_agent_filter_ignores_other_agents_calls():
    rule = _rule(tool_ids=["a"], operator="all", agent_id="agent-1")
    events = [_event("a", agent_id="agent-2")]  # wrong agent
    res = evaluate_rule(rule, events, {"agent-1", "agent-2"})
    assert res["status"] == RULE_FAILED


def test_any_agent_rule_considers_all_agents():
    rule = _rule(tool_ids=["a"], operator="all", agent_id=None)
    res = evaluate_rule(rule, [_event("a", agent_id="agent-9")], {"agent-9"})
    assert res["status"] == RULE_PASSED


# ---- min/max calls ---------------------------------------------------------

def test_min_calls_enforced():
    rule = _rule(tool_ids=["a"], operator="all", min_calls=2)
    one = evaluate_rule(rule, [_event("a")], {"agent-1"})
    two = evaluate_rule(rule, [_event("a"), _event("a")], {"agent-1"})
    assert one["status"] == RULE_FAILED
    assert two["status"] == RULE_PASSED


def test_max_calls_enforced():
    rule = _rule(tool_ids=["a"], operator="all", max_calls=1)
    res = evaluate_rule(rule, [_event("a"), _event("a")], {"agent-1"})
    assert res["status"] == RULE_FAILED


# ---- per-tool advanced -----------------------------------------------------

def test_per_tool_result_not_empty():
    rule = _rule(tool_ids=["a"], operator="all", per_tool={"a": {"result_not_empty": True}})
    empty = evaluate_rule(rule, [_event("a", result="No results found")], {"agent-1"})
    full = evaluate_rule(rule, [_event("a", result="here is your answer")], {"agent-1"})
    assert empty["status"] == RULE_FAILED
    assert full["status"] == RULE_PASSED


def test_per_tool_expected_args():
    rule = _rule(tool_ids=["a"], operator="all", per_tool={"a": {"expected_args": {"q": "pto"}}})
    ok = evaluate_rule(rule, [_event("a", arguments={"q": "pto", "extra": 1})], {"agent-1"})
    bad = evaluate_rule(rule, [_event("a", arguments={"q": "vacation"})], {"agent-1"})
    assert ok["status"] == RULE_PASSED
    assert bad["status"] == RULE_FAILED


# ---- coverage aggregation --------------------------------------------------

def test_coverage_and_overall():
    rules = [
        _rule(id="pass", tool_ids=["a"], operator="all"),
        _rule(id="fail", tool_ids=["b"], operator="all"),
        _rule(id="skip", tool_ids=["c"], operator="all", agent_id="agent-2"),
    ]
    summary = evaluate_rules(rules, [_event("a")], {"agent-1"})
    assert summary["coverage"] == {
        "passed": 1, "failed": 1, "not_evaluated": 1, "evaluated": 2, "total": 3,
    }
    assert summary["score"] == 0.5
    assert summary["passed"] is False  # a failure means not healthy


def test_all_not_evaluated_is_not_healthy():
    rules = [_rule(id="x", tool_ids=["a"], operator="all", agent_id="never")]
    summary = evaluate_rules(rules, [], set())
    assert summary["score"] is None
    assert summary["passed"] is False


# ---- validation ------------------------------------------------------------

def test_duplicate_rule_ids_rejected():
    with pytest.raises(ValueError):
        parse_tool_usage_config({"rules": [
            {"id": "x", "tool_ids": ["a"], "operator": "all"},
            {"id": "x", "tool_ids": ["b"], "operator": "all"},
        ]})


def test_specific_turn_requires_target():
    with pytest.raises(ValueError):
        ToolUsageRule(id="x", tool_ids=["a"], operator="all", scope="specific_turn")


def test_specific_turn_accepts_conversation_turn_target():
    rule = ToolUsageRule(
        id="x", tool_ids=["a"], operator="all", scope="specific_turn",
        target_source_conversation_id="conv-1", target_turn_index=2,
    )
    assert rule.scope == "specific_turn"


def test_only_allows_empty_tool_ids():
    rule = ToolUsageRule(id="x", tool_ids=[], operator="only")
    assert rule.operator == "only"


def test_bad_operator_rejected():
    with pytest.raises(ValueError):
        ToolUsageRule(id="x", tool_ids=["a"], operator="sometimes")


# ---- legacy conversion -----------------------------------------------------

def test_legacy_should_call_true_becomes_all():
    cfg = parse_tool_usage_config({"tool": "search", "node": "Research Agent"})
    assert len(cfg.rules) == 1
    rule = cfg.rules[0]
    assert rule.operator == "all"
    assert rule.tool_ids == ["search"]
    assert rule.agent_id == "Research Agent"
    assert rule.scope == "every_turn"


def test_legacy_should_call_false_becomes_none():
    cfg = parse_tool_usage_config({"tool": "delete", "should_call": False})
    assert cfg.rules[0].operator == "none"


def test_legacy_result_options_map_to_per_tool():
    cfg = parse_tool_usage_config({"tool": "search", "result_not_empty": True})
    rule = cfg.rules[0]
    assert rule.per_tool["search"].result_not_empty is True


def test_legacy_resolver_maps_names_to_ids():
    cfg = parse_tool_usage_config(
        {"tool": "search", "node": "Research Agent"},
        resolve_tool_id=lambda name: "tool-node-7",
        resolve_agent_id=lambda label: "agent-node-3",
    )
    rule = cfg.rules[0]
    assert rule.tool_ids == ["tool-node-7"]
    assert rule.agent_id == "agent-node-3"


def test_legacy_unresolvable_name_raises():
    with pytest.raises(ValueError):
        parse_tool_usage_config(
            {"tool": "ghost"}, resolve_tool_id=lambda name: None
        )


def test_legacy_any_tool_expands_to_any_over_all_tools():
    # Old "any tool" config: should_call true with no tool named.
    cfg = parse_tool_usage_config({"should_call": True}, all_tool_ids=["tool-1", "tool-2"])
    rule = cfg.rules[0]
    assert rule.operator == "any"
    assert rule.tool_ids == ["tool-1", "tool-2"]
    used = evaluate_rule(rule, [_event("tool-1", agent_id="ag")], {"ag"})
    idle = evaluate_rule(rule, [], {"ag"})
    assert used["status"] == RULE_PASSED
    assert idle["status"] == RULE_FAILED


def test_legacy_no_tool_forbids_all_tools():
    # Old "no tool may be used" config: should_call false with no tool named.
    cfg = parse_tool_usage_config({"should_call": False})
    rule = cfg.rules[0]
    assert rule.operator == "only"
    assert rule.tool_ids == []
    used = evaluate_rule(rule, [_event("x", agent_id="ag")], {"ag"})
    clean = evaluate_rule(rule, [], {"ag"})
    assert used["status"] == RULE_FAILED
    assert clean["status"] == RULE_PASSED


def test_canonicalize_legacy_any_tool_uses_all_tool_ids():
    out = canonicalize_tool_usage_config(
        {"should_call": True},
        resolve_tool_id=lambda name: name,  # idempotent id -> id
        resolve_agent_id=lambda label: None,
        all_tool_ids=["tool-1", "tool-2"],
    )
    assert out["rules"][0]["operator"] == "any"
    assert out["rules"][0]["tool_ids"] == ["tool-1", "tool-2"]


# ---- scope planning --------------------------------------------------------

def _turn(tid, conv=None, idx=None):
    return {"id": tid, "source_conversation_id": conv, "turn_index": idx}


def test_every_turn_grades_each_turn_separately():
    rule = ToolUsageRule(id="r", tool_ids=["a"], operator="all", scope="every_turn", agent_id="ag")
    turns = [_turn("t1"), _turn("t2")]
    events = {"t1": [_event("a", agent_id="ag")], "t2": []}
    executed = {"t1": {"ag"}, "t2": {"ag"}}
    planned = plan_tool_rule_results([rule], turns, [["t1"], ["t2"]], events, executed)
    assert [p["case_id"] for p in planned] == ["t1", "t2"]
    assert planned[0]["result"]["status"] == RULE_PASSED
    assert planned[1]["result"]["status"] == RULE_FAILED


def test_conversation_scope_merges_turns_and_grades_once():
    rule = ToolUsageRule(id="r", tool_ids=["a"], operator="any", scope="conversation", agent_id="ag")
    turns = [_turn("t1", "conv-1", 0), _turn("t2", "conv-1", 1)]
    events = {"t1": [], "t2": [_event("a", agent_id="ag")]}  # tool used only on turn 2
    executed = {"t1": {"ag"}, "t2": {"ag"}}
    planned = plan_tool_rule_results([rule], turns, [["t1", "t2"]], events, executed)
    assert len(planned) == 1  # one result for the whole conversation
    assert planned[0]["result"]["status"] == RULE_PASSED
    assert planned[0]["source_conversation_id"] == "conv-1"
    assert planned[0]["case_id"] is None


def test_specific_turn_targets_by_conversation_and_index():
    rule = ToolUsageRule(
        id="r", tool_ids=["a"], operator="all", scope="specific_turn", agent_id="ag",
        target_source_conversation_id="conv-1", target_turn_index=1,
    )
    turns = [_turn("t1", "conv-1", 0), _turn("t2", "conv-1", 1)]
    events = {"t1": [_event("a", agent_id="ag")], "t2": []}  # tool used on turn 0, not turn 1
    executed = {"t1": {"ag"}, "t2": {"ag"}}
    planned = plan_tool_rule_results([rule], turns, [["t1", "t2"]], events, executed)
    assert len(planned) == 1
    assert planned[0]["case_id"] == "t2"  # resolved to the turn-1 case
    assert planned[0]["result"]["status"] == RULE_FAILED


def test_specific_turn_missing_target_is_not_evaluated():
    rule = ToolUsageRule(
        id="r", tool_ids=["a"], operator="all", scope="specific_turn",
        target_source_conversation_id="conv-9", target_turn_index=5,
    )
    planned = plan_tool_rule_results([rule], [_turn("t1", "conv-1", 0)], [["t1"]], {"t1": []}, {"t1": set()})
    assert planned[0]["result"]["status"] == RULE_NOT_EVALUATED
    assert "not found" in planned[0]["result"]["comment"]


def test_summary_from_planned_results_reports_coverage():
    rules = [
        ToolUsageRule(id="p", tool_ids=["a"], operator="all", scope="every_turn", agent_id="ag"),
        ToolUsageRule(id="f", tool_ids=["b"], operator="all", scope="every_turn", agent_id="ag"),
    ]
    turns = [_turn("t1")]
    planned = plan_tool_rule_results(rules, turns, [["t1"]], {"t1": [_event("a", agent_id="ag")]}, {"t1": {"ag"}})
    summary = summarize_planned_results(planned)
    assert summary["coverage"] == {
        "passed": 1, "failed": 1, "not_evaluated": 0, "evaluated": 2, "total": 2,
    }
    assert summary["accuracy"] == 0.5


# ---- call counts -----------------------------------------------------------

def test_result_records_call_counts():
    rule = _rule(tool_ids=["a"], operator="all")
    res = evaluate_rule(rule, [_event("a"), _event("a", status="failed")], {"agent-1"})
    assert res["call_counts"]["a"] == 2
    assert res["successful_call_counts"]["a"] == 1


# ---- describe_tool_rule ----------------------------------------------------

def test_describe_all_rule_uses_labels_and_conjunction():
    rule = _rule(tool_ids=["t1", "t2"], operator="all", agent_id="ag", scope="conversation")
    text = describe_tool_rule(rule, {"ag": "Support Agent"}, {"t1": "Knowledge Search", "t2": "Create Ticket"})
    assert text == 'Support Agent must use "Knowledge Search" and "Create Ticket" during the conversation.'


def test_describe_none_rule():
    rule = _rule(tool_ids=["t1"], operator="none", agent_id="ag")
    text = describe_tool_rule(rule, {"ag": "Support Agent"}, {"t1": "Delete Customer"})
    assert text == 'Support Agent must not use "Delete Customer" on every turn.'


def test_describe_require_success_specific_turn():
    rule = ToolUsageRule(
        id="r", tool_ids=["t1"], operator="all", agent_id="ag", require_success=True,
        scope="specific_turn", target_source_conversation_id="c", target_turn_index=1,
    )
    text = describe_tool_rule(rule, {"ag": "Support Agent"}, {"t1": "Create Ticket"})
    assert "successfully use" in text
    assert "on turn 2" in text


def test_describe_only_no_tools():
    rule = ToolUsageRule(id="r", tool_ids=[], operator="only", agent_id="ag")
    text = describe_tool_rule(rule, {"ag": "Support Agent"}, {})
    assert text == "Support Agent must not use any tools on every turn."


def test_describe_falls_back_to_ids_without_labels():
    rule = _rule(tool_ids=["tool-xyz"], operator="all", agent_id=None)
    text = describe_tool_rule(rule)
    assert text == 'Any agent must use "tool-xyz" on every turn.'


# ---- by_scope --------------------------------------------------------------

def test_summary_includes_by_scope():
    rules = [
        ToolUsageRule(id="c", tool_ids=["a"], operator="any", scope="conversation", agent_id="ag"),
        ToolUsageRule(id="t", tool_ids=["a"], operator="all", scope="every_turn", agent_id="ag"),
    ]
    turns = [_turn("t1", "conv-1", 0), _turn("t2", "conv-1", 1)]
    planned = plan_tool_rule_results(
        rules, turns, [["t1", "t2"]],
        {"t1": [_event("a", agent_id="ag")], "t2": []},
        {"t1": {"ag"}, "t2": {"ag"}},
    )
    summary = summarize_planned_results(planned)
    # conversation rule -> 1 result; every_turn rule -> 2 results (one per turn)
    assert summary["by_scope"] == {"conversation": 1, "every_turn": 2}
    assert summary["passed"] + summary["failed"] + summary["not_evaluated"] == 3
