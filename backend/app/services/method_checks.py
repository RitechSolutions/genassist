"""An evaluation's older methods read back as Should / Should not checks.

Pure: no DB or engine. Converting once leaves an evaluation that needs only checks;
whatever has no check yet is listed, so the person can see what was left out.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from app.services.evaluation_text import names_equal, normalize_text
from app.services.route_action_rules import parse_action_config, parse_route_config
from app.services.rule_scopes import ScopedRule, _rule_targets
from app.services.scenario_checks import CHECKS_TECHNIQUE, EMBEDDING_FIELDS, Check, parse_checks_config
from app.services.tool_usage_rules import parse_tool_usage_config

# Where a converted evaluation keeps the methods it had, and what could not become a check.
OLDER_METHODS_KEY = "older_methods"

METHOD_LABELS = {
    "exact_match": "Exact Match",
    "contains": "Contains",
    "not_contains": "Does Not Contain",
    "json_match": "JSON Match",
    "field_equals": "Field Equals",
    "no_errors": "No Errors",
    "nli_eval": "NLI Evaluation",
    "provenance_eval": "Provenance Evaluation",
    "llm_judge": "LLM Judge",
    "tool_used": "Tool Usage",
    "route_taken": "Route Taken",
    "action_taken": "Action Taken",
}

# The methods an evaluation saved with none of them runs, as the runner falls back to.
DEFAULT_METHODS = ("exact_match", "contains", "json_match", "field_equals", "no_errors", "nli_eval", "provenance_eval")

# Older dotted source fields, as the source presets that replaced them.
_SOURCE_FIELDS = {
    "reference_outputs": "expected_output",
    "trace.retrievals": "kb_retrievals",
    "trace.session": "conversation_context",
    "trace.tool_events": "tool_events",
    "outputs": "output",
}
# A grading source, as what a check's AI grader reads.
_CONTEXTS = {
    "expected_output": "expected_reply",
    "kb_retrievals": "knowledge_base",
    "tool_events": "tool_calls",
    "conversation_context": "session",
    "path": "run_value",
}
# Checks pass an AI grading at this score.
_PASS_SCORE = 0.5
_EVERY_TURN = {"level": "every_conversation", "when": "every_turn"}


@dataclass
class Conversion:
    """Checks made from older methods, and what could not become one."""

    checks: List[Dict[str, Any]] = field(default_factory=list)
    llm_provider_id: Optional[str] = None
    left_out: List[str] = field(default_factory=list)


def needs_conversion(techniques: Optional[Iterable[str]]) -> bool:
    """True while an evaluation runs any older method, including one saved with none."""
    techniques = list(techniques or [])
    return not techniques or any(technique != CHECKS_TECHNIQUE for technique in techniques)


def convert_methods(
    techniques: Optional[Iterable[str]],
    technique_configs: Optional[Dict[str, Any]],
    catalog: Optional[Dict[str, List[Dict[str, Any]]]] = None,
) -> Conversion:
    """The checks the evaluation's older methods amount to."""
    configs = technique_configs or {}
    techniques = list(techniques or []) or list(DEFAULT_METHODS)
    builder = _Builder(catalog)
    for technique in techniques:
        if technique == CHECKS_TECHNIQUE:
            continue
        config = configs.get(technique)
        convert = _CONVERTERS.get(technique)
        builder.method = METHOD_LABELS.get(technique, technique)
        if convert is None:
            builder.leave_out(f"{technique}, an older method with no check.")
            continue
        convert(builder, config if isinstance(config, dict) else {})
    return builder.conversion


def converted_evaluation(
    techniques: Optional[Iterable[str]],
    technique_configs: Optional[Dict[str, Any]],
    catalog: Optional[Dict[str, List[Dict[str, Any]]]] = None,
) -> Tuple[List[str], Dict[str, Any], Conversion]:
    """The evaluation's techniques and configs with only checks, its older methods kept aside."""
    techniques = list(techniques or [])
    configs = dict(technique_configs or {})
    conversion = convert_methods(techniques, configs, catalog)

    current = configs.get(CHECKS_TECHNIQUE) if isinstance(configs.get(CHECKS_TECHNIQUE), dict) else {}
    own = list(current.get("checks") or [])
    graded = [check for check in conversion.checks if _graded_by_ai(check)]
    graders = {check.get("llm_provider_id") for check in graded}
    provider = current.get("llm_provider_id")
    if provider and None in graders:
        # A method with no grader used the default model, so the evaluation's grader moves onto its own checks.
        own = [{**check, "llm_provider_id": provider} if _without_grader(check) else check for check in own]
        provider = None
    elif not provider and len(graders) == 1 and None not in graders and not any(map(_without_grader, own)):
        # One grader for every method grades the evaluation, unless its own checks use the default model.
        provider = next(iter(graders))
    converted = [
        {key: value for key, value in check.items() if not (key == "llm_provider_id" and value == provider)}
        for check in conversion.checks
    ]
    checks = _merged(own, converted)
    checks_config: Dict[str, Any] = {"checks": checks}
    if provider:
        checks_config["llm_provider_id"] = provider
    # Kept so the conversion can be read back or undone, and what was left out can be shown.
    record: Dict[str, Any] = {
        "techniques": techniques,
        "technique_configs": {key: value for key, value in configs.items() if key != CHECKS_TECHNIQUE},
        "left_out": conversion.left_out,
    }
    earlier = current.get(OLDER_METHODS_KEY)
    if isinstance(earlier, dict):
        record["earlier"] = earlier
    checks_config[OLDER_METHODS_KEY] = record
    parse_checks_config(checks_config)
    return [CHECKS_TECHNIQUE], {CHECKS_TECHNIQUE: checks_config}, conversion


def _graded_by_ai(check: Dict[str, Any]) -> bool:
    try:
        return Check.model_validate({"id": "candidate", **check}).ai_graded
    except ValueError:
        return False


def _without_grader(check: Any) -> bool:
    """An AI-graded check with no grader of its own, graded by the evaluation's grader or the default model."""
    return isinstance(check, dict) and _graded_by_ai(check) and not check.get("llm_provider_id")


def _merged(current: List[Dict[str, Any]], added: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """The evaluation's own checks first, then each converted one not already there."""
    seen = {_identity(check) for check in current if isinstance(check, dict)}
    ids = {check.get("id") for check in current if isinstance(check, dict)}
    merged = list(current)
    for check in added:
        if _identity(check) in seen:
            continue
        seen.add(_identity(check))
        base, number = check["id"], 2
        while check["id"] in ids:
            check = {**check, "id": f"{base}-{number}"}
            number += 1
        ids.add(check["id"])
        merged.append(check)
    return merged


def _identity(check: Dict[str, Any]) -> str:
    return json.dumps({key: value for key, value in check.items() if key != "id"}, sort_keys=True, default=str)


# ---- building checks ------------------------------------------------------------------


class _Builder:
    def __init__(self, catalog: Optional[Dict[str, List[Dict[str, Any]]]]) -> None:
        self.catalog = catalog
        self.conversion = Conversion()
        self.method = ""
        self._counts: Dict[str, int] = {}
        self._seen: set = set()

    def add(self, method: str, check: Dict[str, Any]) -> None:
        """Add a check, made once even when two methods ask for the same thing."""
        check = {"expect": "should", **{key: value for key, value in check.items() if not _blank(value)}}
        try:
            Check.model_validate({"id": "candidate", **check})
        except ValueError as exc:
            # One setting that cannot become a check does not stop the others; it is named with why.
            self.leave_out(f"{self.method}: {_why_not(exc, check)}")
            return
        identity = _identity(check)
        if identity in self._seen:
            return
        self._seen.add(identity)
        self._counts[method] = self._counts.get(method, 0) + 1
        self.conversion.checks.append({"id": f"check-{method.replace('_', '-')}-{self._counts[method]}", **check})

    def leave_out(self, what: str) -> None:
        if what not in self.conversion.left_out:
            self.conversion.left_out.append(what)

    def provider(self, provider_id: Any) -> Optional[str]:
        """The method's own grader, kept on its checks."""
        if not isinstance(provider_id, str) or not provider_id:
            return None
        if not self.conversion.llm_provider_id:
            self.conversion.llm_provider_id = provider_id
        return provider_id

    # Names from the workflow, so a check reads as the editor would write it.

    def tool(self, tool_id: str) -> Tuple[str, Optional[str]]:
        tools = [tool for agent in (self.catalog or {}).get("agents") or [] for tool in agent.get("tools") or []]
        found = _find(tools, tool_id, ("id", "name", "label"))
        return (found["id"], found.get("name")) if found else (tool_id, None)

    def agent(self, agent_id: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
        if not agent_id:
            return None, None
        found = _find((self.catalog or {}).get("agents") or [], agent_id, ("id", "label"))
        return (found["id"], found.get("label")) if found else (agent_id, None)


def _why_not(exc: ValueError, check: Dict[str, Any]) -> str:
    """Why a setting could not become a check, in the words the check gave."""
    reason = ""
    errors = getattr(exc, "errors", None)
    if callable(errors):
        messages = [str(error.get("msg") or "") for error in errors()]
        reason = next((message for message in messages if message), "")
    reason = re.sub(r"^(Value error, )?check 'candidate': ", "", reason).strip().rstrip(".")
    what = describe_kind(check)
    return f"{what} could not become a check ({reason})." if reason else f"{what} could not become a check."


def describe_kind(check: Dict[str, Any]) -> str:
    """A setting named by what it checked, as the left-out list reads it."""
    tool = check.get("tool_name") or check.get("tool")
    if tool:
        return f'a rule on "{tool}"'
    for key in ("step_name", "step", "step_type", "router_name", "router", "path", "text"):
        if check.get(key):
            return f'a rule on "{check[key]}"'
    return "a setting"


def _blank(value: Any) -> bool:
    # A count of 0 or turn 0 is a value; an unset flag or empty text is not.
    return value is None or value is False or value == "" or value == {}


def _find(entries: Iterable[Dict[str, Any]], ref: Any, fields: Tuple[str, ...]) -> Optional[Dict[str, Any]]:
    entries = list(entries)
    for entry in entries:
        if ref and entry.get("id") == ref:
            return entry
    for entry in entries:
        if any(names_equal(entry.get(key), ref) for key in fields if entry.get(key)):
            return entry
    return None


def _all_found(entries: Iterable[Dict[str, Any]], ref: Any, fields: Tuple[str, ...]) -> List[Dict[str, Any]]:
    """The entry with this id, else every entry the name matches."""
    entries = list(entries)
    by_id = [entry for entry in entries if ref and entry.get("id") == ref]
    return by_id or [entry for entry in entries if any(names_equal(entry.get(key), ref) for key in fields if entry.get(key))]


def _placements(rule: ScopedRule, expect: str) -> List[Dict[str, Any]]:
    """Where a scoped rule applied, as check levels: every turn, each conversation, or its turns."""
    if rule.scope == "every_turn":
        # "Never" covers every turn, so a Should not has no When, as in the editor.
        return [{"level": "every_conversation", "when": "every_turn" if expect == "should" else "anywhere"}]
    if rule.scope == "conversation":
        return [{"level": "every_conversation", "when": "anywhere"}]
    conversation = rule.target_source_conversation_id
    placements = []
    for case_id, turn_index in _rule_targets(rule):
        if case_id or (conversation and turn_index is not None):
            placements.append(
                {
                    "level": "turn",
                    "case_id": case_id,
                    "conversation_id": conversation,
                    "turn_index": turn_index,
                }
            )
    return placements


def _source(config: Dict[str, Any], source_key: str, field_key: str, default: str) -> Tuple[str, Optional[str]]:
    """A grading source and, for an older dotted field, its path."""
    value = config.get(source_key)
    if isinstance(value, str) and value:
        return value, None
    legacy = config.get(field_key)
    if isinstance(legacy, str) and legacy:
        return (_SOURCE_FIELDS[legacy], None) if legacy in _SOURCE_FIELDS else ("path", legacy)
    return default, None


def _pass_score(value: Any) -> Optional[float]:
    """An older pass score as a check's, kept within 0 to 1; the usual 0.5 needs none."""
    score = _number(value)
    if score is None or score == _PASS_SCORE:
        return None
    return min(max(score, 0.0), 1.0)


def _number(value: Any) -> Optional[float]:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _hidden_fields(builder: _Builder, config: Dict[str, Any], keys: Tuple[str, ...] = ("question_field", "answer_field")) -> None:
    # Settings the evaluation screens never offered; grading always reads the turn's message and reply.
    for key in keys:
        if _filled_text(config.get(key)):
            builder.leave_out(f'{builder.method}: grading "{normalize_text(config.get(key))}" in place of the {key.split("_")[0]}.')


def _filled_text(value: Any) -> bool:
    return bool(normalize_text(value))


def _as_typed(value: Any) -> Any:
    """A stored value as the editor shows and saves it: text, with objects and lists as JSON."""
    if value is None or isinstance(value, str):
        return value
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True)
    return str(value)


# ---- each method --------------------------------------------------------------------------


def _reply_matches(match: str) -> Callable[["_Builder", Dict[str, Any]], None]:
    def convert(builder: _Builder, _config: Dict[str, Any]) -> None:
        builder.add("reply_matches", {"kind": "reply_matches", "match": match, **_EVERY_TURN})

    return convert


def _json_match(builder: _Builder, _config: Dict[str, Any]) -> None:
    # The whole output against the whole expected output, as JSON Match compared them.
    builder.add("value_equals", {"kind": "value_equals", "path": "outputs", **_EVERY_TURN})


def _not_contains(builder: _Builder, config: Dict[str, Any]) -> None:
    # As the runner reads them: the phrases, else the older single text.
    raw = config.get("phrases")
    if raw is None:
        raw = config.get("text")
    phrases = [raw] if isinstance(raw, str) else raw if isinstance(raw, list) else []
    if not any(isinstance(phrase, str) and phrase.strip() for phrase in phrases):
        builder.leave_out("Does Not Contain had no words to look for, so it failed every turn.")
        return
    for phrase in phrases:
        if isinstance(phrase, str) and phrase.strip():
            builder.add(
                "reply_mentions",
                {
                    "kind": "reply_mentions",
                    "expect": "should_not",
                    "text": phrase.strip(),
                    "level": "every_conversation",
                    "when": "anywhere",
                },
            )


def _field_equals(builder: _Builder, config: Dict[str, Any]) -> None:
    path = normalize_text(config.get("field"))
    has_expected = "expected" in config
    expected = normalize_text(config.get("expected")) if has_expected else ""
    if has_expected and not expected:
        # An empty expected value never matched, so this setting failed every turn.
        builder.leave_out("Field Equals with no expected value.")
        return
    if not path:
        if has_expected:
            builder.add("reply_mentions", {"kind": "reply_mentions", "match": "exact", "text": expected, **_EVERY_TURN})
        else:
            builder.add("reply_matches", {"kind": "reply_matches", "match": "exact", **_EVERY_TURN})
        return
    builder.add(
        "value_equals",
        {"kind": "value_equals", "path": path, "value": _as_typed(config.get("expected")) if has_expected else None,
         **_EVERY_TURN},
    )


def _no_errors(builder: _Builder, _config: Dict[str, Any]) -> None:
    builder.add("step_fails", {"kind": "step_fails", "expect": "should_not", "level": "every_conversation", "when": "anywhere"})


def _grounding(method: str, source_key: str, field_key: str) -> Callable[["_Builder", Dict[str, Any]], None]:
    """NLI and Provenance: the reply sticks to their source, graded as they graded it."""

    def convert(builder: _Builder, config: Dict[str, Any]) -> None:
        # They read the reply in place of an answer field, never a question.
        _hidden_fields(builder, config, ("answer_field",))
        source, path = _source(config, source_key, field_key, "expected_output")
        if source == "output":
            # The reply against itself always passed, so there is nothing to check.
            return
        context = "expected_reply" if source == "expected_output" else _CONTEXTS.get(source)
        if context is None:
            builder.leave_out(f"{METHOD_LABELS[method]} against {source}.")
            return
        key = "min_entail_score" if method == "nli_eval" else "min_score"
        threshold = _number(config.get(key))
        threshold = _PASS_SCORE if threshold is None else threshold
        if not 0 <= threshold <= 1:
            builder.leave_out(f"{METHOD_LABELS[method]}: its threshold of {threshold:g} is outside 0 to 1, so it never graded.")
            return
        check: Dict[str, Any] = {
            "kind": "reply_grounded",
            "context": context,
            "context_path": path,
            "pass_score": None if threshold == _PASS_SCORE else threshold,
            **_EVERY_TURN,
        }
        if method == "nli_eval":
            check.update(
                grader="nli",
                nli_model=normalize_text(config.get("nli_model_name")) or None,
                fail_on_contradiction=bool(config.get("fail_on_contradiction")),
            )
        elif config.get("provenance_mode") == "llm" or config.get("use_llm_judge"):
            check.update(
                rubric=normalize_text(config.get("llm_judge_system_prompt_suffix")) or None,
                llm_provider_id=builder.provider(config.get("llm_provider_id")),
            )
        else:
            embedding = {
                field: normalize_text(config.get(f"embedding_{field}"))
                for field in EMBEDDING_FIELDS
                if _filled_text(config.get(f"embedding_{field}"))
            }
            check.update(grader="similarity", embedding=embedding)
            if _filled_text(config.get("embedding_api_key")):
                builder.leave_out(f"{METHOD_LABELS[method]}: its own embedding API key. Text similarity uses the server's key.")
            if _filled_text(config.get("embedding_base_url")):
                builder.leave_out(
                    f"{METHOD_LABELS[method]}: its own embedding address. Text similarity uses the server's."
                )
        builder.add("reply_grounded", check)

    return convert


def _judge_rules(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    raw_rules = config.get("rules")
    candidates = [rule for rule in raw_rules if isinstance(rule, dict)] if isinstance(raw_rules, list) else [config]
    return [rule for rule in candidates if normalize_text(rule.get("rubric") or rule.get("instructions"))]


def _llm_judge(builder: _Builder, config: Dict[str, Any]) -> None:
    grader = builder.provider(config.get("llm_provider_id"))
    _hidden_fields(builder, config)
    rules = _judge_rules(config)
    if not rules:
        builder.leave_out("LLM Judge had no rule to grade, so it failed every turn.")
        return
    for rule in rules:
        rubric = normalize_text(rule.get("rubric") or rule.get("instructions"))
        name = normalize_text(rule.get("label")) or rubric[:40]
        source, path = _source(rule, "source_type", "source_field", "none")
        context = None if source in ("none", "output") else _CONTEXTS.get(source)
        if source not in ("none", "output") and context is None:
            builder.leave_out(f'LLM Judge "{name}" against {source}.')
            continue
        score = _number(rule.get("min_score"))
        if score is not None and score > 1:
            builder.leave_out(f'LLM Judge "{name}": its pass score of {score:g} is above 1, so it could never pass.')
            continue
        builder.add(
            "reply_meets",
            {
                "kind": "reply_meets",
                "rubric": rubric,
                "context": context,
                "context_path": path,
                "pass_score": _pass_score(rule.get("min_score")),
                "llm_provider_id": grader,
                **_EVERY_TURN,
            },
        )


def _rules_of(config: Dict[str, Any], prefix: str, parse: Callable[[Dict[str, Any]], Any]) -> Tuple[List[Any], int]:
    """Each rule that reads, as the runner reads it, and how many did not; one bad rule keeps the others."""
    if not isinstance(config.get("rules"), list):
        try:
            return list(parse(config).rules), 0
        except Exception:  # pylint: disable=broad-except
            return [], 1
    rules, unreadable = [], 0
    for index, raw in enumerate(config["rules"], start=1):
        if not isinstance(raw, dict):
            continue
        try:
            rules.extend(parse({"rules": [{"id": f"{prefix}-{index}", **raw}]}).rules)
        except Exception:  # pylint: disable=broad-except
            unreadable += 1
    return rules, unreadable


def _named(names: List[str]) -> str:
    quoted = [f'"{name}"' for name in names]
    return quoted[0] if len(quoted) == 1 else ", ".join(quoted[:-1]) + f" and {quoted[-1]}"


def _tool_used(builder: _Builder, config: Dict[str, Any]) -> None:
    all_tools = sorted(
        {tool.get("id") for agent in (builder.catalog or {}).get("agents") or [] for tool in agent.get("tools") or []}
    )
    rules, unreadable = _rules_of(config, "tool", lambda raw: parse_tool_usage_config(raw, all_tool_ids=all_tools))
    if unreadable:
        builder.leave_out("Tool Usage: a rule that could not be read.")
    for rule in rules:
        raw_ids = [tool_id for tool_id in rule.tool_ids if normalize_text(tool_id)]
        tools = [builder.tool(tool_id) for tool_id in raw_ids]
        refs = [{"tool": tool, "tool_name": name} for tool, name in tools]
        names = [name or tool for tool, name in tools]
        agent, agent_name = builder.agent(rule.agent_id)
        expect = "should_not" if rule.operator == "none" else "should"
        placements = _placements(rule, "should" if rule.operator == "only" else expect)
        if not placements:
            builder.leave_out(f"Tool Usage on {_named(names) if names else 'its tools'}: the turns it was about are not known.")
            continue
        who = {"agent": agent, "agent_name": agent_name}
        # At least 0 asks nothing; for all and any, at least 1 is asked by the call itself.
        floor = 0 if rule.operator == "only" else 1
        counts = {
            "min_calls": rule.min_calls if rule.min_calls is not None and rule.min_calls > floor else None,
            "max_calls": rule.max_calls,
        }

        if rule.operator == "only":
            # Success matters only to what a count includes.
            counted = {**counts, "succeeds": rule.require_success and any(value is not None for value in counts.values())}
            for placement in placements:
                builder.add("only_tools", {"kind": "only_tools", "tools": refs, **who, **counted, **placement})
            continue

        if rule.operator == "none":
            for ref in refs:
                for placement in placements:
                    builder.add("tool_called", {"kind": "tool_called", "expect": "should_not", **ref, **who, **placement})
            continue

        conditions = [_tool_conditions(rule.per_tool.get(raw_id)) for raw_id in raw_ids]
        conditions = [{key: value for key, value in condition.items() if not _blank(value)} for condition in conditions]
        succeeds = {"succeeds": rule.require_success}
        if rule.operator == "any" and len(refs) > 1:
            # Any one of the tools, each held to its own values and result.
            first, *others = [{**ref, **condition} for ref, condition in zip(refs, conditions)]
            for placement in placements:
                builder.add(
                    "tool_called",
                    {"kind": "tool_called", **first, "tools": others, **who, **succeeds, **counts, **placement},
                )
            continue

        # Every tool, each with its own conditions; a count is over the tools together.
        together = len(refs) > 1 and any(value is not None for value in counts.values())
        for ref, condition in zip(refs, conditions):
            for placement in placements:
                builder.add(
                    "tool_called",
                    {"kind": "tool_called", **ref, **who, **condition, **succeeds,
                     **({} if together else counts), **placement},
                )
        if together:
            for placement in placements:
                builder.add(
                    "tool_called",
                    {"kind": "tool_called", **refs[0], "tools": refs[1:], **who, **succeeds, **counts, **placement},
                )


def _tool_conditions(per_tool: Any) -> Dict[str, Any]:
    """A tool's own values and result checks, as a check's."""
    if per_tool is None:
        return {}
    return {
        "args": {key: _as_typed(value) for key, value in (per_tool.expected_args or {}).items()},
        "result_not_empty": bool(per_tool.result_not_empty),
        "result_contains": normalize_text(per_tool.result_contains) or None,
    }


def _route_taken(builder: _Builder, config: Dict[str, Any]) -> None:
    rules, unreadable = _rules_of(config, "route", parse_route_config)
    if unreadable:
        builder.leave_out("Route Taken: a rule that could not be read.")
    routers = (builder.catalog or {}).get("routers") or []
    for rule in rules:
        expected = normalize_text(rule.expected)
        # No router named is any router, including routers added later; a label on several is any of them.
        named = _all_found(routers, rule.router, ("label",)) if rule.router else []
        router = named[0] if len(named) == 1 else None
        searched = named or routers
        branch = next(
            (entry for candidate in searched for entry in candidate.get("branches") or []
             if names_equal(entry.get("value"), expected) or names_equal(entry.get("label"), expected)),
            None,
        )
        placements = _placements(rule, "should")
        if not placements:
            builder.leave_out(f'Route Taken "{expected}": the turns it was about are not known.')
        for placement in placements:
            builder.add(
                "route_taken",
                {
                    "kind": "route_taken",
                    "router": router["id"] if router else rule.router,
                    "router_name": router.get("label") if router else None,
                    "branch": branch.get("value") if branch else expected,
                    "branch_label": (branch.get("label") or branch.get("value")) if branch else expected,
                    **placement,
                },
            )


def _type_label(node_type: str) -> str:
    """A node type as words: "zendeskTicketNode" reads "Zendesk ticket"."""
    words = re.sub(r"(?<!^)(?=[A-Z])", " ", re.sub(r"Node$", "", node_type)).split()
    text = " ".join(word.lower() for word in words) or node_type
    return text[0].upper() + text[1:]


def _action_taken(builder: _Builder, config: Dict[str, Any]) -> None:
    rules, unreadable = _rules_of(config, "action", parse_action_config)
    if unreadable:
        builder.leave_out("Action Taken: a rule that could not be read.")
    steps = (builder.catalog or {}).get("action_nodes") or []
    for rule in rules:
        expect = "should" if rule.should_fire else "should_not"
        if rule.node:
            found = _all_found(steps, rule.node, ("label",))
            if rule.node_type and any(step.get("type") != rule.node_type for step in found):
                # Both had to match, which this step never could.
                builder.leave_out(
                    f'Action Taken "{rule.node}": it is not a "{_type_label(rule.node_type)}" step, so this rule never held.'
                )
                continue
            # A label on several steps is any of them, as Action Taken matched it.
            one = found[0] if len(found) == 1 else None
            target = {"step": one["id"], "step_name": one.get("label")} if one else {"step": rule.node, "step_name": rule.node}
        else:
            target = {"step_type": rule.node_type, "step_name": _type_label(rule.node_type)}
        placements = _placements(rule, expect)
        if not placements:
            builder.leave_out(f'Action Taken "{rule.node or rule.node_type}": the turns it was about are not known.')
        for placement in placements:
            builder.add("step_runs", {"kind": "step_runs", "expect": expect, **target, **placement})


_CONVERTERS: Dict[str, Callable[[_Builder, Dict[str, Any]], None]] = {
    "exact_match": _reply_matches("exact"),
    "json_match": _json_match,
    "contains": _reply_matches("contains"),
    "not_contains": _not_contains,
    "field_equals": _field_equals,
    "no_errors": _no_errors,
    "nli_eval": _grounding("nli_eval", "evidence_source", "evidence_field"),
    "provenance_eval": _grounding("provenance_eval", "context_source", "context_field"),
    "llm_judge": _llm_judge,
    "tool_used": _tool_used,
    "route_taken": _route_taken,
    "action_taken": _action_taken,
}
