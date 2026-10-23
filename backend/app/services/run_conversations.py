"""A run's results by conversation, graded by one rule for the checks and the older methods.

Pure: no DB, engine or ORM, so the run (which stores the counts) and the API (which shows
each conversation) read results the same way. Rows are duck-typed: cases have ``id``,
``source_conversation_id``, ``turn_index`` and ``created_at``; results have ``case_id``,
``status`` and ``metrics``; rule rows have ``case_id``, ``source_conversation_id``,
``scope`` and ``status``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

PASSED = "passed"
FAILED = "failed"
NOT_EVALUATED = "not_evaluated"

# Stored with a run's summary: how many of its conversations passed, failed or were not evaluated.
CONVERSATIONS_KEY = "_conversations"

_SCORED = "scored"
_EXECUTION_FAILED = "execution_failed"
_SKIPPED = "skipped"
_SCORING_FAILED = "scoring_failed"
_TURN_SCOPES = frozenset({"every_turn", "specific_turn", "turn"})

# The runner's skip errors, in the words the results use.
_SKIP_REASONS = {
    "Skipped: an earlier turn is waiting for human input": (
        "This turn did not run because the conversation was waiting for a person."
    ),
    "Skipped: an earlier turn was not persisted to memory": (
        "This turn did not run because an earlier turn failed."
    ),
    "Skipped: turn has no 'message' field, so it cannot join the conversation's memory": (
        "This turn did not run because it has no message."
    ),
}


@dataclass
class StoredResult:
    """What the verdicts read from a stored result, kept by the run as it stores each turn."""

    case_id: Any
    status: Optional[str]
    metrics: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


@dataclass
class TurnOutcome:
    case: Any
    result: Any = None
    rules: List[Any] = field(default_factory=list)
    number: int = 0
    verdict: str = NOT_EVALUATED
    # Its grading broke: a method or check could not grade it, or scoring failed.
    broken: bool = False


@dataclass
class ConversationOutcome:
    key: str
    turns: List[TurnOutcome]
    rules: List[Any] = field(default_factory=list)
    verdict: str = NOT_EVALUATED


@dataclass
class RunOutcome:
    conversations: List[ConversationOutcome]
    unplaced: List[Any] = field(default_factory=list)

    def counts(self) -> Dict[str, int]:
        verdicts = [conversation.verdict for conversation in self.conversations]
        return {
            "total": len(verdicts),
            "passed": verdicts.count(PASSED),
            "failed": verdicts.count(FAILED),
            "not_evaluated": verdicts.count(NOT_EVALUATED),
        }


def turn_verdict(
    status: Optional[str], metrics: Optional[Dict[str, Any]], rule_statuses: Iterable[str], rules_broke: bool = False
) -> str:
    """Whether a stored turn passed, failed or was not evaluated, from its methods and its checks."""
    statuses = list(rule_statuses)
    # A crash is what a customer would have seen.
    if status == _EXECUTION_FAILED or FAILED in statuses:
        return FAILED
    if status not in (None, _SCORED):
        return NOT_EVALUATED
    values = [value for value in (metrics or {}).values() if isinstance(value, dict)]
    graded = [value for value in values if not value.get("not_evaluated") and not value.get("error")]
    if any(not value.get("passed") for value in graded):
        return FAILED
    # A method or check that broke leaves the turn ungraded unless another one failed it.
    if rules_broke or any(value.get("error") for value in values):
        return NOT_EVALUATED
    if graded or PASSED in statuses:
        return PASSED
    return NOT_EVALUATED


def _broke(rule: Any) -> bool:
    """A check row that could not be graded, as when the AI grader did not answer."""
    details = getattr(rule, "details", None)
    return isinstance(details, dict) and bool(details.get("error"))


def _grading_broke(turn: TurnOutcome, methods: bool) -> bool:
    """A method could not grade the turn; checks say so on their own rows."""
    result = turn.result
    if result is None:
        return False
    # Older methods grade as each turn is stored, so a turn that failed scoring was never graded by them.
    if methods and getattr(result, "status", None) == _SCORING_FAILED:
        return True
    metrics = getattr(result, "metrics", None) or {}
    return any(isinstance(value, dict) and value.get("error") for value in metrics.values())


def _ran(turn: TurnOutcome) -> bool:
    """Whether the turn played: it ran, crashed, or ran but could not be graded.

    Results from before statuses were stored keep a null status only when they have no
    metrics, and nothing proves those ran.
    """
    if turn.result is None:
        return False
    status = getattr(turn.result, "status", None)
    if status is None:
        return bool(getattr(turn.result, "metrics", None))
    return status in (_SCORED, _EXECUTION_FAILED, _SCORING_FAILED)


def conversation_verdict(turns: List[TurnOutcome], rule_statuses: Iterable[str], rules_broke: bool = False) -> str:
    """Failed when a turn or a whole-conversation check failed; a half-run, or grading that broke, never passes."""
    seen = [turn.verdict for turn in turns] + list(rule_statuses)
    if FAILED in seen:
        return FAILED
    if any(not _ran(turn) or turn.broken for turn in turns) or rules_broke:
        return NOT_EVALUATED
    if PASSED in seen:
        return PASSED
    return NOT_EVALUATED


def conversation_key(case: Any) -> str:
    return str(case.source_conversation_id or case.id)


def build_run_outcome(
    cases: Iterable[Any], results: Iterable[Any], rules: Iterable[Any], methods: bool = True
) -> RunOutcome:
    """Group a run's turns as the run did, place each rule row on its turn or conversation, and grade both.

    ``methods`` is False for a run graded by checks alone.
    """
    result_by_case = {str(result.case_id): result for result in results}
    groups: Dict[str, List[Any]] = {}
    for case in sorted(cases, key=lambda case: str(case.id)):
        groups.setdefault(conversation_key(case), []).append(case)

    conversations: List[ConversationOutcome] = []
    turn_by_case: Dict[str, TurnOutcome] = {}
    for key, group in groups.items():
        group.sort(key=lambda case: (case.turn_index or 0, case.created_at))
        turns = []
        for number, case in enumerate(group, start=1):
            turn = TurnOutcome(case=case, result=result_by_case.get(str(case.id)), number=number)
            turn_by_case[str(case.id)] = turn
            turns.append(turn)
        conversations.append(ConversationOutcome(key=key, turns=turns))

    by_key = {conversation.key: conversation for conversation in conversations}
    unplaced: List[Any] = []
    for rule in rules:
        turn = turn_by_case.get(str(rule.case_id)) if rule.case_id else None
        if turn is not None and rule.scope in _TURN_SCOPES:
            turn.rules.append(rule)
            continue
        # Whole-conversation rows sit on their conversation, or on its first turn when it has no id.
        if turn is not None:
            key = conversation_key(turn.case)
        else:
            key = str(rule.source_conversation_id) if rule.source_conversation_id else None
        conversation = by_key.get(key) if key else None
        if conversation is None:
            unplaced.append(rule)
        else:
            conversation.rules.append(rule)

    for conversation in conversations:
        # A whole-conversation check that failed names the turns it failed on; those turns failed too.
        failed_on = {number for rule in conversation.rules for number in _failed_turn_numbers(rule)}
        for turn in conversation.turns:
            statuses = [rule.status for rule in turn.rules] + ([FAILED] if turn.number in failed_on else [])
            rules_broke = any(_broke(rule) for rule in turn.rules)
            turn.broken = rules_broke or _grading_broke(turn, methods)
            if turn.result is None:
                turn.verdict = FAILED if FAILED in statuses else NOT_EVALUATED
            else:
                turn.verdict = turn_verdict(
                    getattr(turn.result, "status", None), getattr(turn.result, "metrics", None), statuses, rules_broke
                )
        conversation.verdict = conversation_verdict(
            conversation.turns,
            [rule.status for rule in conversation.rules],
            any(_broke(rule) for rule in conversation.rules),
        )
    return RunOutcome(conversations=conversations, unplaced=unplaced)


def _failed_turn_numbers(rule: Any) -> List[int]:
    details = getattr(rule, "details", None)
    turns = details.get("turns") if isinstance(details, dict) and getattr(rule, "status", None) == FAILED else None
    return [number for number in turns if isinstance(number, int)] if isinstance(turns, list) else []


def turn_reason(turn: TurnOutcome) -> Optional[str]:
    """Why a turn crashed or was not evaluated; a failed check or method speaks for itself."""
    result = turn.result
    if result is None:
        return "This turn has no result in this run."
    status = getattr(result, "status", None)
    error = getattr(result, "error", None)
    if status is None and not getattr(result, "metrics", None):
        return error or "This turn was not scored."
    if status == _EXECUTION_FAILED:
        return error or "The turn did not finish."
    if status == _SKIPPED:
        return _SKIP_REASONS.get(error or "") or error or "This turn did not run."
    if status == _SCORING_FAILED:
        return "The turn ran, but it could not be graded."
    if turn.verdict != NOT_EVALUATED:
        return None
    values = [value for value in (getattr(result, "metrics", None) or {}).values() if isinstance(value, dict)]
    if any(value.get("error") for value in values):
        return "A method could not grade this turn."
    for value in values:
        if value.get("not_evaluated") and value.get("comment"):
            return value["comment"]
    for rule in turn.rules:
        comment = (rule.details or {}).get("comment")
        if comment:
            return comment
    # Nothing graded this turn, which is not a problem in itself.
    return None


def as_text(value: Any) -> Optional[str]:
    """A stored value as plain text: a wrapped string unwrapped, anything else as JSON."""
    if value is None:
        return None
    if isinstance(value, dict):
        for key in ("value", "text"):
            if list(value.keys()) == [key]:
                return as_text(value[key])
        return json.dumps(value, ensure_ascii=False) if value else None
    if isinstance(value, str):
        return value.strip() or None
    return json.dumps(value, ensure_ascii=False)


def reply_of(actual_output: Any) -> Optional[str]:
    """The reply live chat would show."""
    if isinstance(actual_output, dict):
        for key in ("message", "response"):
            text = actual_output.get(key)
            if isinstance(text, str) and text.strip():
                return text.strip()
    return as_text(actual_output)


def message_of(case: Any, trace_input: Any) -> str:
    """What the customer said: what the run sent, else the dataset's turn."""
    if isinstance(trace_input, str) and trace_input.strip():
        return trace_input.strip()
    if isinstance(trace_input, dict) and isinstance(trace_input.get("message"), str):
        return trace_input["message"].strip()
    message = (getattr(case, "input_data", None) or {}).get("message")
    return message.strip() if isinstance(message, str) else ""
