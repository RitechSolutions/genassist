"""
Plain-language narration of the Workflow Builder's tool calls for the chat.

While the builder agent works, each tool call becomes one ``step`` frame on the
streamed chat turn ("Adding 3 steps and connecting them", "Testing with “My
invoice is wrong”"), so the person watches the work happen instead of a bare
"Thinking". Nothing here changes what the tools do; it only describes them.
"""

import json
import re
import uuid
from typing import Any, Dict, Optional, Tuple

from app.core import turn_stream

# Groups a step for its icon in the chat.
KIND_READ = "read"
KIND_LOOKUP = "lookup"
KIND_SEARCH = "search"
KIND_EDIT = "edit"
KIND_TEST = "test"
KIND_FINALIZE = "finalize"
KIND_QUESTION = "question"

_TOOL_KINDS: Dict[str, str] = {
    "get_workflow": KIND_READ,
    "get_node": KIND_READ,
    "get_last_test_run": KIND_READ,
    "list_resources": KIND_READ,
    "lookup_node": KIND_LOOKUP,
    "get_pattern": KIND_LOOKUP,
    "search_web": KIND_SEARCH,
    "apply_plan": KIND_EDIT,
    "set_node_field": KIND_EDIT,
    "update_node": KIND_EDIT,
    "add_node": KIND_EDIT,
    "add_tool": KIND_EDIT,
    "connect": KIND_EDIT,
    "disconnect": KIND_EDIT,
    "remove_node": KIND_EDIT,
    "test_workflow": KIND_TEST,
    "finalize_workflow": KIND_FINALIZE,
    "ask_user": KIND_QUESTION,
}

_FIELD_LABELS = {
    "systemPrompt": "prompt",
    "code": "code",
    "pythonScript": "script",
    "template": "template",
    "description": "description",
}

_RESOURCE_LABELS = {
    "knowledge_bases": "knowledge bases",
    "integrations": "integrations",
    "data_sources": "data sources",
}

QUOTE_LIMIT = 60


def quoted(value: Any, limit: int = QUOTE_LIMIT) -> str:
    text = " ".join(str(value or "").split())
    if len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    return f"“{text}”"


def _plural(count: int, noun: str) -> str:
    return f"{count} {noun}{'' if count == 1 else 's'}"


def _join(parts: list) -> str:
    if len(parts) <= 1:
        return "".join(parts)
    return ", ".join(parts[:-1]) + " and " + parts[-1]


def describe_plan(operations: Any) -> str:
    """What an apply_plan is about to do, from its operations alone."""
    plan = operations
    if isinstance(plan, str):
        try:
            plan = json.loads(plan)
        except (ValueError, TypeError):
            plan = []
    if not isinstance(plan, list):
        plan = []
    ops = [op for op in plan if isinstance(op, dict)]
    added = [op for op in ops if op.get("op") in ("add_node", "add_tool")]
    changed = [op for op in ops if op.get("op") in ("set_node_field", "update_node")]
    removed = [op for op in ops if op.get("op") == "remove_node"]
    wired = [op for op in ops if op.get("op") in ("connect", "disconnect")]
    parts = []
    if added:
        names = [str(op.get("name") or "").strip() for op in added]
        names = [n for n in names if n]
        if 0 < len(names) <= 2 and len(names) == len(added):
            parts.append("adding " + _join([quoted(n) for n in names]))
        else:
            parts.append("adding " + _plural(len(added), "step"))
    if changed:
        parts.append("changing " + _plural(len(changed), "step"))
    if removed:
        parts.append("removing " + _plural(len(removed), "step"))
    if wired and not added:
        parts.append("connecting steps")
    elif wired:
        parts.append("connecting them")
    if not parts:
        return "Applying changes"
    text = _join(parts)
    return text[0].upper() + text[1:]


def describe_call(name: str, args: Dict[str, Any], node_name: Optional[str] = None) -> Tuple[str, str]:
    """(kind, text) for a tool call as it starts. ``node_name`` is the step a node id refers to, when known."""
    kind = _TOOL_KINDS.get(name, KIND_EDIT)
    args = args or {}
    step = quoted(node_name) if node_name else "a step"
    if name == "get_workflow":
        return kind, "Reading the workflow"
    if name == "get_node":
        return kind, f"Reading {step}"
    if name == "get_last_test_run":
        return kind, "Reading your last test run"
    if name == "list_resources":
        what = _RESOURCE_LABELS.get(str(args.get("kind") or ""), "workspace resources")
        return kind, f"Listing {what}"
    if name == "lookup_node":
        query = str(args.get("query") or args.get("node_type") or "").strip()
        return kind, f"Looking up {quoted(query)}" if query else "Looking up step types"
    if name == "get_pattern":
        pattern = str(args.get("name") or "").strip().replace("_", " ")
        return kind, f"Fetching the {pattern} pattern" if pattern else "Listing patterns"
    if name == "search_web":
        return kind, f"Searching the web for {quoted(args.get('query'))}"
    if name == "apply_plan":
        return kind, describe_plan(args.get("operations"))
    if name == "set_node_field":
        field = str(args.get("field") or "")
        label = _FIELD_LABELS.get(field, field.replace("_", " ") or "a setting")
        return kind, f"Writing the {label} of {step}"
    if name == "update_node":
        return kind, f"Updating {step}"
    if name == "add_node":
        return kind, f"Adding {quoted(args.get('name'))}" if args.get("name") else "Adding a step"
    if name == "add_tool":
        return kind, f"Adding the tool {quoted(args.get('name'))}" if args.get("name") else "Adding a tool"
    if name == "connect":
        return kind, "Connecting steps"
    if name == "disconnect":
        return kind, "Disconnecting steps"
    if name == "remove_node":
        return kind, f"Removing {step}"
    if name == "test_workflow":
        return kind, f"Testing with {quoted(args.get('message'))}"
    if name == "finalize_workflow":
        return kind, "Checking the workflow is complete"
    if name == "ask_user":
        return kind, "Preparing a question for you"
    return kind, name.replace("_", " ").capitalize()


_APPLIED = re.compile(r"Applied (\d+) of (\d+) operations")
_RESULT_LINE = re.compile(r"^\d+\. ", re.M)


def describe_outcome(name: str, result: str) -> str:
    """A few words on how a tool call went, for the end of its step."""
    text = result or ""
    if text.startswith("ERROR:"):
        return "Rejected: " + " ".join(text[6:].split())[:90]
    if name == "apply_plan":
        match = _APPLIED.search(text)
        if match:
            applied, total = int(match.group(1)), int(match.group(2))
            failed = total - applied
            return f"{applied} of {total} applied" + (f", {failed} failed" if failed else "")
        return ""
    if name == "test_workflow":
        if text.startswith("STOP"):
            return "Stopped: too many failed runs"
        from app.modules.workflow.builder.testing import test_passed, test_was_attempted

        if not test_was_attempted(text):
            return "Could not run"
        if test_passed(text):
            return "Passed, finalized" if "Workflow finalized" in text else "Passed"
        return "Failed"
    if name == "finalize_workflow":
        return "Finalized" if "Workflow finalized" in text else "Not finalized yet"
    if name == "search_web":
        if text.startswith("No results"):
            return "No results"
        count = len(_RESULT_LINE.findall(text))
        return _plural(count, "result") if count else ""
    if name == "ask_user":
        return "Waiting for your answer"
    return ""


class StepNarrator:
    """
    One step frame per tool call: ``start`` once (the first call wins, so a tool
    can refine the text once it knows the step's name), ``end`` with the outcome.
    """

    def __init__(self, name: str, args: Dict[str, Any]) -> None:
        self.name = name
        self.args = args or {}
        self.id = uuid.uuid4().hex[:10]
        self.kind, self.text = describe_call(name, self.args)
        self._started = False
        self._ended = False

    @property
    def needs_node_name(self) -> bool:
        return self.name in ("get_node", "set_node_field", "update_node", "remove_node") and bool(
            self.args.get("node_id")
        )

    def start(self, node_name: Optional[str] = None) -> None:
        if self._started:
            return
        self._started = True
        if node_name:
            self.kind, self.text = describe_call(self.name, self.args, node_name)
        turn_stream.emit_step(self.id, self.kind, self.text, "start")

    def end(self, result: str) -> None:
        if self._ended:
            return
        self.start()
        self._ended = True
        turn_stream.emit_step(self.id, self.kind, self.text, "end", describe_outcome(self.name, result))

    def fail(self) -> None:
        if self._ended:
            return
        self.start()
        self._ended = True
        turn_stream.emit_step(self.id, self.kind, self.text, "end", "Failed")
