"""
Loop node implementation using the BaseNode class.

Runs a *body* of nodes repeatedly. The engine itself never revisits a node, so
the Loop owns the iteration: for every pass it publishes an iteration context as
its output, asks the engine to run the body sub-graph, and reads the result from
the node wired back into its ``input_loop`` handle (see engine/loops.py). Only
the body reads that context: to every other node the Loop has no output until
it has finished (``BaseNode.is_source_ready``).

Two modes:

* ``forEach``: one pass per item of a list (or per batch of ``batchSize``
  items). The first body node reads ``{{source.item}}``.
* ``repeatUntil``: pass after pass until the stop condition holds or
  ``maxIterations`` is reached (critique-and-retry). The body reads the previous
  attempt from ``{{source.previous}}``.

The stop condition is resolved after every pass, so it can read what the body
just produced: ``{{node_outputs.<loop id>.result...}}`` is the pass's result, and
any body node can be read by id. As in every node,
``{{source...}}`` is the Loop's own upstream input.

Iterations run one at a time. Body outputs are cleared before each pass so a
node never sees a value left over from the pass before.
"""

import asyncio
import json
import logging
import math
import re
import sys
import time
from typing import Any, Dict, List, Optional, Sequence, Set

from ..base_node import BaseNode
from ..conditions import evaluate, parse_bool, to_text
from ..loops import (
    LOOP_BODY_HANDLE,
    LOOP_DONE_HANDLE,
    LOOP_NODE_TYPE,
    back_edge_sources,
    handle_targets,
    loop_body,
)
from ..node_result import node_failure
from ..utils import replace_config_vars

logger = logging.getLogger(__name__)

MODE_FOR_EACH = "forEach"
MODE_REPEAT_UNTIL = "repeatUntil"
MODES = (MODE_FOR_EACH, MODE_REPEAT_UNTIL)

ON_ERROR_STOP = "stop"
ON_ERROR_CONTINUE = "continue"

# What the Done output carries in ``results``: every pass, only the last one, or nothing.
COLLECT_ALL = "all"
COLLECT_LAST = "last"
COLLECT_NONE = "none"
COLLECT_MODES = (COLLECT_ALL, COLLECT_LAST, COLLECT_NONE)

# Longest wait between two passes, whatever the node asks for or backoff reaches.
MAX_DELAY_SECONDS = 60

DEFAULT_MAX_ITERATIONS = {MODE_FOR_EACH: 100, MODE_REPEAT_UNTIL: 5}
DEFAULT_STOP_OPERATOR = "equal"

# Earlier runs of a body node are archived in the run trace; keep only the most
# recent ones so a long loop does not bloat the response.
ARCHIVED_RUNS_KEPT_PER_NODE = 20

_STOP_FIELDS = ("stopField", "stopOperator", "stopValue", "stopCaseSensitive")


class LoopNode(BaseNode):
    """Loop node: repeats its body per item, or until a condition holds."""

    def _unresolved_config_fields(self) -> set[str]:
        # The stop condition reads the body's outputs, so it is resolved after
        # every pass rather than once before the loop starts.
        return set(_STOP_FIELDS)

    def get_source_nodes(self) -> List[str]:
        """Upstream nodes only. The body's back-edge is not a prerequisite: it
        has no output until the loop has run, so waiting on it would never start."""
        returning = set(back_edge_sources(self.node_id, self.state.target_edges))
        return [source for source in super().get_source_nodes() if source not in returning]

    def get_bypass_next_nodes(self) -> Optional[List[str]]:
        """A deactivated Loop skips its body and continues from Done."""
        return handle_targets(self.node_id, LOOP_DONE_HANDLE, self.state.source_edges)

    def set_node_output(self, output: Any) -> None:
        """Store the result without the engine's routing key."""
        if isinstance(output, dict) and "next_nodes" in output:
            output = {key: value for key, value in output.items() if key != "next_nodes"}
        super().set_node_output(output)

    async def process(self, config: Dict[str, Any]) -> Any:
        """
        Run the body once per item or batch (``forEach``) or until the stop
        condition holds (``repeatUntil``), then route to the Done branch.

        Returns:
            ``{results, last, count, iterations, total, total_items, skipped,
            failed, errors, stopped_reason, next_nodes}``. ``results`` holds the
            result of each pass in order, leaving out passes that produced
            nothing (e.g. stopped by a Filter) and passes in which a node failed.
        """
        mode = str(config.get("mode") or MODE_FOR_EACH)
        if mode not in MODES:
            return node_failure(f"Unknown loop mode: {mode}")

        from app.core.config.settings import settings

        limit = self._max_iterations(config.get("maxIterations"), mode, settings.WORKFLOW_LOOP_MAX_ITERATIONS)
        upstream = self.get_input_from_source()

        batch_size = 1
        items: Optional[Sequence[Any]] = None
        total_items = 0
        total = limit
        if mode == MODE_FOR_EACH:
            try:
                items = self._parse_items(config.get("items"))
            except ValueError as e:
                return node_failure(str(e))
            total_items = len(items)
            batch_size = max(int(self._number(config.get("batchSize"), 1)), 1)
            if isinstance(items, range):
                # A count comes from upstream data and can be any size; it is never
                # turned into a list, and neither is a batch larger than the server cap.
                batch_size = min(batch_size, max(settings.WORKFLOW_LOOP_MAX_ITERATIONS, 1))
            # Batches are sliced one pass at a time, so only the passes that run cost memory.
            total = -(-total_items // batch_size)

        planned = min(total, limit)
        on_error = str(config.get("onError") or ON_ERROR_STOP)
        collect = str(config.get("collect") or COLLECT_ALL)
        delay = min(max(self._number(config.get("delaySeconds"), 0), 0), MAX_DELAY_SECONDS)
        delay_backoff = parse_bool(config.get("delayBackoff", False))
        time_limit = max(self._number(config.get("timeLimitSeconds"), 0), 0)

        state = self.get_state()
        done_targets = handle_targets(self.node_id, LOOP_DONE_HANDLE, state.source_edges)
        body_entry = handle_targets(self.node_id, LOOP_BODY_HANDLE, state.source_edges)
        body = loop_body(self.node_id, state.source_edges)
        returning = back_edge_sources(self.node_id, state.target_edges)
        nested_loops = self._nested_loops(body)
        # A nested loop answers for its own body: what it does about a failure
        # there is its ``onError``, not this loop's.
        own_body = body.difference(*(loop_body(loop_id, state.source_edges) for loop_id in nested_loops))

        results: List[Any] = []
        errors: List[Dict[str, Any]] = []
        previous: Any = None
        iterations = 0
        produced = 0
        skipped = 0
        failed = 0
        stopped_reason = "completed"
        started_at = time.monotonic()

        if not body_entry or self.engine is None:
            # Nothing to repeat (or the node is being run outside a workflow).
            stopped_reason = "no_body"
            planned = 0

        state.active_loops.append(self.node_id)
        try:
            for index in range(planned):
                if state.loop_iterations_total >= settings.WORKFLOW_LOOP_MAX_TOTAL_ITERATIONS:
                    logger.warning("LoopNode %s stopped: the run's loop iteration budget is used up", self.node_id)
                    stopped_reason = "budget"
                    break

                # Wait between passes (never before the first), unless the wait
                # itself would run past the time limit.
                wait = 0.0
                if index > 0 and delay > 0:
                    wait = min(delay * (2 ** (index - 1)) if delay_backoff else delay, MAX_DELAY_SECONDS)
                if time_limit and time.monotonic() - started_at + wait >= time_limit:
                    stopped_reason = "timeout"
                    break
                if wait:
                    await asyncio.sleep(wait)

                state.loop_iterations_total += 1
                iterations += 1

                # A body node must never read (or be considered ready because of)
                # an output left over from the previous iteration.
                for body_node_id in body:
                    state.node_outputs.pop(body_node_id, None)

                batch = None if items is None else list(items[index * batch_size : (index + 1) * batch_size])
                context = {
                    # One item per pass, or the whole batch when batchSize > 1.
                    "item": None if batch is None else (batch[0] if batch_size == 1 else batch),
                    "index": index,
                    "iteration": index + 1,
                    "total": total,
                    "is_first": index == 0,
                    "is_last": index == planned - 1,
                    "previous": previous,
                    "input": upstream,
                }
                self.set_node_output(context)

                started_ms = int(time.time() * 1000)
                path_mark = len(state.execution_path)
                await self.engine.run_subgraph(body_entry, state, blocked=set(state.active_loops))

                result = self._iteration_result(returning, body, path_mark)
                failures = self._iteration_failures(own_body, nested_loops, started_ms, index)
                errors.extend(failures)
                for body_node_id in body:
                    state.trim_archived_node_runs(body_node_id, ARCHIVED_RUNS_KEPT_PER_NODE)

                # Publish what this pass produced, so the stop condition (and a
                # later pass) can read it without naming a body node.
                self.set_node_output({**context, "result": result})

                if failures:
                    # Whatever a failing pass left behind is not a result.
                    failed += 1
                elif result is None:
                    skipped += 1
                else:
                    produced += 1
                    previous = result
                    if collect == COLLECT_ALL:
                        results.append(result)

                if failures and on_error != ON_ERROR_CONTINUE:
                    stopped_reason = "error"
                    break
                if self._stop_condition_holds(upstream):
                    stopped_reason = "condition"
                    break
            else:
                hit_limit = planned < total or (mode == MODE_REPEAT_UNTIL and self._has_stop_condition())
                if stopped_reason == "completed" and hit_limit:
                    # forEach: more items than allowed. repeatUntil: the condition never held.
                    stopped_reason = "max_iterations"
        finally:
            state.active_loops.remove(self.node_id)
            # The pass context was this node's output only for the body to read.
            # It must not outlive the loop: if a pass raised, nothing replaces it.
            state.node_outputs.pop(self.node_id, None)

        logger.info("LoopNode %s finished: %s iteration(s), %s", self.node_id, iterations, stopped_reason)

        if collect == COLLECT_LAST and previous is not None:
            results = [previous]

        return {
            "results": results,
            "last": None if collect == COLLECT_NONE else previous,
            "count": produced,
            "iterations": iterations,
            "total": total,
            "total_items": total_items,
            "skipped": skipped,
            "failed": failed,
            "errors": errors,
            "stopped_reason": stopped_reason,
            "next_nodes": done_targets,
        }

    # ---- configuration -----------------------------------------------------

    @staticmethod
    def _max_iterations(raw: Any, mode: str, hard_cap: int) -> int:
        """The configured limit, defaulted per mode and clamped to the server cap."""
        try:
            limit = int(float(raw))
        except (TypeError, ValueError):
            limit = 0
        if limit <= 0:
            limit = DEFAULT_MAX_ITERATIONS[mode]
        return min(limit, hard_cap)

    @staticmethod
    def _number(raw: Any, default: float) -> float:
        """A numeric setting, tolerating text from the UI; ``default`` when unset or invalid."""
        if isinstance(raw, bool) or raw is None or raw == "":
            return default
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return default
        return value if value == value and value not in (float("inf"), float("-inf")) else default

    @staticmethod
    def _parse_items(raw: Any) -> Sequence[Any]:
        """The list to iterate.

        A variable in a text field resolves to JSON text, so a JSON array is the
        usual form. Also accepted: an object (iterates as ``{key, value}``
        entries), a whole number N (iterates 0..N-1, returned as a ``range`` so
        a huge N costs nothing), and plain text (one item per line, or per comma
        when it is a single line). Nothing at all is an empty list.
        """
        value = raw
        if isinstance(value, str):
            text = value.strip()
            if text in ("", "null"):
                return []
            try:
                value = json.loads(text)
            except ValueError:
                value = text
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            return [{"key": key, "value": item} for key, item in value.items()]
        if isinstance(value, str):
            parts = value.splitlines() if "\n" in value.strip() else value.split(",")
            return [part.strip() for part in parts if part.strip()]
        if isinstance(value, bool):
            raise ValueError("Items must be a list, but the value is true/false")
        if isinstance(value, (int, float)):
            if not math.isfinite(value) or value < 0 or value != int(value):
                raise ValueError(f"Items must be a list or a whole number of repetitions, but the value is {value}")
            return range(min(int(value), sys.maxsize))
        raise ValueError(f"Items must be a list, but the value is a {type(value).__name__}")

    # ---- per-iteration bookkeeping -----------------------------------------

    def _iteration_result(self, returning: List[str], body: set, path_mark: int) -> Any:
        """What the body produced this pass: the output of the node(s) wired back
        into the loop, or of the last body node that ran when nothing is wired back."""
        state = self.get_state()
        if len(returning) == 1:
            return state.get_node_output(returning[0])
        if returning:
            outputs = {node_id: state.get_node_output(node_id) for node_id in returning}
            outputs = {node_id: output for node_id, output in outputs.items() if output is not None}
            return outputs or None
        for node_id in reversed(state.execution_path[path_mark:]):
            if node_id in body:
                return state.get_node_output(node_id)
        return None

    def _nested_loops(self, body: Set[str]) -> List[str]:
        """Active Loop nodes inside this loop's body (a deactivated one runs nothing)."""
        if self.engine is None:
            return []
        nodes = {node.get("id"): node for node in self.engine.workflow["nodes"]}
        return [
            node_id
            for node_id in sorted(body)
            if (nodes.get(node_id) or {}).get("type") == LOOP_NODE_TYPE
            and not ((nodes.get(node_id) or {}).get("data") or {}).get("deactivated")
        ]

    def _iteration_failures(
        self, own_body: Set[str], nested_loops: List[str], started_ms: int, index: int
    ) -> List[Dict[str, Any]]:
        """What failed during this pass: this loop's own body nodes, and the
        failure that stopped a nested loop. A failure a nested loop carried on
        past (``onError: continue``) stays in that loop's ``errors`` only."""
        state = self.get_state()
        failures = []
        for node_id in own_body:
            status = state.node_execution_status.get(node_id)
            if not status or status.get("status") != "failed":
                continue
            if (status.get("startTime") or 0) < started_ms:
                continue  # left over from an earlier pass
            failures.append(
                {
                    "index": index,
                    "node_id": node_id,
                    "node_name": status.get("name") or node_id,
                    "error": status.get("error"),
                }
            )
        for loop_id in nested_loops:
            # Body outputs are cleared before each pass, so this is this pass's run.
            output = state.get_node_output(loop_id)
            if not isinstance(output, dict) or output.get("stopped_reason") != "error":
                continue
            cause = (output.get("errors") or [{}])[-1]
            failures.append(
                {
                    "index": index,
                    "node_id": cause.get("node_id") or loop_id,
                    "node_name": cause.get("node_name") or loop_id,
                    "error": cause.get("error"),
                }
            )
        return failures

    def _has_stop_condition(self) -> bool:
        return bool(to_text(self.node_data.get("stopField")).strip())

    def _stop_condition_holds(self, upstream: Any) -> bool:
        """Evaluate the stop condition against the state left by the pass that just ran.

        A broken condition never stops the loop; ``maxIterations`` bounds it instead.
        """
        if not self._has_stop_condition():
            return False

        raw = {key: self.node_data.get(key) for key in ("stopField", "stopValue")}
        resolved, _ = replace_config_vars(config=raw, state=self.get_state(), source_output=upstream)
        operator = str(self.node_data.get("stopOperator") or DEFAULT_STOP_OPERATOR)
        try:
            return evaluate(
                to_text(resolved.get("stopField")),
                operator,
                to_text(resolved.get("stopValue")),
                parse_bool(self.node_data.get("stopCaseSensitive", False)),
            )
        except ValueError as e:
            logger.warning("LoopNode %s %s, the stop condition is ignored", self.node_id, e)
        except re.error as e:
            logger.error("LoopNode %s invalid regex in the stop condition: %s", self.node_id, e)
        return False
