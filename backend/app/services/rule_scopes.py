"""Rule scoping shared by every rule-based evaluation technique.

A rule is graded over a *scope unit* rather than always over one turn:

    every_turn     — graded once per turn (one result per turn)
    conversation   — graded once per conversation, over all of its turns
    specific_turn  — graded once per targeted turn, on the turns you picked

Conversation scope is what makes "a ticket is created once per conversation"
expressible: the assertion holds when it is satisfied somewhere in the
conversation, not on every single turn.

This module owns the scope contract (the rule fields and the planner); each
technique supplies its own grading function.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, List, Optional

from pydantic import BaseModel, Field, model_validator

SCOPES = ("specific_turn", "every_turn", "conversation")

RULE_PASSED = "passed"
RULE_FAILED = "failed"
RULE_NOT_EVALUATED = "not_evaluated"


class ScopedRule(BaseModel):
    """Fields every scoped rule carries, whatever it asserts."""

    id: str
    scope: str = "every_turn"

    # Stable turn targeting: imported turns use (source_conversation_id, turn_index)
    # so a rule survives a conversation re-import; manual cases use case_id.
    # A specific-turn rule may target several turns; the singular fields are the
    # one-turn shape saved before that, and are read as a one-item list.
    target_case_id: Optional[str] = None
    target_case_ids: List[str] = Field(default_factory=list)
    target_source_conversation_id: Optional[str] = None
    target_turn_index: Optional[int] = None
    target_turn_indexes: List[int] = Field(default_factory=list)

    @property
    def targeted_case_ids(self) -> List[str]:
        """Every case id this rule targets, in order, without duplicates."""
        return _ordered_unique([*self.target_case_ids, self.target_case_id])

    @property
    def targeted_turn_indexes(self) -> List[int]:
        """Every turn index this rule targets, in order, without duplicates."""
        return _ordered_unique([*self.target_turn_indexes, self.target_turn_index])

    @model_validator(mode="after")
    def _check_scope(self) -> "ScopedRule":
        if self.scope not in SCOPES:
            raise ValueError(f"scope must be one of {SCOPES}, got {self.scope!r}")
        if self.scope == "specific_turn":
            has_cases = bool(self.targeted_case_ids)
            has_turns = (
                self.target_source_conversation_id is not None
                and bool(self.targeted_turn_indexes)
            )
            if not (has_cases or has_turns):
                raise ValueError(
                    f"rule {self.id!r}: specific_turn scope requires target_case_ids or "
                    "(target_source_conversation_id + target_turn_indexes)"
                )
        return self


def _ordered_unique(values: Iterable[Any]) -> List[Any]:
    """Drop ``None`` and duplicates, keeping first-seen order."""
    return list(dict.fromkeys(value for value in values if value is not None))


def scope_phrase(rule: ScopedRule) -> str:
    """The "when" half of a rule's plain-language description."""
    if rule.scope == "conversation":
        return "during the conversation"
    if rule.scope == "specific_turn":
        turns = rule.targeted_turn_indexes
        if len(turns) == 1:
            return f"on turn {turns[0] + 1}"
        if turns:
            return f"on turns {', '.join(str(turn + 1) for turn in turns)}"
        return "on the selected turns"
    return "on every turn"


def plan_rule_results(
    rules: Iterable[ScopedRule],
    turns: List[Dict[str, Any]],
    conversation_groups: List[List[str]],
    grade: Callable[[ScopedRule, List[str]], Dict[str, Any]],
    missing_target: Callable[[ScopedRule, Optional[str]], Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Grade every rule over its scope and return placed results (no DB, no ORM).

    ``turns`` are ``{"id", "source_conversation_id", "turn_index"}`` dicts;
    ``conversation_groups`` lists turn ids grouped per conversation. ``grade``
    receives the rule and the turn ids in scope. Each planned entry carries where
    the result belongs (``case_id`` / ``source_conversation_id``).

    A specific-turn rule targeting several turns is graded once per turn, so a
    result always names the turn it judged.
    """
    turns_by_id = {turn["id"]: turn for turn in turns}
    by_conversation_turn = {
        (turn["source_conversation_id"], turn["turn_index"]): turn["id"]
        for turn in turns
        if turn.get("source_conversation_id") is not None and turn.get("turn_index") is not None
    }

    planned: List[Dict[str, Any]] = []
    for rule in rules:
        if rule.scope == "specific_turn":
            found, missing = _target_turn_ids(rule, turns_by_id, by_conversation_turn)
            for target_id in found:
                planned.append(_place(rule, grade(rule, [target_id]), case_id=target_id))
            for description in missing:
                planned.append(_place(rule, missing_target(rule, description)))

        elif rule.scope == "every_turn":
            for turn in turns:
                planned.append(_place(rule, grade(rule, [turn["id"]]), case_id=turn["id"]))

        else:  # conversation: grade once over all of the conversation's turns
            for group in conversation_groups:
                representative = group[0] if group else None
                conversation_id = turns_by_id.get(representative, {}).get(
                    "source_conversation_id"
                )
                planned.append(
                    _place(
                        rule,
                        grade(rule, list(group)),
                        # Manual (non-imported) cases have no conversation id to
                        # point at, so the result is placed on the first turn.
                        case_id=None if conversation_id is not None else representative,
                        source_conversation_id=conversation_id,
                    )
                )

    return planned


def _rule_targets(rule: ScopedRule) -> List["tuple[Optional[str], Optional[int]]"]:
    """The turns a specific-turn rule points at, as (case id, turn index) pairs.

    The builder writes both lists in the same order, so equal-length lists pair up
    positionally; anything else (a case-only rule, or lists that drifted apart) is
    treated as separate targets.
    """
    case_ids = rule.targeted_case_ids
    turn_indexes = rule.targeted_turn_indexes
    if case_ids and turn_indexes and len(case_ids) == len(turn_indexes):
        return list(zip(case_ids, turn_indexes))
    return [(case_id, None) for case_id in case_ids] + [
        (None, turn_index) for turn_index in turn_indexes
    ]


def _target_turn_ids(
    rule: ScopedRule,
    turns_by_id: Dict[str, Dict[str, Any]],
    by_conversation_turn: Dict[Any, str],
) -> "tuple[List[str], List[Optional[str]]]":
    """Resolve a specific-turn rule's targets to turn ids in the run.

    Returns the ids that are in this run, plus one description per target that is
    not, so a re-imported or trimmed dataset reports which turn went missing
    instead of silently grading fewer turns. A target resolves by case id, or by
    its (conversation, turn) pair once a re-import has replaced the case id.
    """
    conversation_id = rule.target_source_conversation_id
    found: List[str] = []
    missing: List[Optional[str]] = []

    for case_id, turn_index in _rule_targets(rule):
        if case_id is not None and case_id in turns_by_id:
            found.append(case_id)
            continue
        paired = (
            by_conversation_turn.get((conversation_id, turn_index))
            if conversation_id is not None and turn_index is not None
            else None
        )
        if paired is not None:
            found.append(paired)
        else:
            missing.append(f"turn {turn_index + 1}" if turn_index is not None else None)

    # A rule that names no turn at all is rejected when parsed, but a rule built
    # directly would otherwise plan nothing and disappear from the results.
    if not found and not missing:
        missing.append(None)

    return _ordered_unique(found), missing


def _place(rule: ScopedRule, result: Dict[str, Any], *, case_id=None, source_conversation_id=None):
    return {
        "rule_id": rule.id,
        "scope": rule.scope,
        "case_id": case_id,
        "source_conversation_id": source_conversation_id,
        "result": result,
    }


def summarize_planned_results(planned: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Run-level summary (accuracy + coverage) for one technique's planned results."""
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
