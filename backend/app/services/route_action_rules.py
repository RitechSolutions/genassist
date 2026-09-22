"""
Route Taken / Action Taken evaluation rules — pure logic, no DB or engine deps.

Both techniques are a list of rules graded against what a run's trace observed:

    route_taken   — a router node took an expected branch
    action_taken  — a side-effect node did (or did not) complete

Each rule carries a scope (see :mod:`app.services.rule_scopes`), so an assertion
can cover one turn or a whole conversation. Conversation scope is satisfied when
the rule holds *somewhere* in the conversation — "a ticket is created once per
conversation" rather than "on every turn".

Every rule result is one of three states, so incomplete runs never look healthy:

    passed         — the assertion held
    failed         — the assertion was violated (observed)
    not_evaluated  — no turn in scope produced a trace, so nothing could be checked
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, List, NamedTuple, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.services.evaluation_text import (
    display_name,
    names_equal,
    node_matches_selector,
    normalize_text,
)
from app.services.rule_scopes import (
    RULE_FAILED,
    RULE_NOT_EVALUATED,
    RULE_PASSED,
    ScopedRule,
    plan_rule_results,
    scope_phrase,
)

ROUTER_NODE_TYPE = "routerNode"


# ---- schema ----------------------------------------------------------------


class RouteRule(ScopedRule):
    """One routing assertion: ``router`` took branch ``expected``.

    ``router`` is a node id or display label; empty means "any router node".
    """

    router: Optional[str] = None
    expected: str

    @model_validator(mode="after")
    def _check_expected(self) -> "RouteRule":
        if not normalize_text(self.expected):
            raise ValueError(f"rule {self.id!r}: an expected route is required")
        return self


class ActionRule(ScopedRule):
    """One side-effect assertion: ``node`` (or any node of ``node_type``) must
    complete, or must never complete, within the rule's scope."""

    node: Optional[str] = None
    node_type: Optional[str] = None
    should_fire: bool = True

    @model_validator(mode="after")
    def _check_target(self) -> "ActionRule":
        if not self.node and not self.node_type:
            raise ValueError(f"rule {self.id!r}: an action node or node_type is required")
        return self


class RouteConfig(BaseModel):
    """The full ``route_taken`` technique config."""

    model_config = ConfigDict(extra="ignore")

    rules: List[RouteRule] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique_ids(self) -> "RouteConfig":
        _reject_duplicate_ids(rule.id for rule in self.rules)
        return self


class ActionConfig(BaseModel):
    """The full ``action_taken`` technique config."""

    model_config = ConfigDict(extra="ignore")

    rules: List[ActionRule] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique_ids(self) -> "ActionConfig":
        _reject_duplicate_ids(rule.id for rule in self.rules)
        return self


def _reject_duplicate_ids(ids: Iterable[str]) -> None:
    seen = list(ids)
    duplicates = {rule_id for rule_id in seen if seen.count(rule_id) > 1}
    if duplicates:
        raise ValueError(f"duplicate rule ids: {sorted(duplicates)}")


# ---- config parsing --------------------------------------------------------


def parse_route_config(raw: Optional[Dict[str, Any]]) -> RouteConfig:
    """Parse a ``route_taken`` config; the legacy single-rule shape becomes one rule."""
    return RouteConfig(rules=_rule_dicts(raw, "route", _is_route_rule))


def parse_action_config(raw: Optional[Dict[str, Any]]) -> ActionConfig:
    """Parse an ``action_taken`` config; the legacy single-rule shape becomes one rule."""
    return ActionConfig(rules=_rule_dicts(raw, "action", _is_action_rule))


def _is_route_rule(raw: Dict[str, Any]) -> bool:
    return bool(normalize_text(raw.get("expected")))


def _is_action_rule(raw: Dict[str, Any]) -> bool:
    return bool(raw.get("node") or raw.get("node_type"))


def _rule_dicts(
    raw: Optional[Dict[str, Any]],
    id_prefix: str,
    is_rule: Callable[[Dict[str, Any]], bool],
) -> List[Dict[str, Any]]:
    """Normalize either config shape into a list of rule dicts with stable ids.

    Configs saved before rules had ids get index-based ones, so a stored config
    always plans the same rule ids for the same rules.
    """
    raw = raw or {}
    raw_rules = raw.get("rules")
    candidates = raw_rules if isinstance(raw_rules, list) else [raw]

    rules: List[Dict[str, Any]] = []
    for index, candidate in enumerate(candidates, start=1):
        if not isinstance(candidate, dict) or not is_rule(candidate):
            continue
        rule = dict(candidate)
        # Legacy route configs named the router "node"; the builder writes "router".
        if id_prefix == "route" and not rule.get("router") and rule.get("node"):
            rule["router"] = rule.pop("node")
        rule.setdefault("id", f"{id_prefix}-{index}")
        rules.append(rule)
    return rules


# ---- trace observations ----------------------------------------------------


def route_observations(trace: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """The router nodes one turn executed, with the branch each one took."""
    routers = ((trace or {}).get("nodes_by_type") or {}).get(ROUTER_NODE_TYPE) or []
    observations = []
    for router in routers:
        output = router.get("output")
        observations.append(
            {
                "id": router.get("id"),
                "label": router.get("label"),
                "route": (output or {}).get("route") if isinstance(output, dict) else None,
            }
        )
    return observations


def action_observations(trace: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """The nodes one turn executed, with how each one finished."""
    nodes = (trace or {}).get("nodes") or {}
    return [
        {
            "id": node.get("id"),
            "label": node.get("label"),
            "type": node.get("type"),
            "status": node.get("status"),
            "error": node.get("error"),
        }
        for node in nodes.values()
        if isinstance(node, dict)
    ]


class ScopeSlice(NamedTuple):
    """What a rule is graded against: the observations of each turn in scope that
    produced a trace, plus how many turns the scope covers (including ones that
    never ran, so a partly-failed conversation is reported honestly)."""

    turns: List[List[Dict[str, Any]]]
    total_turns: int

    @property
    def spans_many_turns(self) -> bool:
        return self.total_turns > 1


def slice_for(
    observations_by_turn: Dict[str, List[Dict[str, Any]]], turn_ids: List[str]
) -> ScopeSlice:
    return ScopeSlice(
        turns=[observations_by_turn[turn_id] for turn_id in turn_ids if turn_id in observations_by_turn],
        total_turns=len(turn_ids),
    )


# ---- grading ---------------------------------------------------------------


def _not_evaluated(rule_number: int, scope_slice: ScopeSlice, **extra: Any) -> Dict[str, Any]:
    comment = (
        "No turn in this conversation produced a trace, so the rule could not be checked."
        if scope_slice.spans_many_turns
        else "This turn produced no trace, so the rule could not be checked."
    )
    return {
        "rule_number": rule_number,
        "status": RULE_NOT_EVALUATED,
        "passed": False,
        "observed": "not evaluated",
        "comment": comment,
        **extra,
    }


def _turns_phrase(hits: int, total: int) -> str:
    return f"{hits} of {total} turn{'s' if total != 1 else ''}"


def grade_route_rule(
    rule: RouteRule,
    scope_slice: ScopeSlice,
    node_labels: Dict[str, str],
    rule_number: int,
) -> Dict[str, Any]:
    """Grade one route rule over its scope slice."""
    selector = rule.router
    expected = normalize_text(rule.expected)

    routes_taken: List[str] = []
    hit_turns = 0
    router_ran = False
    trace_label: Optional[str] = None
    for turn in scope_slice.turns:
        matched = [obs for obs in turn if node_matches_selector(obs, selector)] if selector else turn
        router_ran = router_ran or bool(matched)
        trace_label = trace_label or next(
            (obs.get("label") for obs in matched if obs.get("label")), None
        )
        turn_routes = [normalize_text(obs.get("route")) for obs in matched]
        if any(names_equal(route, expected) for route in turn_routes):
            hit_turns += 1
        routes_taken.extend(route for route in turn_routes if route)

    # Prefer the name the trace recorded; fall back to the graph's label for a
    # router that never ran.
    router_name = (trace_label or display_name(selector, node_labels)) if selector else None
    router_info = {"id": selector, "label": router_name}
    if not scope_slice.turns:
        return _not_evaluated(rule_number, scope_slice, router=router_info, expected=expected)

    # The stored observed value stays plain (legacy shape); quotes are comment-only.
    unique_routes = list(dict.fromkeys(routes_taken))
    observed = ", ".join(unique_routes) or "none"
    passed = hit_turns > 0

    return {
        "rule_number": rule_number,
        "router": router_info,
        "expected": expected,
        "observed": observed,
        "status": RULE_PASSED if passed else RULE_FAILED,
        "passed": passed,
        "comment": _route_comment(
            passed=passed,
            expected=expected,
            router_name=router_name,
            router_ran=router_ran or not selector,
            routes=unique_routes,
            hit_turns=hit_turns,
            scope_slice=scope_slice,
        ),
    }


def _route_comment(
    *,
    passed: bool,
    expected: str,
    router_name: Optional[str],
    router_ran: bool,
    routes: List[str],
    hit_turns: int,
    scope_slice: ScopeSlice,
) -> str:
    quoted_routes = ", ".join(f"'{route}'" for route in routes) or "none"
    where = f" on {_turns_phrase(hit_turns, scope_slice.total_turns)}" if scope_slice.spans_many_turns else ""
    in_scope = " in this conversation" if scope_slice.spans_many_turns else ""

    if passed:
        if router_name:
            return f"Router '{router_name}' took route '{expected}'{where}."
        return f"Route '{expected}' was taken{where}."
    if router_name and not router_ran:
        return f"Router '{router_name}' did not run{in_scope}."
    if router_name:
        return f"Expected route '{expected}' on router '{router_name}'{in_scope}, took {quoted_routes}."
    return f"Expected route '{expected}'{in_scope}, took {quoted_routes}."


def grade_action_rule(
    rule: ActionRule,
    scope_slice: ScopeSlice,
    node_labels: Dict[str, str],
    rule_number: int,
) -> Dict[str, Any]:
    """Grade one action rule over its scope slice."""
    selector = rule.node
    node_type = rule.node_type

    def is_target(node: Dict[str, Any]) -> bool:
        if selector and not node_matches_selector(node, selector):
            return False
        if node_type and node.get("type") != node_type:
            return False
        return True

    fired_turns = 0
    ran_turns = 0
    errored = False
    fired_label: Optional[str] = None
    seen_label: Optional[str] = None
    for turn in scope_slice.turns:
        candidates = [node for node in turn if is_target(node)]
        if not candidates:
            continue
        ran_turns += 1
        seen_label = seen_label or candidates[0].get("label")
        completed = next(
            (node for node in candidates if node.get("status") == "success" and not node.get("error")),
            None,
        )
        if completed is not None:
            fired_turns += 1
            fired_label = fired_label or completed.get("label")
        errored = errored or any(node.get("error") for node in candidates)

    # Name the node that determined the outcome: the one that completed when the
    # rule hinges on completing, else any match (they share the not-fired status).
    target_name = (
        fired_label or seen_label or display_name(selector or node_type, node_labels)
    )
    node_info = {"id": selector or node_type, "label": target_name}
    if not scope_slice.turns:
        return _not_evaluated(
            rule_number,
            scope_slice,
            node=node_info,
            expected="must complete" if rule.should_fire else "must not complete",
        )

    fired = fired_turns > 0
    passed = fired if rule.should_fire else not fired
    comment, show_comment_on_pass = _action_comment(
        passed=passed,
        should_fire=rule.should_fire,
        target_name=target_name,
        ran_turns=ran_turns,
        fired_turns=fired_turns,
        scope_slice=scope_slice,
    )

    return {
        "rule_number": rule_number,
        "node": node_info,
        "expected": "must complete" if rule.should_fire else "must not complete",
        "observed": _action_observed(ran_turns, fired, errored),
        "status": RULE_PASSED if passed else RULE_FAILED,
        "passed": passed,
        "comment": comment,
        "show_comment_on_pass": show_comment_on_pass,
    }


def _action_observed(ran_turns: int, fired: bool, errored: bool) -> str:
    if ran_turns == 0:
        return "did not run"
    if fired:
        return "completed"
    return "ran with an error" if errored else "did not complete"


def _action_comment(
    *,
    passed: bool,
    should_fire: bool,
    target_name: str,
    ran_turns: int,
    fired_turns: int,
    scope_slice: ScopeSlice,
) -> "tuple[str, bool]":
    """The rule's outcome in words, and whether to show it on a pass."""
    many = scope_slice.spans_many_turns
    where = f" on {_turns_phrase(fired_turns, scope_slice.total_turns)}" if many else ""
    in_scope = " in this conversation" if many else " in this evaluation"

    if passed:
        if ran_turns == 0:
            # Passing because nothing ran is worth saying out loud.
            return f"'{target_name}' did not run{in_scope}.", True
        if fired_turns:
            return f"'{target_name}' completed{where}.", False
        return f"'{target_name}' did not complete.", False
    if should_fire:
        requirement = f"to complete at least once{in_scope}" if many else "to complete"
        return f"Expected '{target_name}' {requirement} but it did not.", False
    return f"Expected '{target_name}' not to complete but it did{where}.", False


# ---- human-readable description --------------------------------------------


def describe_route_rule(rule: RouteRule, node_labels: Optional[Dict[str, str]] = None) -> str:
    """A plain-language sentence for a route rule, using human labels where available.

    Captured at evaluation time so a later rename never rewrites past results.
    """
    phrase = scope_phrase(rule)
    expected = normalize_text(rule.expected)
    if not rule.router:
        return f'Route "{expected}" must be taken {phrase}.'
    name = display_name(rule.router, node_labels or {}, fallback="Unknown router")
    return f'Router "{name}" must take route "{expected}" {phrase}.'


def describe_action_rule(rule: ActionRule, node_labels: Optional[Dict[str, str]] = None) -> str:
    """A plain-language sentence for an action rule, using human labels where available."""
    phrase = scope_phrase(rule)
    name = display_name(
        rule.node or rule.node_type, node_labels or {}, fallback="Unknown node"
    )
    if rule.should_fire:
        return f'"{name}" must complete {phrase}.'
    return f'"{name}" must not complete {phrase}.'


# ---- scope planning --------------------------------------------------------


def plan_route_results(
    rules: List[RouteRule],
    turns: List[Dict[str, Any]],
    conversation_groups: List[List[str]],
    observations_by_turn: Dict[str, List[Dict[str, Any]]],
    node_labels: Dict[str, str],
) -> List[Dict[str, Any]]:
    """Grade every route rule over its scope and return placed results."""
    return _plan(rules, turns, conversation_groups, observations_by_turn, node_labels, grade_route_rule)


def plan_action_results(
    rules: List[ActionRule],
    turns: List[Dict[str, Any]],
    conversation_groups: List[List[str]],
    observations_by_turn: Dict[str, List[Dict[str, Any]]],
    node_labels: Dict[str, str],
) -> List[Dict[str, Any]]:
    """Grade every action rule over its scope and return placed results."""
    return _plan(rules, turns, conversation_groups, observations_by_turn, node_labels, grade_action_rule)


def _plan(
    rules: List[Any],
    turns: List[Dict[str, Any]],
    conversation_groups: List[List[str]],
    observations_by_turn: Dict[str, List[Dict[str, Any]]],
    node_labels: Dict[str, str],
    grade_rule: Callable[..., Dict[str, Any]],
) -> List[Dict[str, Any]]:
    rule_number_by_id = {rule.id: index for index, rule in enumerate(rules, start=1)}

    def grade(rule: Any, turn_ids: List[str]) -> Dict[str, Any]:
        return grade_rule(
            rule, slice_for(observations_by_turn, turn_ids), node_labels, rule_number_by_id[rule.id]
        )

    def missing_target(rule: Any, description: Optional[str] = None) -> Dict[str, Any]:
        target = description or "turn"
        return {
            "rule_number": rule_number_by_id[rule.id],
            "status": RULE_NOT_EVALUATED,
            "passed": False,
            "observed": "not evaluated",
            "comment": f"Target {target} not found in this run.",
        }

    return plan_rule_results(rules, turns, conversation_groups, grade, missing_target)
