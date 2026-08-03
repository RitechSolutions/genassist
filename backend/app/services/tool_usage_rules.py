"""
Tool Usage evaluation rules — pure logic, no DB or engine dependencies.

A Tool Usage evaluation is a list of rules. Each rule asserts something about the
tool calls an agent made, using one operator:

    all   — every selected tool was called
    any   — at least one selected tool was called
    none  — no selected tool was attempted (a failed attempt still counts)
    only  — only selected tools were called (no tool outside the list)

Rules are graded against normalized tool events (see WorkflowState.tool_events).
Each rule result is one of three states so incomplete runs never look healthy:

    passed         — the assertion held
    failed         — the assertion was violated (observed)
    not_evaluated  — the agent never ran, so the assertion could not be checked
"""

from __future__ import annotations

import json
from typing import Any, Callable, Dict, Iterable, List, Optional, Set

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# ---- constants -------------------------------------------------------------

OPERATORS = ("all", "any", "none", "only")
SCOPES = ("specific_turn", "every_turn", "conversation")

RULE_PASSED = "passed"
RULE_FAILED = "failed"
RULE_NOT_EVALUATED = "not_evaluated"

# Operators that assert a tool WAS used (vs. forbidding/whitelisting usage).
_REQUIRING_OPERATORS = ("all", "any")

# No-result phrases emitted by the platform's retrieval layers.
_EMPTY_RESULT_PREFIXES = ("no results found", "no relevant information found")


# ---- schema ----------------------------------------------------------------


class PerToolCheck(BaseModel):
    """Optional extra assertions on a specific tool's call."""

    result_not_empty: bool = False
    result_contains: Optional[str] = None
    expected_args: Optional[Dict[str, Any]] = None


class ToolUsageRule(BaseModel):
    """One tool-usage assertion. See module docstring for operator semantics."""

    id: str
    tool_ids: List[str] = Field(default_factory=list)
    operator: str = "all"
    agent_id: Optional[str] = None
    require_success: bool = False
    scope: str = "every_turn"

    # Stable turn targeting: imported turns use (source_conversation_id, turn_index)
    # so a rule survives a conversation re-import; manual cases use case_id.
    target_case_id: Optional[str] = None
    target_source_conversation_id: Optional[str] = None
    target_turn_index: Optional[int] = None

    min_calls: Optional[int] = None
    max_calls: Optional[int] = None
    per_tool: Dict[str, PerToolCheck] = Field(default_factory=dict)

    @field_validator("operator")
    @classmethod
    def _valid_operator(cls, value: str) -> str:
        if value not in OPERATORS:
            raise ValueError(f"operator must be one of {OPERATORS}, got {value!r}")
        return value

    @field_validator("scope")
    @classmethod
    def _valid_scope(cls, value: str) -> str:
        if value not in SCOPES:
            raise ValueError(f"scope must be one of {SCOPES}, got {value!r}")
        return value

    @model_validator(mode="after")
    def _check_targets_and_tools(self) -> "ToolUsageRule":
        # "only" may forbid every tool (empty list); the others need a tool.
        if self.operator != "only" and not self.tool_ids:
            raise ValueError(f"rule {self.id!r}: operator {self.operator!r} requires at least one tool")
        if self.scope == "specific_turn":
            has_case = self.target_case_id is not None
            has_turn = (
                self.target_source_conversation_id is not None
                and self.target_turn_index is not None
            )
            if not (has_case or has_turn):
                raise ValueError(
                    f"rule {self.id!r}: specific_turn scope requires target_case_id or "
                    "(target_source_conversation_id + target_turn_index)"
                )
        if self.min_calls is not None and self.min_calls < 0:
            raise ValueError(f"rule {self.id!r}: min_calls must be >= 0")
        if self.max_calls is not None and self.max_calls < 0:
            raise ValueError(f"rule {self.id!r}: max_calls must be >= 0")
        if (
            self.min_calls is not None
            and self.max_calls is not None
            and self.min_calls > self.max_calls
        ):
            raise ValueError(
                f"rule {self.id!r}: min_calls ({self.min_calls}) must be <= max_calls ({self.max_calls})"
            )
        return self


class ToolUsageConfig(BaseModel):
    """The full ``tool_used`` technique config: a set of uniquely-identified rules."""

    model_config = ConfigDict(extra="ignore")

    rules: List[ToolUsageRule] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique_ids(self) -> "ToolUsageConfig":
        ids = [rule.id for rule in self.rules]
        duplicates = {rid for rid in ids if ids.count(rid) > 1}
        if duplicates:
            raise ValueError(f"duplicate rule ids: {sorted(duplicates)}")
        return self


# ---- evaluation ------------------------------------------------------------


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    try:
        return json.dumps(value, default=str)
    except (TypeError, ValueError):
        return str(value)


def _result_is_empty(result: Any) -> bool:
    text = _as_text(result)
    structurally_empty = isinstance(result, (list, dict)) and not result
    return (
        not text
        or structurally_empty
        or text.lower().startswith(_EMPTY_RESULT_PREFIXES)
    )


def _args_superset_match(actual: Any, expected: Dict[str, Any]) -> bool:
    if not isinstance(actual, dict):
        return False
    return all(_as_text(actual.get(k)) == _as_text(v) for k, v in expected.items())


def _per_tool_failure_reason(check: PerToolCheck, events: List[Dict[str, Any]]) -> Optional[str]:
    """None when some event meets the per-tool assertions; else a human reason.

    Distinguishes a missing/None result ("does not record") from an empty or
    sentinel result, so the failure message is honest about what was observed.
    """
    saw_result = False
    for event in events:
        result = event.get("result")
        if result is not None:
            saw_result = True
        if check.result_not_empty and _result_is_empty(result):
            continue
        if check.result_contains and check.result_contains not in _as_text(result):
            continue
        if check.expected_args and not _args_superset_match(event.get("arguments"), check.expected_args):
            continue
        return None
    if check.result_not_empty and not saw_result:
        return "the trace does not record a result for this tool"
    if check.result_not_empty:
        return "the tool result was empty or a no-results sentinel"
    if check.result_contains:
        return f"the tool result did not contain {check.result_contains!r}"
    if check.expected_args:
        return "the tool was not called with the expected arguments"
    return "the tool call did not satisfy the configured checks"


def _events_for_rule(rule: ToolUsageRule, events: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Events attributable to this rule's agent (or all agents when unscoped)."""
    if rule.agent_id is None:
        return list(events)
    return [e for e in events if e.get("agent_id") == rule.agent_id]


def _agent_ran(rule: ToolUsageRule, executed_agent_ids: Set[str]) -> bool:
    if rule.agent_id is not None:
        return rule.agent_id in executed_agent_ids
    return len(executed_agent_ids) > 0


def _result(rule: ToolUsageRule, status: str, *, comment: str,
            observed: Optional[List[str]] = None,
            missing: Optional[List[str]] = None,
            forbidden: Optional[List[str]] = None,
            failed: Optional[List[str]] = None,
            check_failures: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    return {
        "rule_id": rule.id,
        "operator": rule.operator,
        "agent_id": rule.agent_id,
        "scope": rule.scope,
        "status": status,
        # missing = never called; failed = called but never succeeded (require_success);
        # check_failures = called successfully but result/arguments did not match.
        "observed_tools": observed or [],
        "missing_tools": missing or [],
        "forbidden_tools": forbidden or [],
        "failed_tools": failed or [],
        "check_failures": check_failures or {},
        # Filled in by evaluate_rule so the UI can say "used successfully N times".
        "call_counts": {},
        "successful_call_counts": {},
        "comment": comment,
    }


def _count_calls(scoped: List[Dict[str, Any]]) -> "tuple[Dict[str, int], Dict[str, int]]":
    """Total and successful call counts per tool id observed in this scope."""
    call_counts: Dict[str, int] = {}
    successful: Dict[str, int] = {}
    for event in scoped:
        tool_id = event.get("tool_id")
        if not tool_id:
            continue
        call_counts[tool_id] = call_counts.get(tool_id, 0) + 1
        if event.get("status") == "succeeded":
            successful[tool_id] = successful.get(tool_id, 0) + 1
    return call_counts, successful


def _named(ids: Iterable[str], label_of: Callable[[str], str]) -> str:
    return ", ".join(f"'{label_of(item)}'" for item in ids)


def evaluate_rule(
    rule: ToolUsageRule,
    events: Iterable[Dict[str, Any]],
    executed_agent_ids: Optional[Set[str]] = None,
    label_of: Optional[Callable[[str], str]] = None,
) -> Dict[str, Any]:
    """Grade one rule against a scoped set of tool events. Returns a three-state result.

    ``label_of`` renders tool/agent ids as display names in comments; ids are kept
    as-is in the structured result fields.
    """
    executed_agent_ids = executed_agent_ids or set()
    label_of = label_of or (lambda value: value)
    scoped = _events_for_rule(rule, events)
    target_set: Set[str] = set(rule.tool_ids)

    call_counts, successful_call_counts = _count_calls(scoped)

    def done(result: Dict[str, Any]) -> Dict[str, Any]:
        # Record what actually happened so the UI can say "used successfully N times".
        result["call_counts"] = call_counts
        result["successful_call_counts"] = successful_call_counts
        return result

    attempted = {e.get("tool_id") for e in scoped}
    used = {
        e.get("tool_id")
        for e in scoped
        if not rule.require_success or e.get("status") == "succeeded"
    }
    agent_ran = _agent_ran(rule, executed_agent_ids)

    # Forbidding / whitelisting operators are attempt-based: a forbidden attempt is a
    # failure even if the call failed or the turn later errored.
    if rule.operator == "none":
        violated = sorted(t for t in (target_set & attempted) if t)
        if violated:
            return done(_result(rule, RULE_FAILED, forbidden=violated,
                                comment=f"Forbidden tool(s) attempted: {_named(violated, label_of)}."))
        if not agent_ran:
            return done(_result(rule, RULE_NOT_EVALUATED,
                                comment="Agent did not run; forbidden-tool rule could not be checked."))
        return done(_result(rule, RULE_PASSED, comment="No forbidden tools were attempted."))

    if rule.operator == "only":
        outside = sorted(t for t in (attempted - target_set) if t)
        if outside:
            return done(_result(rule, RULE_FAILED, forbidden=outside,
                                comment=f"Tool(s) outside the allowed set were used: {_named(outside, label_of)}."))
        if not agent_ran:
            return done(_result(rule, RULE_NOT_EVALUATED,
                                comment="Agent did not run; allowed-only rule could not be checked."))
        if not _calls_within_bounds(rule, target_set, scoped):
            return done(_result(rule, RULE_FAILED,
                                comment=_bounds_comment(rule, target_set, scoped)))
        return done(_result(rule, RULE_PASSED, comment="Only allowed tools were used."))

    # Required operators (all / any): if the agent never ran, we cannot judge usage.
    if not agent_ran:
        return done(_result(rule, RULE_NOT_EVALUATED,
                            comment="Agent did not run; required-tool rule could not be checked."))

    used_targets = {t for t in target_set if t in used}
    per_tool_reasons = {t: reason for t in used_targets if (reason := _per_tool_failure(rule, t, scoped))}
    satisfied = used_targets - set(per_tool_reasons)
    observed = sorted(satisfied)

    # Separate "never called" from "called but did not succeed" so a failed call
    # (with require_success on) is not reported as if the tool were missing.
    attempted_targets = {t for t in target_set if t in attempted}
    not_called = sorted(target_set - attempted_targets)
    called_but_failed = sorted(attempted_targets - used_targets)

    if rule.operator == "all":
        ok = not not_called and not called_but_failed and not per_tool_reasons
    else:  # any
        ok = bool(satisfied)

    if ok and not _calls_within_bounds(rule, target_set, scoped):
        return done(_result(rule, RULE_FAILED, observed=observed, missing=not_called,
                            comment=_bounds_comment(rule, target_set, scoped)))
    if ok:
        return done(_result(rule, RULE_PASSED, observed=observed,
                            comment="Required tool usage satisfied."))

    scope = f" by agent '{label_of(rule.agent_id)}'" if rule.agent_id else ""
    parts: List[str] = []
    if not_called:
        parts.append(f"not called: {_named(not_called, label_of)}")
    if called_but_failed:
        parts.append(f"called but did not succeed: {_named(called_but_failed, label_of)}")
    if per_tool_reasons:
        reasons = "; ".join(
            f"{label_of(tool_id)}: {reason}" for tool_id, reason in sorted(per_tool_reasons.items())
        )
        parts.append(f"result/argument checks failed — {reasons}")
    comment = f"Required tool usage not satisfied{scope}: " + "; ".join(parts) + "."
    return done(_result(rule, RULE_FAILED, observed=observed, missing=not_called,
                        failed=called_but_failed, check_failures=per_tool_reasons, comment=comment))


def _qualifying_calls(rule: ToolUsageRule, target_set: Set[str], scoped: List[Dict[str, Any]]) -> int:
    return sum(
        1
        for e in scoped
        if e.get("tool_id") in target_set
        and (not rule.require_success or e.get("status") == "succeeded")
    )


def _calls_within_bounds(rule: ToolUsageRule, target_set: Set[str], scoped: List[Dict[str, Any]]) -> bool:
    if rule.min_calls is None and rule.max_calls is None:
        return True
    count = _qualifying_calls(rule, target_set, scoped)
    if rule.min_calls is not None and count < rule.min_calls:
        return False
    if rule.max_calls is not None and count > rule.max_calls:
        return False
    return True


def _bounds_comment(rule: ToolUsageRule, target_set: Set[str], scoped: List[Dict[str, Any]]) -> str:
    count = _qualifying_calls(rule, target_set, scoped)
    return f"Call count {count} outside bounds (min={rule.min_calls}, max={rule.max_calls})."


def _tool_events(tool_id: str, scoped: List[Dict[str, Any]], require_success: bool) -> List[Dict[str, Any]]:
    """This tool's events in scope; only successful ones when require_success."""
    return [
        e for e in scoped
        if e.get("tool_id") == tool_id and (not require_success or e.get("status") == "succeeded")
    ]


def _per_tool_failure(rule: ToolUsageRule, tool_id: str, scoped: List[Dict[str, Any]]) -> Optional[str]:
    """Reason the per-tool checks failed for ``tool_id``, or None if they pass.

    When ``require_success`` is set, result/argument checks inspect only the
    tool's successful events, so a failed call cannot satisfy them.
    """
    check = rule.per_tool.get(tool_id)
    if check is None:
        return None
    return _per_tool_failure_reason(check, _tool_events(tool_id, scoped, rule.require_success))


def evaluate_rules(
    rules: Iterable[ToolUsageRule],
    events: Iterable[Dict[str, Any]],
    executed_agent_ids: Optional[Set[str]] = None,
    label_of: Optional[Callable[[str], str]] = None,
) -> Dict[str, Any]:
    """Grade every rule and summarize with pass/fail/coverage. ``events`` is one scope slice."""
    events = list(events)
    results = [evaluate_rule(rule, events, executed_agent_ids, label_of) for rule in rules]

    passed = sum(1 for r in results if r["status"] == RULE_PASSED)
    failed = sum(1 for r in results if r["status"] == RULE_FAILED)
    not_evaluated = sum(1 for r in results if r["status"] == RULE_NOT_EVALUATED)
    evaluated = passed + failed

    return {
        "results": results,
        "coverage": {
            "passed": passed,
            "failed": failed,
            "not_evaluated": not_evaluated,
            "evaluated": evaluated,
            "total": len(results),
        },
        # Score is over evaluated rules only; None when nothing could be evaluated.
        "score": (passed / evaluated) if evaluated else None,
        # Healthy only when something was evaluated and nothing failed.
        "passed": failed == 0 and evaluated > 0,
    }


# ---- scope planning --------------------------------------------------------


def _not_evaluated_result(rule: ToolUsageRule, comment: str) -> Dict[str, Any]:
    return {
        "rule_id": rule.id, "operator": rule.operator, "scope": rule.scope,
        "status": RULE_NOT_EVALUATED, "observed_tools": [], "missing_tools": [],
        "forbidden_tools": [], "failed_tools": [], "check_failures": {},
        "call_counts": {}, "successful_call_counts": {}, "comment": comment,
    }


def plan_tool_rule_results(
    rules: Iterable[ToolUsageRule],
    turns: List[Dict[str, Any]],
    conversation_groups: List[List[str]],
    events_by_turn: Dict[str, List[Dict[str, Any]]],
    executed_by_turn: Dict[str, Set[str]],
    label_of: Optional[Callable[[str], str]] = None,
) -> List[Dict[str, Any]]:
    """Grade every rule over its scope and return placed results (no DB, no ORM).

    ``turns`` are ``{"id", "source_conversation_id", "turn_index"}`` dicts;
    ``conversation_groups`` lists turn ids grouped per conversation. Each planned
    entry carries where the result belongs (``case_id`` / ``source_conversation_id``).
    """
    turns_by_id = {t["id"]: t for t in turns}
    by_conversation_turn = {
        (t["source_conversation_id"], t["turn_index"]): t["id"]
        for t in turns
        if t.get("source_conversation_id") is not None and t.get("turn_index") is not None
    }

    def place(rule, result, *, case_id=None, source_conversation_id=None):
        return {
            "rule_id": rule.id, "scope": rule.scope, "case_id": case_id,
            "source_conversation_id": source_conversation_id, "result": result,
        }

    planned: List[Dict[str, Any]] = []
    for rule in rules:
        if rule.scope == "specific_turn":
            target_id = None
            if rule.target_case_id and rule.target_case_id in turns_by_id:
                target_id = rule.target_case_id
            elif rule.target_source_conversation_id is not None and rule.target_turn_index is not None:
                target_id = by_conversation_turn.get(
                    (rule.target_source_conversation_id, rule.target_turn_index)
                )
            if target_id is None:
                planned.append(place(rule, _not_evaluated_result(rule, "Target turn not found in this run.")))
                continue
            result = evaluate_rule(
                rule, events_by_turn.get(target_id, []), executed_by_turn.get(target_id, set()), label_of
            )
            planned.append(place(rule, result, case_id=target_id))

        elif rule.scope == "every_turn":
            for turn in turns:
                tid = turn["id"]
                result = evaluate_rule(
                    rule, events_by_turn.get(tid, []), executed_by_turn.get(tid, set()), label_of
                )
                planned.append(place(rule, result, case_id=tid))

        else:  # conversation: merge every turn's events and grade once
            for group in conversation_groups:
                merged_events: List[Dict[str, Any]] = []
                merged_executed: Set[str] = set()
                for tid in group:
                    merged_events.extend(events_by_turn.get(tid, []))
                    merged_executed |= executed_by_turn.get(tid, set())
                representative = group[0] if group else None
                conversation_id = turns_by_id.get(representative, {}).get("source_conversation_id")
                result = evaluate_rule(rule, merged_events, merged_executed, label_of)
                planned.append(place(
                    rule, result,
                    case_id=None if conversation_id is not None else representative,
                    source_conversation_id=conversation_id,
                ))

    return planned


def summarize_planned_results(planned: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Run-level Tool Usage summary (accuracy + coverage) from planned results."""
    statuses = [entry["result"]["status"] for entry in planned]
    passed = statuses.count(RULE_PASSED)
    failed = statuses.count(RULE_FAILED)
    not_evaluated = statuses.count(RULE_NOT_EVALUATED)
    evaluated = passed + failed
    accuracy = (passed / evaluated) if evaluated else 0.0

    # How many checks ran at each scope, so the card can say e.g.
    # "2 conversation checks · 13 turn checks".
    by_scope: Dict[str, int] = {}
    for entry in planned:
        scope = entry.get("scope", "every_turn")
        by_scope[scope] = by_scope.get(scope, 0) + 1

    return {
        "avg_score": accuracy,
        "accuracy": accuracy,
        "cases": evaluated,
        "passed": passed,
        "failed": failed,
        "not_evaluated": not_evaluated,
        "by_scope": by_scope,
        "coverage": {
            "passed": passed, "failed": failed, "not_evaluated": not_evaluated,
            "evaluated": evaluated, "total": len(planned),
        },
    }


# ---- human-readable description --------------------------------------------


def _quote_join(items: List[str], conjunction: str) -> str:
    if not items:
        return "a tool"
    quoted = [f'"{item}"' for item in items]
    if len(quoted) == 1:
        return quoted[0]
    return f"{', '.join(quoted[:-1])} {conjunction} {quoted[-1]}"


def _scope_phrase(rule: "ToolUsageRule") -> str:
    if rule.scope == "conversation":
        return "during the conversation"
    if rule.scope == "specific_turn":
        if rule.target_turn_index is not None:
            return f"on turn {rule.target_turn_index + 1}"
        return "on the selected turn"
    return "on every turn"


def describe_tool_rule(
    rule: "ToolUsageRule",
    agent_labels: Optional[Dict[str, str]] = None,
    tool_labels: Optional[Dict[str, str]] = None,
) -> str:
    """A plain-language sentence for a rule, using human labels where available.

    Captured at evaluation time so a later rename never rewrites past results.
    """
    agent_labels = agent_labels or {}
    tool_labels = tool_labels or {}

    subject = agent_labels.get(rule.agent_id, "The agent") if rule.agent_id else "Any agent"
    names = [tool_labels.get(tool_id, tool_id) for tool_id in rule.tool_ids]
    scope_phrase = _scope_phrase(rule)

    if rule.operator == "none":
        return f"{subject} must not use {_quote_join(names, 'or')} {scope_phrase}."
    if rule.operator == "only":
        if not names:
            return f"{subject} must not use any tools {scope_phrase}."
        return f"{subject} may only use {_quote_join(names, 'or')} {scope_phrase}."
    conjunction = "and" if rule.operator == "all" else "or"
    successfully = "successfully " if rule.require_success else ""
    return f"{subject} must {successfully}use {_quote_join(names, conjunction)} {scope_phrase}."


# ---- config parsing + legacy conversion ------------------------------------


def parse_tool_usage_config(
    raw: Optional[Dict[str, Any]],
    *,
    resolve_tool_id=None,
    resolve_agent_id=None,
    all_tool_ids: Optional[List[str]] = None,
) -> ToolUsageConfig:
    """Parse a ``tool_used`` config, converting the legacy single-tool shape.

    ``resolve_tool_id(name) -> id`` and ``resolve_agent_id(label) -> id`` map legacy
    display names to graph ids; when omitted the raw names are kept as-is (useful for
    pure unit tests). A legacy name that a provided resolver cannot map raises.

    ``all_tool_ids`` is the workflow's full tool set, used to expand a legacy
    "any tool" config (``should_call: true`` with no tool named).
    """
    raw = raw or {}
    if "rules" in raw:
        return ToolUsageConfig.model_validate(raw)
    # Legacy shape: a single tool/agent, or a bare should_call ("any" / "no" tool).
    if "tool" in raw or "node" in raw or "should_call" in raw:
        return ToolUsageConfig(
            rules=[_legacy_rule(raw, resolve_tool_id, resolve_agent_id, all_tool_ids)]
        )
    return ToolUsageConfig(rules=[])


def canonicalize_tool_usage_config(
    raw: Optional[Dict[str, Any]],
    *,
    resolve_tool_id=None,
    resolve_agent_id=None,
    all_tool_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Return a ``{"rules": [...]}`` config with every tool/agent reference resolved
    to a canonical id. Raises ``ValueError`` on an unknown or ambiguous name so a
    create/update boundary can refuse to store a non-canonical config.

    Unlike :func:`parse_tool_usage_config`, this also resolves ids/names *inside* an
    already ``rules``-shaped config — the frontend can save legacy names into
    ``tool_ids``/``agent_id``. Resolving an id returns it unchanged (idempotent).
    """
    parsed = parse_tool_usage_config(
        raw,
        resolve_tool_id=resolve_tool_id,
        resolve_agent_id=resolve_agent_id,
        all_tool_ids=all_tool_ids,
    )
    if resolve_tool_id is None and resolve_agent_id is None:
        return parsed.model_dump(mode="json")

    canonical: List[ToolUsageRule] = []
    for rule in parsed.rules:
        tool_ids = [_resolve_or_raise(resolve_tool_id, tool_id, "tool") for tool_id in rule.tool_ids]
        agent_id = _resolve_or_raise(resolve_agent_id, rule.agent_id, "agent")
        per_tool = {
            _resolve_or_raise(resolve_tool_id, tool_id, "tool"): check
            for tool_id, check in rule.per_tool.items()
        }
        canonical.append(
            rule.model_copy(update={"tool_ids": tool_ids, "agent_id": agent_id, "per_tool": per_tool})
        )
    return ToolUsageConfig(rules=canonical).model_dump(mode="json")


def _resolve_or_raise(resolver, value, kind: str):
    if value is None:
        return None
    if resolver is None:
        return value
    resolved = resolver(value)
    if not resolved:
        raise ValueError(f"could not resolve legacy {kind} {value!r} in this workflow")
    return resolved


def _legacy_rule(
    raw: Dict[str, Any],
    resolve_tool_id,
    resolve_agent_id,
    all_tool_ids: Optional[List[str]] = None,
) -> ToolUsageRule:
    tool_name = raw.get("tool")
    tool_id = _resolve_or_raise(resolve_tool_id, tool_name, "tool")
    agent_id = _resolve_or_raise(resolve_agent_id, raw.get("node"), "agent")
    should_call = bool(raw.get("should_call", True))

    per_tool: Dict[str, PerToolCheck] = {}
    if tool_id and should_call and (
        raw.get("result_not_empty") or raw.get("result_contains") or raw.get("expected_args")
    ):
        per_tool[tool_id] = PerToolCheck(
            result_not_empty=bool(raw.get("result_not_empty", False)),
            result_contains=raw.get("result_contains"),
            expected_args=raw.get("expected_args"),
        )

    operator, tool_ids = _legacy_operator_and_tools(tool_id, should_call, all_tool_ids)
    return ToolUsageRule(
        id="legacy-tool-rule",
        tool_ids=tool_ids,
        operator=operator,
        agent_id=agent_id,
        scope="every_turn",
        per_tool=per_tool,
    )


def _legacy_operator_and_tools(tool_id, should_call, all_tool_ids):
    """Map a legacy (tool, should_call) pair to a canonical operator + tool list.

    The old UI allowed "any tool" by leaving the tool empty, so a bare should_call
    is expanded: true -> "any" over every workflow tool; false -> "only" nothing.
    """
    if tool_id:
        return ("all" if should_call else "none"), [tool_id]
    if should_call:
        return "any", sorted(all_tool_ids or [])
    return "only", []
