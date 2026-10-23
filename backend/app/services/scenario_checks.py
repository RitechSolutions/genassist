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

KINDS = (
    "reply_mentions",
    "reply_meets",
    "reply_matches",
    "reply_grounded",
    "tool_called",
    "only_tools",
    "step_runs",
    "route_taken",
    "state_equals",
    "value_equals",
    "step_fails",
)
LEVELS = ("every_conversation", "conversation", "turn")
# Each reply is graded against its own turn, so these hold on every turn they apply to.
EVERY_TURN_KINDS = frozenset({"reply_matches", "reply_grounded"})
MATCH_MODES = ("exact", "contains", "meaning")
# What an AI grader can read besides the reply.
CONTEXTS = ("expected_reply", "knowledge_base", "tool_calls", "session", "run_value")

# Besides the AI grader, a reply can stick to its source as NLI and Provenance graded it.
GRADERS = ("nli", "similarity")
EMBEDDING_TYPES = ("huggingface", "openai", "bedrock")
# No custom address: the server's own key would be sent to it.
EMBEDDING_FIELDS = ("type", "model_name", "model_id", "region_name")

NO_EXPECTED_REPLY = "This turn has no expected reply in the dataset."
NO_REPLY_TEXT = "The reply was empty, so there was nothing to check."
NO_PASSAGES = "This turn found no knowledge-base passages to check against."
NO_TOOL_CALLS = "This turn called no tools to check against."
NO_SESSION = "This turn has no session values to check against."
# The same reasons, said of a whole conversation.
_CONVERSATION_REASONS = {
    NO_EXPECTED_REPLY: "No turn of this conversation has an expected reply in the dataset.",
    NO_PASSAGES: "No turn of this conversation found knowledge-base passages to check against.",
    NO_TOOL_CALLS: "No turn of this conversation called a tool to check against.",
    NO_SESSION: "No turn of this conversation has session values to check against.",
}


def _said_of_conversation(reason: str) -> str:
    if reason in _CONVERSATION_REASONS:
        return _CONVERSATION_REASONS[reason]
    if reason.endswith(" on this turn."):
        return reason[: -len(" on this turn.")] + " in this conversation."
    if reason.startswith("This turn has no value at "):
        return "No turn of this conversation has a value at " + reason[len("This turn has no value at "):]
    return reason

# A judge score at or above this meets the expectation, as for llm_judge's default.
JUDGE_PASS_SCORE = 0.5
# BaseTool records a refused call with this reason; it never ran.
REFUSED_CALL_PREFIX = "required parameters are missing or empty"
# Retrieval layers answer an empty search with these, which count as no result.
_EMPTY_RESULT_PREFIXES = ("no results found", "no relevant information found")
# Enough of the opening message to notice a turn that changed under a check.
FINGERPRINT_CHARS = 120
# The most of a value from the run the AI grader reads, as for its other sources.
MATERIAL_CHARS = 16000


class ToolRef(BaseModel):
    """One more tool a check is about, by id and name; as another tool that should be called, with its own values and result."""

    model_config = ConfigDict(extra="ignore")

    tool: Optional[str] = None
    tool_name: Optional[str] = None
    args: Dict[str, Any] = Field(default_factory=dict)
    result_not_empty: bool = False
    result_contains: Optional[str] = None

    @property
    def conditioned(self) -> bool:
        return bool(self.args) or self.result_not_empty or _filled(self.result_contains)


class Check(BaseModel):
    """One expectation about what should or should not happen."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(min_length=1, max_length=128)
    expect: Literal["should", "should_not"] = "should"
    kind: Literal[
        "reply_mentions",
        "reply_meets",
        "reply_matches",
        "reply_grounded",
        "tool_called",
        "only_tools",
        "step_runs",
        "route_taken",
        "state_equals",
        "value_equals",
        "step_fails",
    ]
    level: Literal["every_conversation", "conversation", "turn"] = "every_conversation"
    # Every conversation or the chosen ones: hold on every turn, or at some point.
    when: Literal["every_turn", "anywhere"] = "anywhere"

    # The conversation level's chosen conversations; one was stored as conversation_id before.
    conversation_ids: List[str] = Field(default_factory=list)
    conversation_id: Optional[str] = None
    case_id: Optional[str] = None
    turn_index: Optional[int] = None
    turn_message: Optional[str] = None

    text: Optional[str] = None
    # A rule in plain words; for other AI-graded checks, an extra instruction to the grader.
    rubric: Optional[str] = None
    # What the AI grader reads besides the reply; for reply_grounded, what the reply sticks to.
    context: Optional[Literal["expected_reply", "knowledge_base", "tool_calls", "session", "run_value"]] = None
    context_path: Optional[str] = None
    # An AI-graded check passes at this score (0.5 when not set), graded by this model when set.
    pass_score: Optional[float] = Field(default=None, ge=0, le=1)
    llm_provider_id: Optional[str] = None
    # reply_grounded: the NLI model or text similarity in place of the AI grader, with their settings.
    grader: Optional[Literal["nli", "similarity"]] = None
    nli_model: Optional[str] = None
    fail_on_contradiction: bool = False
    embedding: Dict[str, Any] = Field(default_factory=dict)
    # The reply against a text or the expected reply: how closely.
    match: Optional[Literal["exact", "contains", "meaning"]] = None
    tool: Optional[str] = None
    tool_name: Optional[str] = None
    # tool_called: more tools, any of which counts, each with its own values and result;
    # only_tools: the tools that may be used, or with Should not, may not.
    tools: List[ToolRef] = Field(default_factory=list)
    agent: Optional[str] = None
    agent_name: Optional[str] = None
    # The check's own tool: the values it is called with, and what it returns.
    args: Dict[str, Any] = Field(default_factory=dict)
    result_not_empty: bool = False
    result_contains: Optional[str] = None
    # Over every tool of the check: a call counts only when it succeeded.
    succeeds: bool = False
    min_calls: Optional[int] = Field(default=None, ge=0)
    max_calls: Optional[int] = Field(default=None, ge=0)
    step: Optional[str] = None
    step_name: Optional[str] = None
    # Any step of this node type, when no one step is picked.
    step_type: Optional[str] = None
    router: Optional[str] = None
    router_name: Optional[str] = None
    branch: Optional[str] = None
    branch_label: Optional[str] = None
    key: Optional[str] = None
    # value_equals: where in the turn the value is, as a dotted path.
    path: Optional[str] = None
    value: Any = None

    @model_validator(mode="after")
    def _check_fields(self) -> "Check":
        if self.level == "conversation":
            chosen = [*self.conversation_ids, *([self.conversation_id] if self.conversation_id else [])]
            self.conversation_ids = list(dict.fromkeys(str(key) for key in chosen if _filled(key)))
            if not self.conversation_ids:
                raise ValueError(f"check {self.id!r}: pick the conversations it is about")
        if self.level == "turn" and not (
            self.case_id or (self.conversation_id and self.turn_index is not None)
        ):
            raise ValueError(f"check {self.id!r}: pick the turn it is about")
        missing = {
            "reply_mentions": not _filled(self.text),
            "reply_meets": not _filled(self.rubric),
            "reply_matches": self.match is None,
            "reply_grounded": False,
            "tool_called": not (_filled(self.tool) or _filled(self.tool_name)),
            "only_tools": any(not (_filled(item.tool) or _filled(item.tool_name)) for item in self.tools)
            or (self.expect == "should_not" and not self.tools),
            "step_runs": not (_filled(self.step) or _filled(self.step_name) or _filled(self.step_type)),
            "route_taken": not (_filled(self.branch) or _filled(self.branch_label)),
            "state_equals": not _filled(self.key) or self.value is None,
            "value_equals": not _filled(self.path),
            "step_fails": False,
        }[self.kind]
        if missing:
            raise ValueError(f"check {self.id!r}: fill in what the {self.kind} check looks for")
        if self.kind in EVERY_TURN_KINDS:
            # Each turn is checked, so "at some point" has no meaning here.
            self.when = "every_turn"
        if self.kind == "reply_mentions" and self.match == "meaning":
            raise ValueError(f"check {self.id!r}: words can be mentioned or be the whole reply")
        self._check_tool_extras()
        self._check_grading()
        return self

    def _check_tool_extras(self) -> None:
        counted = self.min_calls is not None or self.max_calls is not None
        extras = self.succeeds or self.result_not_empty or _filled(self.result_contains) or counted
        if self.kind in ("tool_called", "only_tools") and self.expect == "should_not":
            if extras or (self.kind == "tool_called" and self.tools):
                raise ValueError(f"check {self.id!r}: these tool settings only apply to what should happen")
        if self.kind == "tool_called" and self.max_calls == 0:
            raise ValueError(f"check {self.id!r}: a tool that should be called at most 0 times can never pass")
        if self.kind == "tool_called" and any(not (_filled(item.tool) or _filled(item.tool_name)) for item in self.tools):
            raise ValueError(f"check {self.id!r}: pick each tool")
        if self.kind == "only_tools" and any(item.conditioned for item in self.tools):
            raise ValueError(f"check {self.id!r}: only a tool that should be called has values or a result")
        if self.min_calls is not None and self.max_calls is not None and self.min_calls > self.max_calls:
            raise ValueError(f"check {self.id!r}: the fewest calls cannot be more than the most")

    def _check_grading(self) -> None:
        allowed = {
            "reply_meets": CONTEXTS,
            "reply_grounded": ("expected_reply", "knowledge_base", "tool_calls", "session", "run_value"),
        }.get(self.kind, ())
        if self.context and self.context not in allowed:
            raise ValueError(f"check {self.id!r}: this check cannot read {self.context}")
        if self.context and self.kind == "reply_meets" and not self.per_turn:
            raise ValueError(f"check {self.id!r}: only a rule graded on each turn can read more than the reply")
        if self.context == "run_value" and not _filled(self.context_path):
            raise ValueError(f"check {self.id!r}: name the value the grader reads")
        if self.grader and self.kind != "reply_grounded":
            raise ValueError(f"check {self.id!r}: only a check that sticks to the facts has another grader")
        if self.grader and _filled(self.rubric):
            raise ValueError(f"check {self.id!r}: only the AI grader reads an extra instruction")
        if self.grader != "nli" and (_filled(self.nli_model) or self.fail_on_contradiction):
            raise ValueError(f"check {self.id!r}: these settings are for the NLI model")
        if self.grader != "similarity" and self.embedding:
            raise ValueError(f"check {self.id!r}: these settings are for text similarity")
        if "base_url" in self.embedding:
            raise ValueError(f"check {self.id!r}: text similarity uses the server's embedding address")
        unknown = set(self.embedding) - set(EMBEDDING_FIELDS)
        if unknown or self.embedding.get("type", "huggingface") not in EMBEDDING_TYPES:
            raise ValueError(f"check {self.id!r}: the embedding model is not one text similarity can use")
        if self.pass_score is not None and not self.scored:
            raise ValueError(f"check {self.id!r}: only a check graded by AI has a pass score")
        if self.llm_provider_id and not self.ai_graded:
            raise ValueError(f"check {self.id!r}: only a check graded by AI has an AI grader")

    @property
    def per_turn(self) -> bool:
        """Graded turn by turn rather than once over the conversation."""
        return (
            self.kind in EVERY_TURN_KINDS
            or self.level == "turn"
            or (self.level in ("every_conversation", "conversation") and self.when == "every_turn")
        )

    @property
    def ai_graded(self) -> bool:
        return (
            self.kind == "reply_meets"
            or (self.kind == "reply_grounded" and self.grader is None)
            or (self.kind == "reply_matches" and self.match == "meaning")
        )

    @property
    def scored(self) -> bool:
        """Graded with a score, by the AI grader, the NLI model or text similarity."""
        return self.ai_graded or (self.kind == "reply_grounded" and self.grader is not None)

    @property
    def passes_at(self) -> float:
        return self.pass_score if self.pass_score is not None else JUDGE_PASS_SCORE

    @property
    def material(self) -> Optional[str]:
        """What the check grades the reply against, when anything besides the reply."""
        if self.kind == "reply_matches":
            return "expected_reply"
        if self.kind == "reply_grounded":
            return self.context or "knowledge_base"
        return self.context if self.kind == "reply_meets" else None

    @property
    def tool_refs(self) -> List[ToolRef]:
        """Every tool the check is about: tool_called's own, with its values and result, and its others; or only_tools' list."""
        if self.kind != "tool_called":
            return list(self.tools)
        own = ToolRef(
            tool=self.tool,
            tool_name=self.tool_name,
            args=self.args,
            result_not_empty=self.result_not_empty,
            result_contains=self.result_contains,
        )
        return [own, *self.tools]

    @property
    def counted(self) -> bool:
        return self.min_calls is not None or self.max_calls is not None


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
    whole = check.level in ("every_conversation", "conversation")
    once = whole and check.when == "anywhere"
    if check.expect == "should_not":
        modal = "should never" if once else "should not"
    else:
        modal = "should"

    # The chosen conversations are named where the check is listed, so only every conversation says so.
    every = check.level == "every_conversation"
    prefix = ""
    if check.kind in EVERY_TURN_KINDS:
        prefix = "" if check.level == "turn" else "On every turn, "
    elif whole:
        if check.when == "every_turn":
            prefix = "On every turn, "
        elif check.expect == "should" and check.kind != "only_tools":
            prefix = "In every conversation, at some point, " if every else "At some point, "
        elif every:
            prefix = "In every conversation, "

    sentence = prefix + _clause(check, modal)
    if check.pass_score is not None and check.pass_score != JUDGE_PASS_SCORE:
        sentence += f" (passes at {check.pass_score:g})"
    return sentence[0].upper() + sentence[1:] + "."


_MATCH_VERBS = {"exact": "be exactly", "contains": "contain", "meaning": "say the same as"}
_CONTEXT_PHRASES = {
    "expected_reply": ", graded with the expected reply",
    "knowledge_base": ", graded with the knowledge-base passages",
    "tool_calls": ", graded with the tool calls",
    "session": ", graded with the session values",
}
_GROUNDS = {
    "expected_reply": "the expected reply",
    "knowledge_base": "the knowledge base",
    "tool_calls": "the tool results",
    "session": "the session values",
}


def _clause(check: Check, modal: str) -> str:
    if check.kind == "reply_mentions":
        if check.match == "exact":
            return f'the reply {modal} be exactly "{normalize_text(check.text)}"'
        return f'the reply {modal} mention "{normalize_text(check.text)}"'
    if check.kind == "reply_meets":
        subject = "the reply" if check.per_turn else "the agent"
        clause = f'{subject} {modal} do this: "{normalize_text(check.rubric)}"'
        if check.context == "run_value":
            return clause + f', graded with the value at "{normalize_text(check.context_path)}"'
        return clause + _CONTEXT_PHRASES.get(check.context or "", "")
    if check.kind == "reply_matches":
        clause = f"the reply {modal} {_MATCH_VERBS[check.match or 'meaning']} the expected reply"
        return clause + _also(check)
    if check.kind == "reply_grounded":
        source = check.context or "knowledge_base"
        grounds = _GROUNDS.get(source) or f'the value at "{normalize_text(check.context_path)}"'
        return f"the reply {modal} stick to {grounds}" + _graded_by(check) + _also(check)
    if check.kind == "step_fails":
        if modal == "should":
            return "a step should fail"
        return "no step should ever fail" if modal == "should never" else "no step should fail"
    if check.kind == "tool_called":
        refs = check.tool_refs
        if len(refs) > 1:
            # Each tool says its own values and result; the counts and success are over them all.
            named = _joined([_tool_with_conditions(ref) for ref in refs], "or")
            clause = f"one of the tools {named} {modal} be called" + _by_agent(check) + _counts(check)
            if check.counted:
                clause += " in all"
            return clause + (" and succeed" if check.succeeds else "")
        clause = f'the tool "{tool_display(check)}" {modal} be called' + _by_agent(check)
        if check.args:
            clause += f" with {_pairs(check.args)}"
        clause += _counts(check)
        if check.succeeds:
            clause += " and succeed"
        if _filled(check.result_contains):
            clause += f' and return a result that contains "{normalize_text(check.result_contains)}"'
        elif check.result_not_empty:
            clause += " and return a result"
        return clause
    if check.kind == "only_tools":
        names = [normalize_text(ref.tool_name or ref.tool) for ref in check.tools]
        if check.expect == "should_not":
            # The tools it may not use, each of them.
            if len(names) == 1:
                return f'the tool "{names[0]}" {modal} be used' + _by_agent(check)
            ever = " ever" if modal == "should never" else ""
            return f"none of the tools {_listed(names, 'and')} should{ever} be used" + _by_agent(check)
        if not names:
            return f"no tool {modal} be used" + _by_agent(check)
        subject = f'only the tool "{names[0]}"' if len(names) == 1 else f"only the tools {_listed(names, 'and')}"
        counts = _counts(check)
        called = (" successfully" if check.succeeds else "") + counts
        return f"{subject} {modal} be used" + _by_agent(check) + (f", called{called}" if counts else "")
    if check.kind == "step_runs":
        if is_step_type(check):
            return f'a step of type "{normalize_text(check.step_name or check.step_type)}" {modal} run'
        return f'the step "{step_display(check)}" {modal} run'
    if check.kind == "route_taken":
        if not (_filled(check.router) or _filled(check.router_name)):
            return f'a router {modal} take "{branch_display(check)}"'
        return f'the router "{router_display(check)}" {modal} take "{branch_display(check)}"'
    if check.kind == "value_equals":
        expected = f'"{_value_text(check.value)}"' if _filled(check.value) else "the expected reply"
        return f'the value at "{normalize_text(check.path)}" {modal} be {expected}'
    return f'the remembered value "{normalize_text(check.key)}" {modal} be "{_value_text(check.value)}"'


def _also(check: Check) -> str:
    """An extra instruction for the grader, as the sentence ends."""
    return f', also: "{normalize_text(check.rubric)}"' if _filled(check.rubric) else ""


def _graded_by(check: Check) -> str:
    if check.grader == "nli":
        return ", graded by the NLI model" + (", failing any contradiction" if check.fail_on_contradiction else "")
    if check.grader == "similarity":
        return ", graded by text similarity"
    return ""


def _by_agent(check: Check) -> str:
    if _filled(check.agent_name) or _filled(check.agent):
        return f' by "{normalize_text(check.agent_name or check.agent)}"'
    return ""


def _times(count: int) -> str:
    return "1 time" if count == 1 else f"{count} times"


def _counts(check: Check) -> str:
    low, high = check.min_calls, check.max_calls
    if low is not None and high is not None:
        return f" exactly {_times(low)}" if low == high else f" between {low} and {high} times"
    if low is not None:
        return f" at least {_times(low)}"
    if high is not None:
        return f" at most {_times(high)}"
    return ""


def _joined(items: List[str], joiner: str) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + f" {joiner} {items[-1]}"


def _listed(names: List[str], joiner: str) -> str:
    return _joined([f'"{name}"' for name in names], joiner)


def _tool_with_conditions(ref: ToolRef) -> str:
    """A tool by name, with what its own call should have, e.g. '"lookup" (with id = 7, returning a result)'."""
    parts = [f"with {_pairs(ref.args)}"] if ref.args else []
    if _filled(ref.result_contains):
        parts.append(f'returning a result that contains "{normalize_text(ref.result_contains)}"')
    elif ref.result_not_empty:
        parts.append("returning a result")
    name = f'"{normalize_text(ref.tool_name or ref.tool)}"'
    return f"{name} ({', '.join(parts)})" if parts else name


def is_step_type(check: Check) -> bool:
    """Any step of a node type, rather than one picked step."""
    return _filled(check.step_type) and not _filled(check.step)


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
    # The workflow's output as it came, so a JSON reply compares as JSON.
    output: Any = None
    # The dataset's expected reply, as text and as stored.
    expected: str = ""
    expected_value: Any = None
    # The knowledge-base passages the turn found, as the AI grader reads them.
    passages: str = ""
    # What went wrong in the turn's steps; empty when nothing did.
    step_errors: str = ""
    # The turn's tool calls and session values, as the AI grader reads them.
    tool_text: str = ""
    session_text: str = ""
    # The values at the dotted paths the checks name, read from the turn.
    values: Dict[str, Any] = field(default_factory=dict)
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
                "result": event.get("result"),
                "refused": error.lower().startswith(REFUSED_CALL_PREFIX),
            }
        )
    return calls


def check_paths(checks: Iterable[Check]) -> List[str]:
    """The dotted paths the checks read from each turn."""
    paths = {check.path for check in checks if check.kind == "value_equals"}
    paths |= {check.context_path for check in checks if check.context == "run_value"}
    return sorted(normalize_text(path) for path in paths if _filled(path))


def read_path(data: Any, path: str) -> Any:
    """The value at a dotted path, or None when any part is missing."""
    current = data
    for part in normalize_text(path).split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            return None
    return current


# ---- names in the workflow that ran ---------------------------------------------------


@dataclass
class Targets:
    """A check's tools, agent, steps or routers, resolved to ids in the workflow that ran."""

    tool_ids: List[str] = field(default_factory=list)
    # Each of the check's tools in order: its ids in the workflow that ran; none means it is matched by name.
    tool_ids_by_ref: List[List[str]] = field(default_factory=list)
    agent_id: Optional[str] = None
    # The step or router; a name on several nodes means any of them, as Action Taken matched it.
    node_ids: List[str] = field(default_factory=list)
    # Without the workflow that ran, a step or router named as it was typed.
    node_names: List[str] = field(default_factory=list)
    # Any step of this node type, when the check is not about one step.
    node_type: Optional[str] = None
    # The tool's name in the workflow that ran, for what a check saw.
    name: Optional[str] = None
    # Why the check cannot be graded at all, as with an agent the workflow lacks.
    problem: Optional[str] = None
    # What the workflow that ran lacks, so it could not happen: a Should fails and a Should not holds.
    missing: Optional[str] = None
    # The tools the workflow that ran lacks, by name.
    missing_tools: List[str] = field(default_factory=list)
    # Whether the router's branches in the workflow that ran have the check's branch, when known.
    branch_known: Optional[bool] = None
    # Every agent in the workflow that ran, when it is known.
    agent_ids: Optional[List[str]] = None


def resolve_targets(check: Check, catalog: Optional[Dict[str, List[Dict[str, Any]]]]) -> Targets:
    """Match ids first, then names, so a check survives a copied or re-saved workflow."""
    if check.kind not in ("tool_called", "only_tools", "step_runs", "route_taken") or catalog is None:
        return Targets(
            tool_ids=[ref.tool for ref in check.tool_refs if ref.tool],
            tool_ids_by_ref=[[ref.tool] if ref.tool else [] for ref in check.tool_refs],
            agent_id=check.agent,
            node_names=[name for name in (check.step, check.router, check.step_name, check.router_name) if _filled(name)],
            node_type=check.step_type if is_step_type(check) else None,
        )

    if check.kind in ("tool_called", "only_tools"):
        return _tool_targets(check, catalog)

    if check.kind == "step_runs":
        if is_step_type(check):
            if not any(node.get("type") == check.step_type for node in catalog.get("action_nodes") or []):
                label = normalize_text(check.step_name or check.step_type)
                return Targets(node_type=check.step_type, missing=f'No step of type "{label}" is in the workflow that ran, so none ran.')
            return Targets(node_type=check.step_type)
        ids = _matching_ids(catalog.get("action_nodes") or [], check.step, check.step_name, ("id", "label"))
        if not ids:
            return Targets(missing=f'The step "{step_display(check)}" is not in the workflow that ran, so it did not run.')
        return Targets(node_ids=ids)

    routers = catalog.get("routers") or []
    # No router named means any router.
    if not (_filled(check.router) or _filled(check.router_name)):
        return Targets(branch_known=_has_branch(check, routers))
    ids = _matching_ids(routers, check.router, check.router_name, ("id", "label"))
    if not ids:
        return Targets(missing=f'The router "{router_display(check)}" is not in the workflow that ran, so it did not run.')
    return Targets(node_ids=ids, branch_known=_has_branch(check, [r for r in routers if r.get("id") in ids]))


def _has_branch(check: Check, routers: List[Dict[str, Any]]) -> bool:
    """Whether these routers have the check's branch by its value, which then decides alone."""
    return _filled(check.branch) and any(
        names_equal(branch.get("value"), check.branch) for router in routers for branch in router.get("branches") or []
    )


def _tool_targets(check: Check, catalog: Dict[str, List[Dict[str, Any]]]) -> Targets:
    agents = catalog.get("agents") or []
    agent_id = None
    agent = normalize_text(check.agent_name or check.agent)
    if agent:
        ids = _matching_ids(agents, check.agent, check.agent_name, ("id", "label"))
        if len(ids) != 1:
            # As Tool Usage did when its agent did not run: there is nothing to judge.
            where = "matches more than one agent" if ids else "is not"
            return Targets(problem=f'The agent "{agent}" {where} in the workflow that ran.')
        agent_id = ids[0]
    fields = ("id", "name", "label")
    tools = [tool for entry in agents if agent_id in (None, entry.get("id")) for tool in entry.get("tools") or []]
    tool_ids: List[str] = []
    by_ref: List[List[str]] = []
    missing: List[str] = []
    name = None
    for ref in check.tool_refs:
        # A name on several tool nodes means any of them: a call to either counts.
        ids = _matching_ids(tools, ref.tool, ref.tool_name, fields)
        by_ref.append(ids)
        if not ids:
            # No call can be to a tool the workflow lacks, as for Tool Usage.
            missing.append(normalize_text(ref.tool_name or ref.tool))
            continue
        tool_ids.extend(item for item in ids if item not in tool_ids)
        if name is None:
            name = next((tool.get("name") for tool in tools if tool.get("id") in ids), None)
    return Targets(tool_ids=tool_ids, tool_ids_by_ref=by_ref, agent_id=agent_id, name=name, missing_tools=missing,
                   agent_ids=[entry.get("id") for entry in agents if entry.get("id")])


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
        if check.match == "exact":
            same = turn.reply == text
            return same, f'The reply {"was" if same else "was not"} exactly "{text}".'
        mentioned = text.casefold() in turn.reply.casefold()
        return mentioned, f'The reply {"mentioned" if mentioned else "did not mention"} "{text}".'

    if check.kind == "reply_matches":
        if turn.crashed or turn.waiting_for_human:
            return None, "There was no reply to read."
        if not turn.expected:
            return None, NO_EXPECTED_REPLY
        if check.match == "contains":
            found = contains_expected(turn)
            return found, f'The reply {"contained" if found else "did not contain"} the expected reply.'
        same = matches_exactly(turn)
        return same, f'The reply {"was" if same else "was not"} exactly the expected reply.'

    if check.kind == "step_fails":
        if turn.crashed:
            return True, f"The turn did not finish: {turn.error or 'it failed'}"
        if turn.step_errors:
            return True, turn.step_errors
        return False, "No step failed."

    if check.kind == "tool_called":
        return tool_fact(check, targets, [turn])

    if check.kind == "only_tools":
        grade = only_tools_fact if check.expect == "should" else listed_tools_fact
        return grade(check, targets, [turn])

    if check.kind == "step_runs":
        if targets.missing:
            return False, targets.missing
        if targets.node_type:
            steps = [step for step in turn.steps if step.get("type") == targets.node_type]
        else:
            steps = [step for step in turn.steps if _is_node(step, targets, latest=check.expect == "should")]
        if any(step.get("status") == "success" and not step.get("error") for step in steps):
            return True, "The step ran."
        if steps:
            return False, "The step started but did not finish."
        return False, "The step did not run."

    if check.kind == "route_taken":
        if targets.missing:
            return False, targets.missing
        named = bool(targets.node_ids or targets.node_names)
        routes = [
            route for route in turn.routes if not named or _is_node(route, targets, latest=check.expect == "should")
        ]
        if not routes:
            return False, "The router did not run." if named else "No router ran."
        for route in routes:
            if _took_branch(route, check, targets):
                return True, f'The router took "{branch_display(check)}".'
        taken = ", ".join(normalize_text(route.get("route_label") or route.get("route")) or "none" for route in routes)
        return False, f'The router took "{taken}".'

    if check.kind == "value_equals":
        return _value_fact(check, turn)

    # state_equals
    key = normalize_text(check.key)
    if key not in turn.state:
        return False, f"{key} was not set."
    actual = turn.state.get(key)
    return same_value(actual, check.value), f'{key} was "{_value_text(actual)}".'


def _value_fact(check: Check, turn: TurnRecord) -> Tuple[Optional[bool], str]:
    """The value at the check's path against its value, or the expected reply; compared as Field Equals did."""
    path = normalize_text(check.path)
    output = any(path == root or path.startswith(f"{root}.") for root in ("outputs", "trace.output"))
    if turn.waiting_for_human and output:
        return None, "The turn was waiting for a person, so there was no output to read."
    found = turn.values.get(path)
    actual = _plain(found)
    if not _filled(check.value):
        # Against the expected reply, read as Field Equals read both.
        expected = normalize_text(turn.expected_value)
        if not expected:
            return None, NO_EXPECTED_REPLY
        if not actual:
            return False, f'There was no value at "{path}".'
        same = normalize_text(found) == expected or (
            isinstance(found, (dict, list)) and json_equal(found, turn.expected_value)
        )
        return same, f'The value at "{path}" was "{actual}".'
    expected = _plain(check.value)
    if not actual:
        return False, f'There was no value at "{path}".'
    # JSON typed into the check compares as JSON with an object or list in the turn.
    typed = _json_value(check.value)
    if typed is not None and isinstance(found, (dict, list)):
        same = json_equal(found, typed)
    else:
        same = actual == expected or (actual.lower() in ("true", "false") and actual.lower() == expected.lower())
    return same, f'The value at "{path}" was "{actual}".'


def _plain(value: Any) -> str:
    """A value as text: a wrapped string unwrapped, as Field Equals read it; JSON for other objects and lists."""
    if isinstance(value, dict) and list(value) in (["value"], ["text"]) and isinstance(next(iter(value.values())), str):
        return normalize_text(value)
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True, default=str)
    return normalize_text(value)


def agent_ran(targets: Targets, turn: TurnRecord) -> bool:
    """The agent's step ran, or it called a tool, as an agent in a sub-workflow does."""
    return any(_same_node(step.get("id"), targets.agent_id) for step in turn.steps) or any(
        call.get("agent_id") == targets.agent_id for call in turn.tool_calls
    )


def tools_apply(targets: Targets, turn: TurnRecord) -> bool:
    """Whether a tool check applies to the turn: its agent ran, or with any agent, some agent did."""
    if targets.agent_id:
        return agent_ran(targets, turn)
    if targets.agent_ids is None or turn.tool_calls:
        return True
    return any(_same_node(step.get("id"), agent) for step in turn.steps for agent in targets.agent_ids)


def _is_node(observed: Dict[str, Any], targets: Targets, latest: bool) -> bool:
    """Whether a step or router run is the check's; a Should reads its latest run, as Action Taken did."""
    observed_id = observed.get("id")
    if targets.node_ids:
        if latest:
            return observed_id in targets.node_ids
        return any(_same_node(observed_id, node) for node in targets.node_ids)
    # Without the workflow that ran, an id or a label matches, as Action Taken's selector did.
    return any(observed_id == name or names_equal(observed.get("label"), name) for name in targets.node_names)


def _took_branch(route: Dict[str, Any], check: Check, targets: Targets) -> bool:
    """By the branch's value; by its label only when the routers have no branch of that value, as a switch resolves."""
    if _filled(check.branch) and names_equal(route.get("route"), check.branch):
        return True
    if targets.branch_known or names_equal(check.branch, "default") or not _filled(check.branch_label):
        return False
    return names_equal(route.get("route_label"), check.branch_label)


def _tool_calls(check: Check, targets: Targets, turns: List[TurnRecord], every_tool: bool = False) -> List[Dict[str, Any]]:
    """The check's agent's calls in these turns: of its tools, or of any tool."""
    return [
        call
        for turn in turns
        for call in turn.tool_calls
        if (every_tool or _is_tool(call, targets, check))
        and (targets.agent_id is None or call.get("agent_id") == targets.agent_id)
    ]


def _tools_named(check: Check, targets: Targets, calls: List[Dict[str, Any]]) -> str:
    refs = check.tool_refs
    if len(refs) > 1:
        return "none of " + _listed([normalize_text(ref.tool_name or ref.tool) for ref in refs], "or")
    return targets.name or next((call.get("tool_name") for call in calls if call.get("tool_name")), None) or tool_display(check)


def tool_fact(check: Check, targets: Targets, turns: List[TurnRecord]) -> Tuple[bool, str]:
    """Whether the check's tools were called in these turns, as Tool Usage graded a scope."""
    calls = _tool_calls(check, targets, turns)
    name = _tools_named(check, targets, calls)
    # "none of ..." reads as the subject of a miss; a hit names the tool that was called.
    called = name[len("none of "):] if name.startswith("none of ") else name
    ran = [call for call in calls if not call.get("refused")]
    if not calls and targets.agent_id and not any(agent_ran(targets, turn) for turn in turns):
        agent = normalize_text(check.agent_name or check.agent)
        return False, f'"{agent}" did not run, so {called} was not called.'
    several = len(check.tool_refs) > 1

    def own(call: Dict[str, Any]) -> ToolRef:
        """The check's tool the call is to, whose values and result it is held to."""
        return _tool_of(call, targets, check)

    def with_values(call: Dict[str, Any]) -> bool:
        args = own(call).args
        return not args or args_match(call.get("arguments"), args)

    def hit(call: Dict[str, Any]) -> str:
        return call.get("tool_name") or called

    def subject(call: Dict[str, Any]) -> str:
        # With several tools, a miss names the one it is about.
        return hit(call) if several else called

    if check.expect == "should_not":
        # A refused call never ran: it is not a call, but it is an attempt a "should not" forbids.
        if not any(with_values(call) for call in ran) and any(call.get("refused") and with_values(call) for call in calls):
            return True, f"{called} was attempted but refused for missing details."
        matched = [call for call in ran if with_values(call)]
        if matched:
            values = f" with {_pairs(check.args)}" if check.args else ""
            return True, f"{hit(matched[0])} was called{values}."
        if not ran:
            return False, f"{called} was not called."
        return False, f"{called} was called with {_seen_values(check.args, ran)}."

    if not ran:
        missed = f"None of {called} was called." if name.startswith("none of ") else f"{called} was not called."
        return False, missed + _missing_note(targets)
    used = [call for call in ran if not check.succeeds or call.get("status") == "succeeded"]
    if not used:
        return False, f"{called} was called but did not succeed."
    valued = [call for call in used if with_values(call)]
    if not valued:
        last = used[-1]
        return False, f"{subject(last)} was called with {_seen_values(own(last).args, [last])}."
    fitting = [call for call in valued if _result_fits(own(call), call)]
    if not fitting:
        last = valued[-1]
        wanted = own(last)
        if _filled(wanted.result_contains):
            return False, f'{subject(last)} did not return a result that contains "{wanted.result_contains}".'
        return False, f"{subject(last)} returned no result."
    count = len(used)
    attempts = len([call for call in calls if not check.succeeds or call.get("status") == "succeeded"])
    if not _within(check, count, attempts):
        together = " in all" if len(check.tool_refs) > 1 else ""
        over = check.max_calls is not None and attempts > check.max_calls
        return False, f"{called} {'were' if together else 'was'} called {_times(attempts if over else count)}{together}."
    args = own(fitting[0]).args
    values = f" with {_pairs(args)}" if args else ""
    if check.counted and several:
        return True, f"{called} were called {_times(count)} in all."
    counted = f" {_times(count)}" if check.counted else ""
    return True, f"{hit(fitting[0])} was called{values}{counted}."


def only_tools_fact(check: Check, targets: Targets, turns: List[TurnRecord]) -> Tuple[Optional[bool], str]:
    """Whether every tool the agent tried in these turns is one of the check's tools."""
    attempts = _tool_calls(check, targets, turns, every_tool=True)
    # As Tool Usage did, a tool from outside the list fails before anything else is asked.
    outside = [call for call in attempts if not _is_tool(call, targets, check)]
    if outside:
        names = sorted({normalize_text(call.get("tool_name") or call.get("tool_id")) for call in outside})
        return False, f"{_listed(names, 'and')} {'was' if len(names) == 1 else 'were'} used too."
    # With no agent at work, there are no tool calls to judge.
    if not any(tools_apply(targets, turn) for turn in turns):
        agent = normalize_text(check.agent_name or check.agent)
        return None, f'The agent "{agent}" did not run on this turn.' if agent else "No agent ran on this turn."
    counted = [call for call in attempts if not call.get("refused")]
    count = len([call for call in counted if not check.succeeds or call.get("status") == "succeeded"])
    most = len([call for call in attempts if not check.succeeds or call.get("status") == "succeeded"])
    if not _within(check, count, most):
        over = check.max_calls is not None and most > check.max_calls
        return False, f"The tools were called {'successfully ' if check.succeeds else ''}{_times(most if over else count)}."
    if not attempts:
        return True, "No tool was used."
    return True, "Only these tools were used."


def listed_tools_fact(check: Check, targets: Targets, turns: List[TurnRecord]) -> Tuple[bool, str]:
    """Whether the agent tried any of the check's tools in these turns, which a Should not forbids."""
    attempts = _tool_calls(check, targets, turns)
    if not attempts:
        names = [normalize_text(ref.tool_name or ref.tool) for ref in check.tools]
        if len(names) == 1:
            return False, f"{_listed(names, 'and')} was not used."
        return False, f"None of {_listed(names, 'and')} was used."
    names = sorted({normalize_text(call.get("tool_name") or call.get("tool_id")) for call in attempts})
    verb = "was" if len(names) == 1 else "were"
    # A refused call never ran, but it is an attempt, as for a tool that should not be called.
    if all(call.get("refused") for call in attempts):
        return True, f"{_listed(names, 'and')} {verb} attempted but refused for missing details."
    return True, f"{_listed(names, 'and')} {verb} used."


def _within(check: Check, count: int, attempts: Optional[int] = None) -> bool:
    """At least the fewest calls that ran; at most the most, counting refused attempts as Tool Usage did."""
    if check.min_calls is not None and count < check.min_calls:
        return False
    return check.max_calls is None or (count if attempts is None else attempts) <= check.max_calls


def _missing_note(targets: Targets) -> str:
    """What a missed tool check adds when the workflow that ran lacks a tool."""
    names = targets.missing_tools
    if not names:
        return ""
    if len(names) == 1 and not targets.tool_ids:
        return " It is not in the workflow that ran."
    return f" {_listed(names, 'and')} {'is' if len(names) == 1 else 'are'} not in the workflow that ran."


def _seen_values(args: Dict[str, Any], calls: List[Dict[str, Any]]) -> str:
    """What the last call was called with, for the values the check asks about."""
    shown = calls[-1].get("shown_arguments")
    return _pairs({key: (shown or {}).get(key) for key in args}) if isinstance(shown, dict) else "other values"


def _result_text(result: Any) -> str:
    if result is None:
        return ""
    if isinstance(result, str):
        return result.strip()
    try:
        return json.dumps(result, default=str)
    except (TypeError, ValueError):
        return str(result)


def _result_fits(wanted: ToolRef, call: Dict[str, Any]) -> bool:
    """The call's result as its tool asks: not empty, or containing its text, as Tool Usage read it."""
    result = call.get("result")
    text = _result_text(result)
    empty = not text or (isinstance(result, (list, dict)) and not result) or text.lower().startswith(_EMPTY_RESULT_PREFIXES)
    if wanted.result_not_empty and empty:
        return False
    # Spaces included, as Tool Usage looked for the text.
    return not _filled(wanted.result_contains) or wanted.result_contains in text


def _tool_of(call: Dict[str, Any], targets: Targets, check: Check) -> ToolRef:
    """Which of the check's tools a call of them is to: by its ids in the workflow that ran, else by name."""
    refs = check.tool_refs
    if len(refs) == 1:
        return refs[0]
    by_ref = (
        targets.tool_ids_by_ref
        if len(targets.tool_ids_by_ref) == len(refs)
        else [[ref.tool] if ref.tool else [] for ref in refs]
    )
    for ref, ids in zip(refs, by_ref):
        if ids and call.get("tool_id") in ids:
            return ref
    # A tool the workflow that ran lacks is called by name, as from a sub-workflow.
    for ref, ids in zip(refs, by_ref):
        if not ids and names_equal(call.get("tool_name"), ref.tool_name or ref.tool):
            return ref
    return refs[0]


def _is_tool(call: Dict[str, Any], targets: Targets, check: Check) -> bool:
    if targets.tool_ids and call.get("tool_id") in targets.tool_ids:
        return True
    # A tool the workflow that ran lacks can still be called by name, as from a sub-workflow.
    names = (
        targets.missing_tools
        if targets.tool_ids or targets.missing_tools
        else [ref.tool_name or ref.tool for ref in check.tool_refs]
    )
    return any(names_equal(call.get("tool_name"), name) for name in names if _filled(name))


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
    return all(_same_argument(actual.get(key), value) for key, value in expected.items())


def _same_argument(actual: Any, expected: Any) -> bool:
    """As Tool Usage compared a value: the same text, case included; objects, numbers and true or false as values."""
    if isinstance(actual, (dict, list)) or isinstance(expected, (dict, list)):
        return _canonical_json(actual) == _canonical_json(expected)
    if isinstance(actual, bool):
        return normalize_text(expected).lower() == str(actual).lower()
    if isinstance(actual, (int, float)):
        try:
            return float(normalize_text(expected)) == float(actual)
        except ValueError:
            return False
    return normalize_text(actual) == normalize_text(expected)


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


def matches_exactly(turn: TurnRecord) -> bool:
    """The reply is the expected reply; an expected JSON object or list matches equal JSON."""
    expected = _json_value(turn.expected_value)
    if expected is None:
        return bool(turn.reply) and turn.reply == turn.expected
    return _same_json(turn, expected)


def contains_expected(turn: TurnRecord) -> bool:
    """The expected reply is in the reply, ignoring case; expected JSON also matches equal JSON."""
    expected = _json_value(turn.expected_value)
    if expected is not None and _same_json(turn, expected):
        return True
    return turn.expected.casefold() in turn.reply.casefold()


def _same_json(turn: TurnRecord, expected: Any) -> bool:
    return any(json_equal(_json_value(candidate), expected) for candidate in (turn.output, turn.reply))


def json_equal(first: Any, second: Any) -> bool:
    """Equal as JSON values: key order and 10 against 10.0 do not matter, true against 1 does."""
    if isinstance(first, bool) or isinstance(second, bool):
        return isinstance(first, bool) and isinstance(second, bool) and first == second
    if isinstance(first, dict) and isinstance(second, dict):
        return first.keys() == second.keys() and all(json_equal(first[key], second[key]) for key in first)
    if isinstance(first, list) and isinstance(second, list):
        return len(first) == len(second) and all(json_equal(a, b) for a, b in zip(first, second))
    return first == second


def _json_value(value: Any) -> Any:
    """A JSON object or list held by the value, or None; a wrapped string is text."""
    if isinstance(value, dict) and len(value) == 1 and isinstance(value.get("value", value.get("text")), str):
        value = value.get("value", value.get("text"))
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return None
    return value if isinstance(value, (dict, list)) else None


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
    # Set by a grader that decides itself, as the NLI model does from each part of the reply.
    passed: Optional[bool] = None
    # Why the grader could not grade the reply, which leaves the check not evaluated.
    skipped: Optional[str] = None

    @property
    def met(self) -> bool:
        return self.meets(JUDGE_PASS_SCORE)

    def meets(self, pass_score: float) -> bool:
        if self.passed is not None:
            return self.passed
        return self.score is not None and self.score >= pass_score


Judge = Callable[[JudgeRequest], Awaitable[JudgeVerdict]]


def judge_expectation(check: Check, whole_conversation: bool) -> str:
    """The expectation the judge grades, with its Should / Should not built in."""
    if check.kind == "reply_matches":
        if check.expect == "should_not":
            return (
                "The reply should not say the same as the EXPECTED REPLY: it should differ from it in a fact, "
                "the answer or the next step. Different wording alone is not a difference."
                + _also_told(check)
            )
        return (
            "The reply should say the same as the EXPECTED REPLY: the same facts, answer and next step, "
            "in any wording. Extra detail is fine as long as nothing in it contradicts the expected reply."
            + _also_told(check)
        )
    if check.kind == "reply_grounded":
        title = _MATERIAL[check.material or "knowledge_base"][0]
        if check.expect == "should_not":
            return (
                f"The reply should not stick to the {title}: at least one factual claim in it should be one "
                f"the {title} does not support, or contradicts. Greetings and questions back to the user are not claims."
                + _also_told(check)
            )
        return (
            f"Every factual claim in the reply should be supported by the {title}. "
            "Greetings and questions back to the user need no support. "
            f"A claim the {title} does not support, or that contradicts it, does not meet this."
            + _also_told(check)
        )
    rubric = normalize_text(check.rubric)
    if not whole_conversation:
        verb = "should" if check.expect == "should" else "should not"
        return f"The reply {verb} do this: {rubric}"
    if check.expect == "should":
        return f"At some point in the conversation, the assistant should do this: {rubric}"
    return f"At no point in the conversation should the assistant do this: {rubric}"


def _also_told(check: Check) -> str:
    return f" Also: {normalize_text(check.rubric)}" if _filled(check.rubric) else ""


_MATERIAL = {
    "expected_reply": ("EXPECTED REPLY", "EXPECTED REPLY is the reply the dataset expects for this turn."),
    "knowledge_base": (
        "KNOWLEDGE-BASE PASSAGES",
        "KNOWLEDGE-BASE PASSAGES are what the assistant found in its knowledge base on this turn.",
    ),
    "tool_calls": ("TOOL CALLS", "TOOL CALLS are the tools the assistant called on this turn and what they returned."),
    "session": ("SESSION VALUES", "SESSION VALUES are the inputs and remembered values the turn started with."),
    "run_value": ("VALUE", "VALUE is a value from this turn of the run."),
}


def material_text(check: Check, turn: TurnRecord) -> str:
    material = check.material
    if material == "expected_reply":
        return turn.expected
    if material == "knowledge_base":
        return turn.passages
    if material == "tool_calls":
        return turn.tool_text
    if material == "session":
        return turn.session_text
    if material == "run_value":
        value = turn.values.get(normalize_text(check.context_path))
        text = value if isinstance(value, str) else (_value_text(value) if value is not None else "")
        return text[:MATERIAL_CHARS].strip()
    return ""


def grader_name(check: Check) -> str:
    """Who grades a scored check, as its results say."""
    return {"nli": "The NLI model", "similarity": "Text similarity"}.get(check.grader or "", "The AI grader")


def missing_material(check: Check, turn: TurnRecord) -> Optional[str]:
    """Why the turn lacks what the check grades the reply against, or None."""
    if not check.material or material_text(check, turn):
        return None
    if check.material == "run_value":
        return f'This turn has no value at "{normalize_text(check.context_path)}".'
    return {
        "expected_reply": NO_EXPECTED_REPLY,
        "knowledge_base": NO_PASSAGES,
        "tool_calls": NO_TOOL_CALLS,
        "session": NO_SESSION,
    }[check.material]


def judge_prompt(request: JudgeRequest) -> Tuple[str, str]:
    """The system prompt and the user content of one AI grading."""
    check = request.check
    expectation = judge_expectation(check, whole_conversation=not check.per_turn)
    if not check.per_turn:
        system = (
            "You grade a whole conversation between a user and an AI assistant against a "
            "single expectation. CONVERSATION lists every turn in order.\n\n"
            f"EXPECTATION:\n{expectation}\n\n"
        )
        user = f"CONVERSATION:\n{transcript(request.turns)}"
    else:
        turn = request.turns[0]
        title, explained = _MATERIAL.get(check.material or "", ("", ""))
        situational = (
            " An expectation that applies only in some situations is met when this reply is not one of them."
            if check.kind == "reply_meets"
            else ""
        )
        system = (
            "You grade one reply from an AI assistant against a single expectation. "
            f"QUESTION is what the user said and ANSWER is the reply to grade.{' ' + explained if title else ''}\n\n"
            f"EXPECTATION:\n{expectation}\n\n"
            # As LLM Judge framed it, so the grader does not mark down a reply for anything else.
            f"Judge only this expectation, not the reply's overall quality or helpfulness.{situational} "
        )
        material = f"{title}:\n{material_text(check, turn)}\n\n" if title else ""
        user = f"QUESTION:\n{turn.message}\n\n{material}ANSWER:\n{turn.reply}"
    if not check.per_turn:
        system += "Judge only this expectation, not the conversation's overall quality or helpfulness. "
    system += (
        "Score 1.0 when it is fully met, 0.0 when it clearly "
        "is not, and in between only for partial compliance.\n\n"
        "Return ONLY a compact JSON object in this exact format:\n"
        '{"score": 0.0-1.0, "reason": "short explanation"}\n'
        "Do not include any extra text or explanation."
    )
    return system, user


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
        if not check.scored or targets[check.id].problem:
            continue
        if check.level == "turn":
            turn, _ = target_turn(check, conversations)
            if turn is not None and _gradable(check, turn):
                requests.append(JudgeRequest(check, [turn]))
            continue
        for group in _groups_for(check, conversations):
            ran = [turn for turn in group if turn.ran]
            if check.per_turn:
                requests.extend(JudgeRequest(check, [turn]) for turn in ran if _gradable(check, turn))
            elif ran:
                requests.append(JudgeRequest(check, ran))
    return requests


def _gradable(check: Check, turn: TurnRecord) -> bool:
    return _has_reply(turn) and _ungraded_reason(check, turn) is None


def _ungraded_reason(check: Check, turn: TurnRecord) -> Optional[str]:
    """Why a turn that has a reply leaves a scored check not evaluated, or None."""
    missing = missing_material(check, turn)
    if missing:
        return missing
    # As NLI and Provenance did, an empty reply has nothing to hold to its source.
    if check.kind == "reply_grounded" and not turn.reply:
        return NO_REPLY_TEXT
    return None


async def run_judge(
    requests: List[JudgeRequest],
    judge: Judge,
    concurrency: int = 4,
    budget_seconds: Optional[float] = None,
) -> Dict[Any, JudgeVerdict]:
    """Run the judge over every request, a few at a time; a failed or late call is an error verdict."""
    limit = asyncio.Semaphore(concurrency)
    loop = asyncio.get_running_loop()
    # No budget means no deadline; a budget of 0 means no time is left to grade.
    deadline = loop.time() + budget_seconds if budget_seconds is not None else None

    async def one(request: JudgeRequest) -> Tuple[Any, JudgeVerdict]:
        name = grader_name(request.check)
        out_of_time = JudgeVerdict(error=True, reason=f"{name} ran out of time for this run.")
        async with limit:
            remaining = None if deadline is None else deadline - loop.time()
            if remaining is not None and remaining <= 0:
                return request.key, out_of_time
            try:
                return request.key, await asyncio.wait_for(judge(request), remaining)
            except Exception:  # pylint: disable=broad-except
                if deadline is not None and loop.time() >= deadline:
                    return request.key, out_of_time
                logger.warning("%s failed on check %s", name, request.check.id, exc_info=True)
                return request.key, JudgeVerdict(error=True, reason=f"{name} did not answer.")

    return dict(await asyncio.gather(*(one(request) for request in requests)))


_NO_REPLY_WAITING = "The turn was waiting for a person, so there was no reply to grade."
_NO_REPLY_FAILED = "The turn did not finish, so there was no reply to grade."


def _has_reply(turn: TurnRecord) -> bool:
    return turn.ran and not turn.crashed and not turn.waiting_for_human


def _groups_for(check: Check, conversations: List[List[TurnRecord]]) -> List[List[TurnRecord]]:
    if check.level == "every_conversation":
        return [group for group in conversations if group]
    chosen = set(check.conversation_ids)
    return [group for group in conversations if group and group[0].conversation_key in chosen]


def _gone(missing: int, chosen: int) -> str:
    """Why a check cannot be graded on chosen conversations the dataset no longer has."""
    if missing == chosen:
        if chosen == 1:
            return "The conversation this check is about is no longer in the dataset."
        return "The conversations this check is about are no longer in the dataset."
    verb = "is" if missing == 1 else "are"
    return f"{missing} of the {chosen} conversations this check is about {verb} no longer in the dataset."


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
        if check.level == "conversation":
            found = {group[0].conversation_key for group in groups}
            missing = sum(1 for key in check.conversation_ids if key not in found)
            if missing:
                # Said once for the run, beside the chosen conversations it still has.
                planned.append(_entry(check, None, _not_evaluated(
                    sentence, _gone(missing, len(check.conversation_ids)))))
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
        return _not_evaluated(sentence, turn.skip_reason or "This turn did not run.", error=turn.skip_reason == UNREADABLE_TURN)
    if check.scored:
        if turn.waiting_for_human:
            return _not_evaluated(sentence, _NO_REPLY_WAITING)
        missing = _ungraded_reason(check, turn)
        if missing:
            return _not_evaluated(sentence, missing)
        return _from_verdict(verdicts.get((check.id, (turn.case_id,))), sentence, check)
    holds, fact = turn_fact(check, targets, turn)
    if holds is None:
        return _not_evaluated(sentence, fact)
    passed = holds if check.expect == "should" else not holds
    return _result(RULE_PASSED if passed else RULE_FAILED, sentence, fact)


def _grade_conversation(
    check: Check, targets: Targets, group: List[TurnRecord], verdicts: Dict[Any, JudgeVerdict], sentence: str
) -> Dict[str, Any]:
    ran = [turn for turn in group if turn.ran]
    # A turn that ran but could not be read is one the check never saw, so it cannot pass.
    unread = next((turn for turn in group if not turn.ran and turn.skip_reason == UNREADABLE_TURN), None)
    if unread is not None and unread.crashed and check.kind == "step_fails":
        # Its crash is still known, and a crash is a failed step.
        fact = f"{unread.label} did not finish: {unread.error or 'it failed'}"
        return _result(RULE_PASSED if check.expect == "should" else RULE_FAILED, sentence, fact)
    unread_note = (
        f"{unread.label} did not finish: {unread.error or 'it failed'}"
        if unread is not None and unread.crashed
        else f"{unread.label}: {UNREADABLE_TURN}" if unread is not None else ""
    )
    if not ran:
        if unread is not None:
            return _not_evaluated(sentence, unread_note, error=True)
        return _not_evaluated(sentence, "No turn of this conversation ran.")
    result = _grade_turns(check, targets, ran, verdicts, sentence)
    # A failure stands, and so does a Should seen at some point; anything else could hide in the unread turn.
    seen_once = (
        result["status"] == RULE_PASSED
        and check.expect == "should"
        and not (check.per_turn or check.scored or check.counted or check.kind == "only_tools")
    )
    if unread is not None and result["status"] != RULE_FAILED and not seen_once:
        return _not_evaluated(sentence, unread_note, error=True)
    return result


def _grade_turns(
    check: Check,
    targets: Targets,
    ran: List[TurnRecord],
    verdicts: Dict[Any, JudgeVerdict],
    sentence: str,
) -> Dict[str, Any]:
    if check.scored and not check.per_turn:
        return _from_verdict(verdicts.get((check.id, tuple(turn.case_id for turn in ran))), sentence, check)

    # Counting calls, or only these tools, holds over every call in the conversation together.
    together = (check.kind == "only_tools" and check.expect == "should") or (
        check.kind == "tool_called" and check.counted
    )
    if not check.per_turn and together:
        grade = only_tools_fact if check.kind == "only_tools" else tool_fact
        holds, fact = grade(check, targets, ran)
        if holds is None:
            return _not_evaluated(sentence, _said_of_conversation(fact))
        return _result(RULE_PASSED if holds else RULE_FAILED, sentence, fact)

    facts: List[Tuple[TurnRecord, Optional[bool], str]] = []
    # Turns the grader could not grade, which keep the check from passing.
    unanswered: List[Tuple[TurnRecord, str]] = []
    for turn in ran:
        # On every turn, a tool check is about the turns its agent, or any agent, works on.
        if check.kind in ("tool_called", "only_tools") and check.per_turn and not tools_apply(targets, turn):
            agent = normalize_text(check.agent_name or check.agent)
            reason = f'The agent "{agent}" did not run on this turn.' if agent else "No agent ran on this turn."
            facts.append((turn, None, reason))
            continue
        if check.scored:
            verdict = verdicts.get((check.id, (turn.case_id,)))
            ungraded = _ungraded_reason(check, turn)
            if not _has_reply(turn):
                facts.append((turn, None, _NO_REPLY_WAITING if turn.waiting_for_human else _NO_REPLY_FAILED))
            elif ungraded:
                facts.append((turn, None, ungraded))
            elif verdict is None or verdict.error:
                reason = (verdict.reason if verdict else None) or "The AI grader did not answer."
                unanswered.append((turn, reason))
                facts.append((turn, None, reason))
            elif verdict.skipped:
                facts.append((turn, None, verdict.skipped))
            else:
                facts.append((turn, verdict.meets(check.passes_at), verdict.reason or ""))
        else:
            holds, fact = turn_fact(check, targets, turn)
            facts.append((turn, holds, fact))

    known = [(turn, holds, fact) for turn, holds, fact in facts if holds is not None]
    checked = _numbers(turn for turn, _, _ in known)

    def read(result: Dict[str, Any]) -> Dict[str, Any]:
        # The turns it read and what each did, so a page can say how every reply went, not only where it broke.
        if checked and result["status"] != RULE_NOT_EVALUATED:
            result["checked"] = checked
            result["checked_facts"] = [fact for _, _, fact in known]
        return result

    if check.scored:
        # The grader already graded each reply against the Should or Should not.
        misses = [(turn, fact) for turn, met, fact in known if not met]
        if misses:
            return read(_on_turns(RULE_FAILED, sentence, misses))
        if unanswered:
            turn, reason = unanswered[0]
            return _not_evaluated(sentence, f"{turn.label}: {reason}", error=True)
    if not known:
        first, _, reason = facts[0]
        # One reason for every turn is said of the conversation; mixed ones name the first turn.
        if len({fact for _, _, fact in facts}) == 1:
            return _not_evaluated(sentence, _said_of_conversation(reason))
        return _not_evaluated(sentence, f"{first.label}: {reason}")
    if check.scored:
        return read(_result(RULE_PASSED, sentence, _all_of("Met", len(known), len(facts))))

    hits = [(turn, fact) for turn, holds, fact in known if holds]
    misses = [(turn, fact) for turn, holds, fact in known if not holds]
    if check.expect == "should_not":
        if hits:
            return read(_on_turns(RULE_FAILED, sentence, hits))
        return read(_result(RULE_PASSED, sentence, _none_of(len(known), len(facts))))
    if check.per_turn:
        if misses:
            return read(_on_turns(RULE_FAILED, sentence, misses))
        return read(_result(RULE_PASSED, sentence, _all_of("Held", len(known), len(facts))))
    if hits:
        return read(_on_turns(RULE_PASSED, sentence, hits))
    turn, fact = misses[-1]
    return read(_result(RULE_FAILED, sentence, f"{_none_of(len(known), len(facts))} {turn.label}: {fact}"))


def _on_turns(status: str, sentence: str, found: List[Tuple[TurnRecord, str]]) -> Dict[str, Any]:
    """A result that names the turns it is about, with what each one did."""
    turn, fact = found[0]
    return _result(
        status,
        sentence,
        f"{turn.label}: {fact}".strip(),
        turns=_numbers(t for t, _ in found),
        facts=[fact for _, fact in found],
    )


def _all_of(verb: str, count: int, total: Optional[int] = None) -> str:
    if total is not None and count < total:
        return f"{verb} on {_counted(count)}{_unchecked(total - count)}"
    return f"{verb} on its one turn." if count == 1 else f"{verb} on all {count} turns."


def _none_of(count: int, total: Optional[int] = None) -> str:
    if total is not None and count < total:
        checked = "the one turn checked" if count == 1 else f"any of the {count} turns checked"
        return f"Not on {checked}{_unchecked(total - count)}"
    return "Not on its one turn." if count == 1 else f"Not on any of its {count} turns."


def _counted(count: int) -> str:
    return "the one turn checked" if count == 1 else f"the {count} turns checked"


def _unchecked(count: int) -> str:
    return "; the other turn could not be checked." if count == 1 else f"; the other {count} turns could not be checked."


def _numbers(turns: Iterable[TurnRecord]) -> List[int]:
    return [turn.position + 1 for turn in turns]


def _from_verdict(verdict: Optional[JudgeVerdict], sentence: str, check: Check) -> Dict[str, Any]:
    if verdict is None or verdict.error:
        return _not_evaluated(sentence, (verdict.reason if verdict else None) or "The AI grader did not answer.", error=True)
    if verdict.skipped:
        return _not_evaluated(sentence, verdict.skipped)
    met = verdict.meets(check.passes_at)
    observed = verdict.reason or ("The AI grader says it was met." if met else "The AI grader says it was not met.")
    result = _result(RULE_PASSED if met else RULE_FAILED, sentence, observed)
    result["score"] = verdict.score
    return result


def _result(
    status: str,
    sentence: str,
    observed: str,
    turns: Optional[List[int]] = None,
    facts: Optional[List[str]] = None,
) -> Dict[str, Any]:
    result = {"status": status, "passed": status == RULE_PASSED, "expected": sentence, "observed": observed}
    if turns:
        result["turns"] = turns
        # What each listed turn did, in the same order.
        if facts:
            result["facts"] = facts[:len(turns)]
    return result


def _not_evaluated(sentence: str, reason: Optional[str], error: bool = False) -> Dict[str, Any]:
    """Not graded; with error, because grading broke, which keeps its conversation from passing."""
    result = {
        "status": RULE_NOT_EVALUATED,
        "passed": False,
        "expected": sentence,
        "observed": "not evaluated",
        "comment": reason or "This check could not be graded.",
    }
    if error:
        result["error"] = True
    return result


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
    """passed, failed or not_evaluated per conversation key; a crash fails it, a half-run never passes."""
    conversation_of = {turn.case_id: turn.conversation_key for group in conversations for turn in group}
    statuses: Dict[str, List[str]] = {}
    broken: set = set()
    for entry in planned:
        key = entry.get("source_conversation_id") or conversation_of.get(entry.get("case_id"))
        if key:
            statuses.setdefault(str(key), []).append(entry["result"]["status"])
            if entry["result"].get("error"):
                broken.add(str(key))
    verdicts: Dict[str, str] = {}
    for group in conversations:
        if not group:
            continue
        key = group[0].conversation_key
        seen = statuses.get(key, [])
        if any(turn.crashed for turn in group) or RULE_FAILED in seen:
            verdicts[key] = RULE_FAILED
        # A turn that did not run, or a check that could not be graded, never passes; an unread
        # turn says so on each check it could change, so it does not stop the others.
        elif any(not turn.ran and turn.skip_reason != UNREADABLE_TURN for turn in group) or key in broken:
            verdicts[key] = RULE_NOT_EVALUATED
        elif RULE_PASSED in seen:
            verdicts[key] = RULE_PASSED
        else:
            verdicts[key] = RULE_NOT_EVALUATED
    return verdicts
