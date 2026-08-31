"""
Enhanced workflow state management for execution tracking and performance metrics.
"""

import copy
import json
import logging
import time
import uuid
from datetime import datetime
from typing import Any, Dict, Optional, Union

from app.core.utils.llm_usage_utils import extract_cache_tokens
from app.modules.workflow.agents.memory import (
    BaseConversationMemory,
    ConversationMemory,
)

logger = logging.getLogger(__name__)

# Cap the size of tool arguments/results stored on an event so a large tool
# result cannot bloat the persisted trace.
_MAX_EVENT_VALUE_CHARS = 8000


def _bound_event_value(value: Any) -> Any:
    """Return a JSON-safe copy of the value, truncated when it serializes too large.

    Serializing with default=str collapses custom objects (and cyclic graphs,
    which raise) to strings, so no live object leaks into tool_events — a leak
    would later blow up the recursive JSON sanitizer walking their __dict__.
    """
    if isinstance(value, str):
        serialized = safe_value = value
    else:
        try:
            serialized = json.dumps(value, default=str)
            safe_value = json.loads(serialized)
        except (TypeError, ValueError):
            safe_value = serialized = str(value)
    if len(serialized) <= _MAX_EVENT_VALUE_CHARS:
        return safe_value
    return {
        "_truncated": True,
        "chars": len(serialized),
        "preview": serialized[:_MAX_EVENT_VALUE_CHARS],
    }


def _strip_live_tool_refs(node_execution_status: dict) -> dict:
    """Drop live ``tools_reference`` tool objects from node inputs before serialization.

    Each tool holds a back-reference to this WorkflowState, so leaving them in a
    serialized trace creates a reference cycle. Returns a shallow copy; the live
    state the agent is still using is left untouched.
    """
    cleaned = {}
    for node_id, entry in node_execution_status.items():
        node_input = entry.get("input") if isinstance(entry, dict) else None
        if isinstance(node_input, dict) and "tools_reference" in node_input:
            entry = {**entry, "input": {k: v for k, v in node_input.items() if k != "tools_reference"}}
        cleaned[node_id] = entry
    return cleaned


class WorkflowPausedException(BaseException):
    """Raised when a node (e.g. HumanInTheLoop) needs to pause the workflow.

    Inherits from BaseException (not Exception) so it bypasses all broad
    `except Exception` handlers automatically, without requiring explicit
    re-raise checks in every agent and node handler.
    """

    def __init__(self, pause_data: dict):
        self.pause_data = pause_data
        super().__init__("Workflow paused")


class WorkflowState:
    """Enhanced class to maintain state during workflow execution with performance tracking"""

    def __init__(
        self,
        workflow: dict,
        initial_values: dict = None,
        thread_id: str = str(uuid.uuid4()),
        registry_managed: bool = False,
    ):
        """Initialize the workflow state

        Args:
            thread_id: Unique identifier for the thread
            workflow: Workflow dictionary
            initial_values: Dictionary with dot notation for nested initialization
            registry_managed: True only on the interactive registry path that can
                persist and resume sub-agent frames; other entry points may run
                single_turn delegations but not the persistent (task/chat) ones
        """
        self.thread_id = thread_id
        self.registry_managed = registry_managed
        self.sub_agent_persistent_claimed = False
        if initial_values is None:
            initial_values = {}
        self.initial_values = initial_values
        self.session = initial_values if initial_values else {}
        self.timestamp = datetime.now().isoformat()
        self.execution_id = str(uuid.uuid4())
        self.workflow = workflow
        self.workflow_id = workflow.get("config", {}).get("id")
        self.memory = ConversationMemory.get_instance(thread_id=self.thread_id)
        # Execution tracking
        self.status = "idle"  # idle, running, completed, failed, paused
        self.output = ""
        self.is_executing = False
        self.current_step = 0
        self.total_steps = 0
        self.execution_start_time = None
        self.execution_end_time = None

        # Node execution tracking
        self.node_outputs: dict[str, Any] = {}
        self.node_inputs: dict[str, Any] = {}
        self.node_execution_status: dict[str, Any] = {}
        self.execution_path: list[str] = []
        self.execution_history: list[str] = []
        # The single store for prompt-caching diagnostics: this run's own nodes plus any
        # propagated in from sub-agent child runs. Kept out of node_execution_status so
        # no metric, analytics or failure consumer ever sees them
        self.prompt_caching_diagnostics: dict[str, Any] = {}

        # Performance metrics
        self.time_taken = 0
        self.performance_metrics = {
            "totalExecutionTime": 0,
            "averageNodeExecutionTime": 0,
            "slowestNode": "",
            "slowestNodeTime": 0,
            "fastestNode": "",
            "fastestNodeTime": 0,
            "totalNodesExecuted": 0,
            "successRate": 0,
        }

        # Error tracking
        self.errors = []

        # LLM token usage and cost tracking (per request)
        self.llm_usage: list[dict] = []

        # Normalized tool-execution events, one per tool call.
        self.tool_events: list[dict] = []

        # Edge data and execution context
        self.source_edges = workflow.get("source_edges", {}) if workflow else {}
        self.target_edges = workflow.get("target_edges", {}) if workflow else {}

        # Apply initial values if provided
        if initial_values:
            self._apply_initial_values(initial_values)

    def _apply_initial_values(self, initial_values: dict) -> None:
        """Apply initial values using dot notation for nested attributes

        Args:
            initial_values: Dictionary with dot notation keys
        """
        # Create a copy of items to avoid "dictionary changed size during iteration" error
        for key_path, value in list(initial_values.items()):
            self._set_nested_value(key_path, value)

    def _set_nested_value(self, key_path: str, value: Any) -> None:
        """Set a nested value using dot notation

        Args:
            key_path: Dot-separated path to the nested attribute
            value: Value to set
        """
        keys = key_path.split(".")
        current: Union[Dict, Any] = self

        # Navigate to the parent of the target attribute
        for key in keys[:-1]:
            if isinstance(current, dict):
                # Working with a dictionary
                current_dict = current  # Type narrowing for linter
                if key not in current_dict:
                    current_dict[key] = {}
                current = current_dict[key]
            else:
                # Working with an object
                if not hasattr(current, key):
                    setattr(current, key, {})
                current = getattr(current, key)

        # Set the final value
        final_key = keys[-1]
        if isinstance(current, dict):
            current_dict = current  # Type narrowing for linter
            current_dict[final_key] = value
        else:
            setattr(current, final_key, value)

    def set_value(self, key_path: str, value: Any) -> None:
        """Set a value using dot notation

        Args:
            key_path: Dot-separated path to the attribute
            value: Value to set
        """
        self._set_nested_value(key_path, value)

    def get_value(self, key_path: str, default: Any = None) -> Any:
        """Get a value using dot notation

        Args:
            key_path: Dot-separated path to the attribute
            default: Default value if the path doesn't exist

        Returns:
            The value at the specified path, or default if not found
        """
        from app.modules.workflow.engine.utils import get_nested_value

        result = get_nested_value(self, key_path)
        return result if result is not None else default

    def add_node_output(
        self, node_id: str, output: Any, output_key: str = "result"
    ) -> None:
        """Add output for a specific node with a specific key

        Args:
            node_id: ID of the node
            output: Output value
            output_key: Key for the output (defaults to "result")
        """
        if node_id not in self.node_outputs:
            self.node_outputs[node_id] = {}
        self.node_outputs[node_id][output_key] = output
        # if node_id not in self.execution_path:
        self.execution_path.append(node_id)

    def get_node_config(self, node_id: str) -> dict:
        """Get the config for a specific node"""
        return next(node for node in self.workflow["nodes"] if node["id"] == node_id)

    def get_node_config_data(self, node_id: str) -> dict:
        """Get the config data for a specific node"""
        return self.get_node_config(node_id).get("data", {})

    def remove_node_output(self, node_id: str, output_key: str = None) -> None:
        """Remove output for a specific node

        Args:
            node_id: ID of the node
            output_key: Specific output key to remove, or None to remove all outputs for the node
        """
        if node_id in self.node_outputs:
            if output_key is None:
                del self.node_outputs[node_id]
                if node_id in self.execution_path:
                    self.execution_path.remove(node_id)
            elif output_key in self.node_outputs[node_id]:
                del self.node_outputs[node_id][output_key]

    def clear_node_outputs(self) -> None:
        """Clear all node outputs"""
        self.node_outputs.clear()
        self.execution_path.clear()

    def add_error(self, error: str, error_type: str = "general") -> None:
        """Add an error with optional type classification

        Args:
            error: Error message
            error_type: Type of error (defaults to "general")
        """
        error_entry = {
            "message": error,
            "type": error_type,
            "timestamp": datetime.now().isoformat(),
        }
        self.errors.append(error_entry)

    def clear_errors(self) -> None:
        """Clear all errors"""
        self.errors.clear()

    def add_llm_usage(
        self,
        input_tokens: int,
        output_tokens: int,
        provider: str = "",
        model: str = "",
        node_id: str = "",
        purpose: Optional[str] = None,
        token_details: Optional[dict] = None,
        llm_provider_id: Optional[str] = None,
        total_tokens: Optional[int] = None,
        prompt_caching_enabled: bool = False,
    ) -> None:
        """Append LLM token usage for this workflow execution"""
        self.llm_usage.append({
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": max(int(total_tokens or 0), input_tokens + output_tokens),
            "provider": provider,
            "model": model,
            "node_id": node_id,
            "purpose": purpose,
            "token_details": token_details,
            "llm_provider_id": llm_provider_id,
            "prompt_caching_enabled": prompt_caching_enabled,
        })

    def add_tool_event(
        self,
        *,
        agent_id: str | None,
        tool_id: str | None,
        tool_name: str,
        arguments: Any,
        result: Any,
        status: str,
        error: str | None = None,
    ) -> None:
        """Record a single tool call. Arguments/result are redacted before storing."""
        from app.core.utils.sensitive_data_utils import redact_structure

        self.tool_events.append({
            "event_id": str(uuid.uuid4()),
            "agent_id": agent_id,
            "tool_id": tool_id,
            "tool_name": tool_name,
            "arguments": _bound_event_value(redact_structure(arguments)),
            "result": _bound_event_value(redact_structure(result)),
            "status": status,
            "error": error,
            "sequence": len(self.tool_events),
            "workflow_path": [self.workflow_id] if self.workflow_id else [],
        })

    def absorb_tool_events(self, child_state: "WorkflowState") -> None:
        """Merge a sub-workflow's tool events, prepending this workflow to their path."""
        parent = [self.workflow_id] if self.workflow_id else []
        for event in child_state.tool_events:
            self.tool_events.append(
                {**event, "workflow_path": parent + event.get("workflow_path", [])}
            )

    def get_total_llm_usage(self) -> dict:
        """Sum token usage and compute total cost in USD."""
        total_input = sum(u.get("input_tokens", 0) for u in self.llm_usage)
        total_output = sum(u.get("output_tokens", 0) for u in self.llm_usage)
        total_tokens = sum(
            max(u.get("total_tokens") or 0, u.get("input_tokens", 0) + u.get("output_tokens", 0))
            for u in self.llm_usage
        )
        total_cost_usd = 0.0
        total_cache_read = 0
        total_cache_creation = 0
        from app.services.llm_cost_calculator import LlmCostCalculator
        self.llm_cost_calculator = LlmCostCalculator()
        for u in self.llm_usage:
            cache_read, cache_creation = extract_cache_tokens(u.get("token_details"))
            total_cache_read += cache_read
            total_cache_creation += cache_creation
            total_cost_usd += self.llm_cost_calculator.calculate_cost(
                u.get("provider", ""),
                u.get("model", ""),
                u.get("input_tokens", 0),
                u.get("output_tokens", 0),
            )
        totals = {
            "input_tokens": total_input,
            "output_tokens": total_output,
            "total_tokens": total_tokens,
            "cache_read_tokens": total_cache_read,
            "cache_creation_tokens": total_cache_creation,
            "cost_usd": round(total_cost_usd, 6),
            "calls": len(self.llm_usage),
        }
        if not (total_cache_read or total_cache_creation or self._prompt_caching_requested()):
            del totals["cache_read_tokens"]
            del totals["cache_creation_tokens"]
        return totals

    def _prompt_caching_requested(self) -> bool:
        """Whether any call this run came from a node with the caching toggle on"""
        return any(u.get("prompt_caching_enabled") for u in self.llm_usage)

    def reset_execution_state(self) -> None:
        """Reset execution state to initial values"""
        self.status = "idle"
        self.is_executing = False
        self.current_step = 0
        self.execution_start_time = None
        self.execution_end_time = None
        self.time_taken = 0
        self.node_execution_status.clear()
        self.execution_path.clear()
        self.execution_history.clear()
        self.prompt_caching_diagnostics.clear()
        self.errors.clear()
        self.llm_usage.clear()
        self.tool_events.clear()
        self.performance_metrics = {
            "totalExecutionTime": 0,
            "averageNodeExecutionTime": 0,
            "slowestNode": "",
            "slowestNodeTime": 0,
            "fastestNode": "",
            "fastestNodeTime": 0,
            "totalNodesExecuted": 0,
            "successRate": 0,
        }

    def start_execution(self) -> None:
        """Start workflow execution"""
        self.status = "running"
        self.is_executing = True
        self.execution_start_time = int(time.time() * 1000)
        self.execution_path = []
        self.errors = []
        logger.info(f"Workflow execution started: {self.execution_id}")

    def complete_execution(self) -> None:
        """Complete workflow execution"""
        self.status = "completed"
        self.is_executing = False
        self.execution_end_time = int(time.time() * 1000)
        self.output = self.get_last_node_output()
        if self.execution_start_time:
            self.time_taken = self.execution_end_time - self.execution_start_time
        self._update_performance_metrics()
        logger.info(f"Workflow execution completed: {self.execution_id}")

    def fail_execution(self, error: str) -> None:
        """Mark workflow execution as failed"""
        self.status = "failed"
        self.is_executing = False
        self.execution_end_time = int(time.time() * 1000)
        if self.execution_start_time:
            self.time_taken = self.execution_end_time - self.execution_start_time
        self.add_error(error, "execution_failure")
        logger.error(f"Workflow execution failed: {self.execution_id}, Error: {error}")

    def _update_performance_metrics(self) -> None:
        """Update performance metrics based on execution data"""
        if not self.node_execution_status:
            return

        execution_times = []
        for node_id, status in self.node_execution_status.items():
            if status.get("startTime") and status.get("endTime"):
                execution_time = status["endTime"] - status["startTime"]
                execution_times.append((node_id, execution_time))

        if execution_times:
            self.performance_metrics["totalNodesExecuted"] = len(execution_times)
            self.performance_metrics["totalExecutionTime"] = sum(
                time for _, time in execution_times
            )
            self.performance_metrics["averageNodeExecutionTime"] = (
                self.performance_metrics["totalExecutionTime"] / len(execution_times)
            )

            # Find fastest and slowest nodes
            fastest = min(execution_times, key=lambda x: x[1])
            slowest = max(execution_times, key=lambda x: x[1])

            self.performance_metrics["fastestNode"] = fastest[0]
            self.performance_metrics["fastestNodeTime"] = fastest[1]
            self.performance_metrics["slowestNode"] = slowest[0]
            self.performance_metrics["slowestNodeTime"] = slowest[1]

            # Calculate success rate
            successful_nodes = sum(
                1
                for _, status in self.node_execution_status.items()
                if status.get("status") == "success"
            )
            self.performance_metrics["successRate"] = (
                successful_nodes / len(self.node_execution_status)
            ) * 100

    def _next_archived_node_key(self, node_id: str) -> str:
        """Return the next available key for an archived run of this node (e.g. node_id_0, node_id_1)."""
        prefix = f"{node_id}_"
        indices = []
        for key in self.node_execution_status:
            if key == node_id or key.startswith(prefix):
                if key == node_id:
                    indices.append(
                        -1
                    )  # current slot, treat as prior run for next index
                else:
                    try:
                        indices.append(int(key[len(prefix) :]))
                    except ValueError:
                        pass
        next_index = max(indices, default=-1) + 1
        return f"{node_id}_{next_index}"

    def start_node_execution(self, node_id: str) -> None:
        """Start execution of a specific node. If the node was run before, the previous run
        is kept under a prefixed key (e.g. node_id_0, node_id_1); only the latest run stays as node_id.
        """
        if node_id in self.node_execution_status:
            archived_key = self._next_archived_node_key(node_id)
            self.node_execution_status[archived_key] = self.node_execution_status.pop(
                node_id
            )
        start_time = int(time.time() * 1000)
        self.node_execution_status[node_id] = {
            "type": self.get_node_config(node_id).get("type", ""),
            "name": self.get_node_config_data(node_id).get("name", ""),
            "status": "running",
            "startTime": start_time,
            "input": self.initial_values,
            "output": None,
            "error": None,
        }
        logger.debug(f"Node execution started: {node_id}")

    def complete_node_execution(
        self, node_id: str, output: Any = None, error: str = None
    ) -> None:
        """Complete execution of a specific node"""
        if node_id in self.node_execution_status:
            end_time = int(time.time() * 1000)
            start_time = self.node_execution_status[node_id].get("startTime")
            duration_ms = (
                end_time - start_time if start_time is not None else None
            )
            self.node_execution_status[node_id].update(
                {
                    "status": "success" if error is None else "failed",
                    "endTime": end_time,
                    "time_taken": duration_ms,
                    "output": output,
                    "error": error,
                }
            )

            if error:
                self.add_error(f"Node {node_id}: {error}", "node_execution")

            logger.debug(f"Node execution completed: {node_id}")

    def get_thread_id(self) -> str:
        """Get the thread ID for this workflow execution"""
        return self.thread_id

    def get_session(self) -> dict:
        """Get the metadata for this workflow execution"""
        return self.get_value("session", {})

    def update_session_value(self, key: str, value: Any) -> None:
        """Update a value in the session"""
        session = self.get_session()
        session[key] = value
        self.set_value("session", session)
        logger.debug(f"Session value updated: {key} = {value}")

    def get_session_flat(self) -> dict:
        """Get the session values as a flattened dictionary with dot notation keys

        Returns:
            Dict with flattened session values using dot notation keys
            e.g., {"session.val1": "val", "session.value2.val": "val"}
        """
        from app.modules.workflow.engine.utils import flatten_dict

        session_data = self.get_value("session", {})
        return flatten_dict(session_data, prefix="session")

    def get_memory(self) -> BaseConversationMemory:
        """Get the conversation memory for this workflow execution"""
        return self.memory

    def capture_resume_context(self) -> dict:
        """Snapshot the request context a paused execution needs to resume as the same
        logical run.

        A node that pauses (e.g. HumanInTheLoop) stores this; on resume the engine starts
        a fresh WorkflowState at the paused node, so without rehydration the original
        request inputs and session (the message, conversation_history, stateful values and
        any metadata the pre-pause nodes saw) would be lost. node_outputs is captured
        separately by the pausing node.
        """
        from app.modules.workflow.agents.sub_agents.models import SUB_AGENT_RESUME_KEY

        # The sub-agent resume marker is re-supplied on every resume; capturing it would
        # nest each prior payload into the next frame until the size guard trips.
        initial = {k: v for k, v in (self.initial_values or {}).items() if k != SUB_AGENT_RESUME_KEY}
        session = {k: v for k, v in (self.get_session() or {}).items() if k != SUB_AGENT_RESUME_KEY}
        # Deep copy so a later resume (which restores this) can't alias and mutate the
        # values this execution is still using; also matches the JSON round-trip the Redis
        # memory backend performs, keeping behaviour identical across backends.
        return copy.deepcopy({
            "initial_values": initial,
            "session": session,
        })

    def restore_resume_context(
        self, snapshot: dict, drop_keys: set[str] | None = None
    ) -> None:
        """Rehydrate request context captured by capture_resume_context() into this state.

        The CURRENT (resume) request defines the turn — its message, metadata and submitted
        form data always win. The snapshot only fills in context the resume request lacks
        (e.g. stateful/session values the pre-pause chat input computed), so downstream
        nodes keep that context without losing the user's actual submission. Keys in
        drop_keys are never imported from the snapshot — turn-specific flags (e.g. the
        invisible start-form trigger) must not leak into the resumed turn.
        """
        if not snapshot:
            return
        drop_keys = drop_keys or set()

        saved_initial = {
            k: v
            for k, v in (snapshot.get("initial_values") or {}).items()
            if k not in drop_keys
        }
        if saved_initial:
            # Current request wins; the snapshot only fills keys the resume request lacks.
            merged = {**saved_initial, **self.initial_values}
            self.initial_values = merged
            self.session = merged
            self._apply_initial_values(merged)

        saved_session = snapshot.get("session")
        if saved_session:
            current_session = self.get_session()
            filled = {
                **{k: v for k, v in saved_session.items() if k not in drop_keys},
                **current_session,
            }
            self.set_value("session", filled)

    def record_workflow_output(self, output: Any) -> None:
        """Record the final output of the workflow execution"""
        self.output = output

    def get_workflow_output(self) -> Any:
        """Get the final output of the workflow execution"""
        return self.output

    def get_node_output(self, node_id: str) -> Any:
        """Get the output of a specific node"""
        return self.node_outputs.get(node_id)

    def get_last_node_output(self) -> Any:
        """Get the output of the last node"""
        return (
            self.node_outputs.get(self.execution_path[-1])
            if self.execution_path and self.execution_path[-1]
            else None
        )

    def set_node_output(self, node_id: str, output: Any) -> None:
        """Set the output of a specific node"""
        self.node_outputs[node_id] = output
        # if node_id not in self.execution_path:
        self.execution_path.append(node_id)

    def set_node_input(self, node_id: str, input_data: Any) -> None:
        """Set the input for a specific node"""
        self.node_inputs[node_id] = input_data
        self.node_execution_status[node_id].update({"input": input_data})

    def get_node_input(self, node_id: str) -> Any:
        """Get the input for a specific node"""
        return self.node_inputs.get(node_id)

    def get_execution_summary(self) -> Dict[str, Any]:
        """Get a comprehensive summary of the workflow execution"""
        return {
            "execution_id": self.execution_id,
            "thread_id": self.thread_id,
            "timestamp": self.timestamp,
            "execution_path": self.execution_path,
            "input": self.initial_values,
            "node_outputs": self.node_outputs,
        }

    def update_nodes_from_another_state(self, state: "WorkflowState") -> None:
        """Update the nodes from another state"""
        self.node_outputs = {**self.node_outputs, **state.node_outputs}
        self.node_inputs = {**self.node_inputs, **state.node_inputs}
        self.node_execution_status = {
            **self.node_execution_status,
            **state.node_execution_status,
        }
        self.prompt_caching_diagnostics = {
            **self.prompt_caching_diagnostics,
            **state.prompt_caching_diagnostics,
        }
        self.execution_path = [*self.execution_path, *state.execution_path]
        self.execution_history = [*self.execution_history, *state.execution_history]
        # Usage is not merged here: nested engines append into the parent usage_sink,
        # so merging again would double-count.
        self.absorb_tool_events(state)

        # Merge stateful values from sub-workflow session into parent session
        # This ensures stateful values updated in sub-workflows propagate to parent
        # Note: We don't merge conversation_history as it's managed separately
        sub_session = state.get_session()
        parent_session = self.get_session()
        for key, value in sub_session.items():
            # Skip conversation_history as it's managed separately
            if key == "conversation_history":
                continue
            # Merge stateful values: if key doesn't exist in parent or values differ,
            # update parent with sub-workflow's value (sub-workflow may have updated via SetStateNode)
            if key not in parent_session or parent_session.get(key) != value:
                parent_session[key] = value
                self.update_session_value(key, value)

    def get_full_state(self) -> Dict[str, Any]:
        """Get the complete state including all execution details"""
        full = {
            "status": self.status,
            "input": self.initial_values,
            "output": self.output,
            "workflow_id": self.workflow_id,
            "time_taken": self.time_taken,
            "is_executing": self.is_executing,
            "current_step": self.current_step,
            "total_steps": self.total_steps,
            "execution_start_time": self.execution_start_time,
            "nodeExecutionStatus": self.node_execution_status,
            "executionHistory": self.execution_history,
            "errors": self.errors,
            "performanceMetrics": self.performance_metrics,
            "execution_end_time": self.execution_end_time,
        }
        # Conditional: a run with no opted-in sub-agent stays byte-identical to before
        if self.prompt_caching_diagnostics:
            from app.modules.workflow.engine.prompt_cache_diagnostics import with_observed_cache_tokens

            full["promptCachingDiagnostics"] = with_observed_cache_tokens(
                self.prompt_caching_diagnostics, self.llm_usage
            )
        return full

    def _collect_failed_nodes(self) -> list[dict]:
        """Collect the nodes that failed in this run, latest run per node only.

        Re-run nodes are archived under prefixed keys (e.g. ``node_id_0``); only
        the latest run keeps the un-suffixed ``node_id`` key. We ignore archived
        keys so a node that failed once and later succeeded is not reported as
        failed (mirrors the frontend's `stripArchivedKeys`).
        """
        import re

        keys = set(self.node_execution_status.keys())
        failed: list[dict] = []
        for node_id, entry in self.node_execution_status.items():
            # Skip archived earlier runs: "<base>_<n>" where <base> is also a key.
            match = re.match(r"^(.+)_(\d+)$", node_id)
            if match and match.group(1) in keys:
                continue
            if not isinstance(entry, dict) or entry.get("status") != "failed":
                continue
            failed.append({
                "node_id": node_id,
                "name": entry.get("name") or "",
                "type": entry.get("type") or "",
                "error": entry.get("error") or "",
            })
        return failed

    def format_state_as_response(self):
        """
        Format the workflow state as a response and sanitize for JSON compliance.
        """
        state = self.get_full_state()
        state["nodeExecutionStatus"] = _strip_live_tool_refs(state.get("nodeExecutionStatus", {}))
        summary = self.get_execution_summary()

        _input = (
            self.initial_values.get("message", "")
            if self.initial_values and self.initial_values.get("message", None)
            else self.initial_values
        )

        output = (
            state["output"]
            if state["output"]
            else (
                summary["node_outputs"][summary["execution_path"][-1]]
                if "execution_path" in summary and summary["execution_path"]
                else None
            )
        )
        performance_metrics = self.performance_metrics

        # Detect awaiting_input from node output (HumanInTheLoopNode returns form_schema as output)
        if isinstance(output, dict) and output.get("status") == "awaiting_input":
            status = "awaiting_input"
        else:
            status = "success"

        # Surface node-level failures at the run level. This is ADDITIVE: the
        # top-level `status` stays "success" (the workflow still completed and
        # produced a response), but `has_failures`/`failed_nodes` let callers and
        # the UI know a node did not do its job (e.g. a Zendesk ticket that was
        # never created despite a 200-style flow). See node_result.is_node_failure.
        failed_nodes = self._collect_failed_nodes()

        token_usage = self.get_total_llm_usage()
        response = {
            "status": status,
            "has_failures": len(failed_nodes) > 0,
            "failed_nodes": failed_nodes,
            "input": _input,
            "output": output,
            "performance_metrics": performance_metrics,
            "state": state,
            "token_usage": token_usage,
            "cost_usd": token_usage.get("cost_usd", 0.0),
            "execution_id": self.execution_id,
            "tool_events": self.tool_events,
        }

        # Sanitize response to ensure JSON compliance (handle inf, -inf, nan values)
        # and optimize large arrays with uniform schemas for performance
        from app.modules.workflow.engine.nodes.ml import ml_utils

        return ml_utils.sanitize_for_json(response)
