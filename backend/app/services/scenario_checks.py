"""Should / Should not checks: the check model, its sentence, and grading over a run's turns.

Pure: no DB, engine or LLM. The AI-graded kind gets its verdicts through an injected judge.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, Iterable, List, Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.services.evaluation_text import names_equal, normalize_text
from app.services.rule_scopes import RULE_FAILED, RULE_NOT_EVALUATED, RULE_PASSED

logger = logging.getLogger(__name__)

CHECKS_TECHNIQUE = "checks"

KINDS = ("reply_mentions", "reply_meets", "tool_called", "step_runs", "route_taken", "state_equals")
LEVELS = ("every_conversation", "conversation", "turn")

# A judge score at or above this meets the expectation, as for llm_judge's default.
JUDGE_PASS_SCORE = 0.5
# BaseTool records a refused call with this reason; it never ran.
REFUSED_CALL_PREFIX = "required parameters are missing or empty"
# Enough of the opening message to notice a turn that changed under a check.
FINGERPRINT_CHARS = 120


class Check(BaseModel):
    """One expectation about what should or should not happen."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(min_length=1, max_length=128)
    expect: Literal["should", "should_not"] = "should"
    kind: Literal[
        "reply_mentions", "reply_meets", "tool_called", "step_runs", "route_taken", "state_equals"
    ]
    level: Literal["every_conversation", "conversation", "turn"] = "every_conversation"
    # Every conversation only: hold on every turn, or at some point.
    when: Literal["every_turn", "anywhere"] = "anywhere"

    conversation_id: Optional[str] = None
    case_id: Optional[str] = None
    turn_index: Optional[int] = None
    turn_message: Optional[str] = None

    text: Optional[str] = None
    rubric: Optional[str] = None
    tool: Optional[str] = None
    tool_name: Optional[str] = None
    agent: Optional[str] = None
    agent_name: Optional[str] = None
    args: Dict[str, Any] = Field(default_factory=dict)
    step: Optional[str] = None
    step_name: Optional[str] = None
    router: Optional[str] = None
    router_name: Optional[str] = None
    branch: Optional[str] = None
    branch_label: Optional[str] = None
    key: Optional[str] = None
    value: Any = None

    @model_validator(mode="after")
    def _check_fields(self) -> "Check":
        if self.level == "conversation" and not self.conversation_id:
            raise ValueError(f"check {self.id!r}: pick the conversation it is about")
        if self.level == "turn" and not (
            self.case_id or (self.conversation_id and self.turn_index is not None)
        ):
            raise ValueError(f"check {self.id!r}: pick the turn it is about")
        missing = {
            "reply_mentions": not _filled(self.text),
            "reply_meets": not _filled(self.rubric),
            "tool_called": not (_filled(self.tool) or _filled(self.tool_name)),
            "step_runs": not (_filled(self.step) or _filled(self.step_name)),
            "route_taken": not (_filled(self.router) or _filled(self.router_name))
            or not (_filled(self.branch) or _filled(self.branch_label)),
            "state_equals": not _filled(self.key) or self.value is None,
        }[self.kind]
        if missing:
            raise ValueError(f"check {self.id!r}: fill in what the {self.kind} check looks for")
        return self

    @property
    def per_turn(self) -> bool:
        """Graded turn by turn rather than once over the conversation."""
        return self.level == "turn" or (self.level == "every_conversation" and self.when == "every_turn")


class ChecksConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    checks: List[Check] = Field(default_factory=list)
    llm_provider_id: Optional[str] = None

    @model_validator(mode="after")
    def _unique_ids(self) -> "ChecksConfig":
        seen: set = set()
        for check in self.checks:
            if check.id in seen:
                raise ValueError(f"duplicate check id {check.id!r}")
            seen.add(check.id)
        return self


def parse_checks_config(raw: Optional[Dict[str, Any]]) -> ChecksConfig:
    """Parse a stored checks config; raises ValueError when it is not valid."""
    try:
        return ChecksConfig.model_validate(raw or {})
    except Exception as exc:  # pydantic's ValidationError is a ValueError subclass
        raise ValueError(str(exc)) from exc


def _filled(value: Any) -> bool:
    return bool(normalize_text(value))


def fingerprint(message: Any) -> str:
    return " ".join(normalize_text(message).lower().split())[:FINGERPRINT_CHARS]


# ---- sentences -----------------------------------------------------------------


def describe_check(check: Check) -> str:
    """The check read back as one sentence, e.g. 'The reply should never mention "RingGo".'"""
    once = check.level == "conversation" or (check.level == "every_conversation" and check.when == "anywhere")
    if check.expect == "should_not":
        modal = "should never" if once else "should not"
    else:
        modal = "should"

    prefix = ""
    if check.level == "every_conversation":
        if check.when == "every_turn":
            prefix = "On every turn, "
        elif check.expect == "should":
            prefix = "In every conversation, at some point, "
        else:
            prefix = "In every conversation, "
    elif check.level == "conversation" and check.expect == "should":
        prefix = "At some point, "

    sentence = prefix + _clause(check, modal)
    return sentence[0].upper() + sentence[1:] + "."


def _clause(check: Check, modal: str) -> str:
    if check.kind == "reply_mentions":
        return f'the reply {modal} mention "{normalize_text(check.text)}"'
    if check.kind == "reply_meets":
        subject = "the reply" if check.per_turn else "the agent"
        return f'{subject} {modal} do this: "{normalize_text(check.rubric)}"'
    if check.kind == "tool_called":
        clause = f'the tool "{tool_display(check)}" {modal} be called'
        if _filled(check.agent_name) or _filled(check.agent):
            clause += f' by "{normalize_text(check.agent_name or check.agent)}"'
        if check.args:
            clause += f" with {_pairs(check.args)}"
        return clause
    if check.kind == "step_runs":
        return f'the step "{step_display(check)}" {modal} run'
    if check.kind == "route_taken":
        return f'the router "{router_display(check)}" {modal} take "{branch_display(check)}"'
    return f'the remembered value "{normalize_text(check.key)}" {modal} be "{_value_text(check.value)}"'


def tool_display(check: Check) -> str:
    return normalize_text(check.tool_name or check.tool)


def step_display(check: Check) -> str:
    return normalize_text(check.step_name or check.step)


def router_display(check: Check) -> str:
    return normalize_text(check.router_name or check.router)


def branch_display(check: Check) -> str:
    return normalize_text(check.branch_label or check.branch)


def _value_text(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True)
    return normalize_text(value)


def _pairs(values: Dict[str, Any]) -> str:
    return ", ".join(f"{key} = {_value_text(value)}" for key, value in values.items())


# ---- what a turn did -------------------------------------------------------------


@dataclass
class TurnRecord:
    """What one turn of a run did, as far as checks can see."""

    case_id: str
    conversation_key: str
    turn_index: Optional[int]
    position: int
    message: str
    ran: bool = True
    crashed: bool = False
    error: Optional[str] = None
    waiting_for_human: bool = False
    reply: str = ""
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    steps: List[Dict[str, Any]] = field(default_factory=list)
    routes: List[Dict[str, Any]] = field(default_factory=list)
    state: Dict[str, Any] = field(default_factory=dict)
    # Why a turn that did not run (ran=False) has nothing to check.
    skip_reason: str = ""

    @property
    def label(self) -> str:
        return f"Turn {self.position + 1}"


UNREADABLE_TURN = "This turn ran, but its result could not be read."


def skip_reason(earlier: List["TurnRecord"]) -> str:
    """Why a turn without a record did not run, from the turns before it."""
    if any(turn.crashed for turn in earlier):
        return "This turn did not run because an earlier turn failed."
    if any(turn.waiting_for_human for turn in earlier):
        return "This turn did not run because the conversation was waiting for a person."
    return "This turn did not run."


def tool_calls_from_events(
    events: Iterable[Dict[str, Any]], raw_arguments: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """Tool events with the real arguments the run captured; stored events are redacted."""
    raw_arguments = raw_arguments or {}
    calls = []
    for event in events or []:
        if not isinstance(event, dict):
            continue
        error = normalize_text(event.get("error"))
        calls.append(
            {
                "tool_id": event.get("tool_id"),
                "tool_name": event.get("tool_name"),
                "agent_id": event.get("agent_id"),
                "arguments": raw_arguments.get(event.get("event_id"), event.get("arguments")),
                "shown_arguments": event.get("arguments"),
                "status": event.get("status"),
                "refused": error.lower().startswith(REFUSED_CALL_PREFIX),
            }
        )
    return calls


# ---- names in the workflow that ran ---------------------------------------------------


@dataclass
class Targets:
    """A check's tool, agent, step or router, resolved to ids in the workflow that ran."""

    tool_ids: List[str] = field(default_factory=list)
    agent_id: Optional[str] = None
    node_id: Optional[str] = None
    # The tool's name in the workflow that ran, for what a check saw.
    name: Optional[str] = None
    problem: Optional[str] = None


def resolve_targets(check: Check, catalog: Optional[Dict[str, List[Dict[str, Any]]]]) -> Targets:
    """Match ids first, then names, so a check survives a copied or re-saved workflow."""
    if check.kind not in ("tool_called", "step_runs", "route_taken") or catalog is None:
        return Targets(tool_ids=[check.tool] if check.tool else [], agent_id=check.agent,
                       node_id=check.step or check.router)

    if check.kind == "tool_called":
        agents = catalog.get("agents") or []
        agent_id = None
        if _filled(check.agent) or _filled(check.agent_name):
            agent_id, problem = _resolve(agents, check.agent, check.agent_name, ("id", "label"))
            if problem:
                return Targets(problem=f'The agent "{normalize_text(check.agent_name or check.agent)}" {problem}.')
        fields = ("id", "name", "label")
        all_tools = [tool for agent in agents for tool in agent.get("tools") or []]
        tools = [tool for agent in agents if agent_id in (None, agent.get("id")) for tool in agent.get("tools") or []]
        # A name on several tool nodes means any of them: a call to either counts.
        tool_ids = _matching_ids(tools, check.tool, check.tool_name, fields)
        if not tool_ids:
            if agent_id and _matching_ids(all_tools, check.tool, check.tool_name, fields):
                agent = normalize_text(check.agent_name or check.agent)
                return Targets(problem=f'The agent "{agent}" does not use the tool "{tool_display(check)}" in the workflow that ran.')
            return Targets(problem=f'The tool "{tool_display(check)}" is not in the workflow that ran.')
        name = next((tool.get("name") for tool in tools if tool.get("id") in tool_ids), None)
        return Targets(tool_ids=tool_ids, agent_id=agent_id, name=name)

    if check.kind == "step_runs":
        node_id, problem = _resolve(catalog.get("action_nodes") or [], check.step, check.step_name, ("id", "label"))
        if problem:
            return Targets(problem=f'The step "{step_display(check)}" {problem}.')
        return Targets(node_id=node_id)

    node_id, problem = _resolve(catalog.get("routers") or [], check.router, check.router_name, ("id", "label"))
    if problem:
        return Targets(problem=f'The router "{router_display(check)}" {problem}.')
    return Targets(node_id=node_id)


def _resolve(
    entries: List[Dict[str, Any]], ref_id: Optional[str], name: Optional[str], fields: Tuple[str, ...]
) -> Tuple[Optional[str], Optional[str]]:
    """(id, None) when found once; (None, problem) when missing or ambiguous."""
    ids = _matching_ids(entries, ref_id, name, fields)
    if len(ids) == 1:
        return ids[0], None
    if ids:
        return None, "matches more than one node in the workflow that ran"
    return None, "is not in the workflow that ran"


def _matching_ids(
    entries: List[Dict[str, Any]], ref_id: Optional[str], name: Optional[str], fields: Tuple[str, ...]
) -> List[str]:
    """The id when it is there, else every entry the name (or the id taken as a name) matches."""
    if ref_id and any(entry.get("id") == ref_id for entry in entries):
        return [ref_id]
    for wanted in (name, ref_id):
        if _filled(wanted):
            ids = sorted({entry.get("id") for entry in entries
                          if any(names_equal(entry.get(key), wanted) for key in fields)})
            if ids:
                return ids
    return []


# ---- one turn ---------------------------------------------------------------------


def turn_fact(check: Check, targets: Targets, turn: TurnRecord) -> Tuple[Optional[bool], str]:
    """Whether the check's thing happened on this turn, and what was seen.

    None means the turn cannot tell, such as a reply check on a turn waiting for a person.
    """
    if check.kind == "reply_mentions":
        if turn.crashed or turn.waiting_for_human:
            return None, "There was no reply to read."
        text = normalize_text(check.text)
        mentioned = text.lower() in turn.reply.lower()
        return mentioned, f'The reply {"mentioned" if mentioned else "did not mention"} "{text}".'

    if check.kind == "tool_called":
        return _tool_fact(check, targets, turn)

    if check.kind == "step_runs":
        steps = [step for step in turn.steps if _same_node(step.get("id"), targets.node_id)]
        if any(step.get("status") == "success" and not step.get("error") for step in steps):
            return True, "The step ran."
        if steps:
            return False, "The step started but did not finish."
        return False, "The step did not run."

    if check.kind == "route_taken":
        routes = [route for route in turn.routes if _same_node(route.get("id"), targets.node_id)]
        if not routes:
            return False, "The router did not run."
        for route in routes:
            if (_filled(check.branch) and names_equal(route.get("route"), check.branch)) or (
                _filled(check.branch_label) and names_equal(route.get("route_label"), check.branch_label)
            ):
                return True, f'The router took "{branch_display(check)}".'
        taken = ", ".join(normalize_text(route.get("route_label") or route.get("route")) or "none" for route in routes)
        return False, f'The router took "{taken}".'

    # state_equals
    key = normalize_text(check.key)
    if key not in turn.state:
        return False, f"{key} was not set."
    actual = turn.state.get(key)
    return same_value(actual, check.value), f'{key} was "{_value_text(actual)}".'


def _tool_fact(check: Check, targets: Targets, turn: TurnRecord) -> Tuple[bool, str]:
    calls = [
        call for call in turn.tool_calls
        if _is_tool(call, targets, tool_display(check))
        and (targets.agent_id is None or call.get("agent_id") == targets.agent_id)
    ]
    name = targets.name or next((call.get("tool_name") for call in calls if call.get("tool_name")), None) or tool_display(check)
    ran = [call for call in calls if not call.get("refused")]

    def with_values(call: Dict[str, Any]) -> bool:
        return not check.args or args_match(call.get("arguments"), check.args)

    # A refused call never ran: it is not a call, but it is an attempt a "should not" forbids.
    if check.expect == "should_not" and not any(with_values(call) for call in ran):
        if any(call.get("refused") and with_values(call) for call in calls):
            return True, f"{name} was attempted but refused for missing details."
    if not ran:
        return False, f"{name} was not called."
    if not check.args:
        return True, f"{name} was called."
    for call in ran:
        if args_match(call.get("arguments"), check.args):
            return True, f"{name} was called with {_pairs(check.args)}."
    shown = ran[-1].get("shown_arguments")
    seen = _pairs({key: (shown or {}).get(key) for key in check.args}) if isinstance(shown, dict) else "other values"
    return False, f"{name} was called with {seen}."


def _is_tool(call: Dict[str, Any], targets: Targets, name: str) -> bool:
    if targets.tool_ids:
        return call.get("tool_id") in targets.tool_ids
    return names_equal(call.get("tool_name"), name)


def _same_node(observed_id: Any, node_id: Optional[str]) -> bool:
    """A node re-run in a loop is archived as "<id>_<n>"; every run of it counts."""
    observed = str(observed_id or "")
    if not node_id or not observed:
        return False
    if observed == node_id:
        return True
    suffix = observed[len(node_id) + 1:] if observed.startswith(f"{node_id}_") else ""
    return suffix.isdigit()


def args_match(actual: Any, expected: Dict[str, Any]) -> bool:
    if not isinstance(actual, dict):
        return False
    return all(same_value(actual.get(key), value) for key, value in expected.items())


def same_value(actual: Any, expected: Any) -> bool:
    """Equal ignoring case, surrounding spaces and number formatting; a list or object also matches its JSON text."""
    if isinstance(actual, (dict, list)) or isinstance(expected, (dict, list)):
        return _canonical_json(actual) == _canonical_json(expected)
    first, second = normalize_text(actual), normalize_text(expected)
    if first.lower() == second.lower():
        return True
    try:
        return float(first) == float(second)
    except ValueError:
        return False


def _canonical_json(value: Any) -> str:
    # Values typed into a check arrive as text, so text holding JSON compares as that JSON.
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return value
    return json.dumps(value, sort_keys=True, default=str)


# ---- judge ------------------------------------------------------------------------


@dataclass
class JudgeRequest:
    """One AI grading: a reply (one turn) or a whole conversation."""

    check: Check
    turns: List[TurnRecord]

    @property
    def key(self) -> Tuple[str, Tuple[str, ...]]:
        return self.check.id, tuple(turn.case_id for turn in self.turns)


@dataclass
class JudgeVerdict:
    score: Optional[float] = None
    reason: Optional[str] = None
    error: bool = False

    @property
    def met(self) -> bool:
        return self.score is not None and self.score >= JUDGE_PASS_SCORE


Judge = Callable[[JudgeRequest], Awaitable[JudgeVerdict]]


def judge_expectation(check: Check, whole_conversation: bool) -> str:
    """The expectation the judge grades, with its Should / Should not built in."""
    rubric = normalize_text(check.rubric)
    if not whole_conversation:
        verb = "should" if check.expect == "should" else "should not"
        return f"The reply {verb} do this: {rubric}"
    if check.expect == "should":
        return f"At some point in the conversation, the assistant should do this: {rubric}"
    return f"At no point in the conversation should the assistant do this: {rubric}"


def transcript(turns: List[TurnRecord]) -> str:
    lines = []
    for turn in turns:
        lines.append(f"USER: {turn.message}")
        lines.append("ASSISTANT: (no reply, the turn failed)" if turn.crashed else f"ASSISTANT: {turn.reply}")
    return "\n".join(lines)


# ---- planning and grading -------------------------------------------------------------


def target_turn(check: Check, conversations: List[List[TurnRecord]]) -> Tuple[Optional[TurnRecord], str]:
    """The turn a turn-level check is about, or why it cannot be found."""
    turns = [turn for group in conversations for turn in group]
    if check.case_id:
        for turn in turns:
            if turn.case_id == check.case_id:
                return turn, ""
    if check.conversation_id and check.turn_index is not None:
        for turn in turns:
            if turn.conversation_key == check.conversation_id and turn.turn_index == check.turn_index:
                # A re-imported conversation keeps its turn numbers; its message tells a changed turn apart.
                if check.turn_message and fingerprint(turn.message) != fingerprint(check.turn_message):
                    return None, "The turn this check is about has changed since the check was written."
                return turn, ""
    return None, "The turn this check is about is no longer in the dataset."


def judge_requests(
    checks: List[Check], conversations: List[List[TurnRecord]], targets: Dict[str, Targets]
) -> List[JudgeRequest]:
    """Every AI grading the checks need, made once each."""
    requests: List[JudgeRequest] = []
    for check in checks:
        if check.kind != "reply_meets" or targets[check.id].problem:
            continue
        if check.level == "turn":
            turn, _ = target_turn(check, conversations)
            if turn is not None and _has_reply(turn):
                requests.append(JudgeRequest(check, [turn]))
            continue
        for group in _groups_for(check, conversations):
            ran = [turn for turn in group if turn.ran]
            if check.per_turn:
                requests.extend(JudgeRequest(check, [turn]) for turn in ran if _has_reply(turn))
            elif ran:
                requests.append(JudgeRequest(check, ran))
    return requests


async def run_judge(
    requests: List[JudgeRequest],
    judge: Judge,
    concurrency: int = 4,
    budget_seconds: Optional[float] = None,
) -> Dict[Any, JudgeVerdict]:
    """Run the judge over every request, a few at a time; a failed or late call is an error verdict."""
    limit = asyncio.Semaphore(concurrency)
    loop = asyncio.get_running_loop()
    deadline = loop.time() + budget_seconds if budget_seconds else None
    out_of_time = JudgeVerdict(error=True, reason="The AI grader ran out of time for this run.")

    async def one(request: JudgeRequest) -> Tuple[Any, JudgeVerdict]:
        async with limit:
            remaining = None if deadline is None else deadline - loop.time()
            if remaining is not None and remaining <= 0:
                return request.key, out_of_time
            try:
                return request.key, await asyncio.wait_for(judge(request), remaining)
            except Exception:  # pylint: disable=broad-except
                if deadline is not None and loop.time() >= deadline:
                    return request.key, out_of_time
                logger.warning("The AI grader failed on check %s", request.check.id, exc_info=True)
                return request.key, JudgeVerdict(error=True, reason="The AI grader did not answer.")

    return dict(await asyncio.gather(*(one(request) for request in requests)))


_NO_REPLY_WAITING = "The turn was waiting for a person, so there was no reply to grade."
_NO_REPLY_FAILED = "The turn did not finish, so there was no reply to grade."


def _has_reply(turn: TurnRecord) -> bool:
    return turn.ran and not turn.crashed and not turn.waiting_for_human


def _groups_for(check: Check, conversations: List[List[TurnRecord]]) -> List[List[TurnRecord]]:
    if check.level == "every_conversation":
        return [group for group in conversations if group]
    return [group for group in conversations if group and group[0].conversation_key == check.conversation_id]


def grade_checks(
    checks: List[Check],
    conversations: List[List[TurnRecord]],
    targets: Dict[str, Targets],
    verdicts: Dict[Any, JudgeVerdict],
) -> List[Dict[str, Any]]:
    """One planned result per check and conversation (or targeted turn), placed like rule rows."""
    planned: List[Dict[str, Any]] = []
    for check in checks:
        sentence = describe_check(check)
        problem = targets[check.id].problem

        if check.level == "turn":
            turn, missing = target_turn(check, conversations)
            if turn is None or problem:
                # A found turn keeps the row; a lost one stays with its conversation.
                entry = _entry(check, turn, _not_evaluated(sentence, problem or missing))
                if turn is None and check.conversation_id:
                    entry["source_conversation_id"] = check.conversation_id
                planned.append(entry)
                continue
            planned.append(_entry(check, turn, _grade_turn(check, targets[check.id], turn, verdicts, sentence)))
            continue

        groups = _groups_for(check, conversations)
        if not groups and check.level == "conversation":
            planned.append(_entry(check, None, _not_evaluated(
                sentence, "The conversation this check is about is no longer in the dataset.")))
            continue
        for group in groups:
            result = (
                _not_evaluated(sentence, problem)
                if problem
                else _grade_conversation(check, targets[check.id], group, verdicts, sentence)
            )
            planned.append(_entry(check, group[0], result, whole_conversation=True))
    return planned


def _grade_turn(
    check: Check, targets: Targets, turn: TurnRecord, verdicts: Dict[Any, JudgeVerdict], sentence: str
) -> Dict[str, Any]:
    if turn.crashed:
        # A crash is what a customer would have seen, so the check fails.
        return _result(RULE_FAILED, sentence, f"The turn did not finish: {turn.error or 'it failed'}")
    if not turn.ran:
        return _not_evaluated(sentence, turn.skip_reason or "This turn did not run.")
    if check.kind == "reply_meets":
        if turn.waiting_for_human:
            return _not_evaluated(sentence, _NO_REPLY_WAITING)
        return _from_verdict(verdicts.get((check.id, (turn.case_id,))), sentence)
    holds, fact = turn_fact(check, targets, turn)
    if holds is None:
        return _not_evaluated(sentence, fact)
    passed = holds if check.expect == "should" else not holds
    return _result(RULE_PASSED if passed else RULE_FAILED, sentence, fact)


def _grade_conversation(
    check: Check, targets: Targets, group: List[TurnRecord], verdicts: Dict[Any, JudgeVerdict], sentence: str
) -> Dict[str, Any]:
    ran = [turn for turn in group if turn.ran]
    if not ran:
        return _not_evaluated(sentence, "No turn of this conversation ran.")

    if check.kind == "reply_meets" and not check.per_turn:
        return _from_verdict(verdicts.get((check.id, tuple(turn.case_id for turn in ran))), sentence)

    facts: List[Tuple[TurnRecord, Optional[bool], str]] = []
    for turn in ran:
        if check.kind == "reply_meets":
            verdict = verdicts.get((check.id, (turn.case_id,)))
            if not _has_reply(turn):
                facts.append((turn, None, _NO_REPLY_WAITING if turn.waiting_for_human else _NO_REPLY_FAILED))
            elif verdict is None or verdict.error:
                facts.append((turn, None, (verdict.reason if verdict else None) or "The AI grader did not answer."))
            else:
                facts.append((turn, verdict.met, verdict.reason or ""))
        else:
            holds, fact = turn_fact(check, targets, turn)
            facts.append((turn, holds, fact))

    known = [(turn, holds, fact) for turn, holds, fact in facts if holds is not None]
    if not known:
        return _not_evaluated(sentence, facts[0][2] if facts else "Nothing in this conversation could be checked.")

    if check.kind == "reply_meets":
        # The judge already graded each reply against the Should or Should not.
        misses = [(turn, fact) for turn, met, fact in known if not met]
        if misses:
            turn, fact = misses[0]
            return _result(RULE_FAILED, sentence, f"{turn.label}: {fact}".strip(), turns=_numbers(t for t, _ in misses))
        return _result(RULE_PASSED, sentence, f"Met on all {len(known)} turns.")

    hits = [(turn, fact) for turn, holds, fact in known if holds]
    misses = [(turn, fact) for turn, holds, fact in known if not holds]
    if check.expect == "should_not":
        if hits:
            turn, fact = hits[0]
            return _result(RULE_FAILED, sentence, f"{turn.label}: {fact}", turns=_numbers(t for t, _ in hits))
        return _result(RULE_PASSED, sentence, _none_of(len(known)))
    if check.per_turn:
        if misses:
            turn, fact = misses[0]
            return _result(RULE_FAILED, sentence, f"{turn.label}: {fact}", turns=_numbers(t for t, _ in misses))
        return _result(RULE_PASSED, sentence, f"Held on all {len(known)} turns.")
    if hits:
        turn, fact = hits[0]
        return _result(RULE_PASSED, sentence, f"{turn.label}: {fact}", turns=_numbers(t for t, _ in hits))
    turn, fact = misses[-1]
    return _result(RULE_FAILED, sentence, f"{_none_of(len(known))} {turn.label}: {fact}")


def _none_of(count: int) -> str:
    return "Not on its one turn." if count == 1 else f"Not on any of its {count} turns."


def _numbers(turns: Iterable[TurnRecord]) -> List[int]:
    return [turn.position + 1 for turn in turns]


def _from_verdict(verdict: Optional[JudgeVerdict], sentence: str) -> Dict[str, Any]:
    if verdict is None or verdict.error:
        result = _not_evaluated(sentence, (verdict.reason if verdict else None) or "The AI grader did not answer.")
        result["error"] = True
        return result
    observed = verdict.reason or ("The AI grader says it was met." if verdict.met else "The AI grader says it was not met.")
    result = _result(RULE_PASSED if verdict.met else RULE_FAILED, sentence, observed)
    result["score"] = verdict.score
    return result


def _result(status: str, sentence: str, observed: str, turns: Optional[List[int]] = None) -> Dict[str, Any]:
    result = {"status": status, "passed": status == RULE_PASSED, "expected": sentence, "observed": observed}
    if turns:
        result["turns"] = turns
    return result


def _not_evaluated(sentence: str, reason: Optional[str]) -> Dict[str, Any]:
    return {
        "status": RULE_NOT_EVALUATED,
        "passed": False,
        "expected": sentence,
        "observed": "not evaluated",
        "comment": reason or "This check could not be graded.",
    }


def _entry(
    check: Check, turn: Optional[TurnRecord], result: Dict[str, Any], whole_conversation: bool = False
) -> Dict[str, Any]:
    """A planned row: a turn result sits on its case; a conversation result on its conversation."""
    conversation_key = turn.conversation_key if turn else None
    manual = turn is not None and conversation_key == turn.case_id
    on_case = turn is not None and (not whole_conversation or manual)
    return {
        "rule_id": check.id,
        "scope": check.level,
        "case_id": turn.case_id if on_case else None,
        "source_conversation_id": None if manual else conversation_key,
        "result": {
            **result,
            "expect": check.expect,
            "kind": check.kind,
            "level": check.level,
            "when": check.when,
        },
    }


def conversation_verdicts(
    planned: List[Dict[str, Any]], conversations: List[List[TurnRecord]]
) -> Dict[str, str]:
    """passed, failed or not_evaluated per conversation key; a crashed turn fails its conversation."""
    conversation_of = {turn.case_id: turn.conversation_key for group in conversations for turn in group}
    statuses: Dict[str, List[str]] = {}
    for entry in planned:
        key = entry.get("source_conversation_id") or conversation_of.get(entry.get("case_id"))
        if key:
            statuses.setdefault(str(key), []).append(entry["result"]["status"])
    verdicts: Dict[str, str] = {}
    for group in conversations:
        if not group:
            continue
        key = group[0].conversation_key
        seen = statuses.get(key, [])
        if any(turn.crashed for turn in group) or RULE_FAILED in seen:
            verdicts[key] = RULE_FAILED
        elif RULE_PASSED in seen:
            verdicts[key] = RULE_PASSED
        else:
            verdicts[key] = RULE_NOT_EVALUATED
    return verdicts
