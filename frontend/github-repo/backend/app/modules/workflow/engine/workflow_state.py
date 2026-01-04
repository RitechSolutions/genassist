"""
Enhanced workflow state management for execution tracking and performance metrics.
"""

from typing import Dict, Any, Union
import logging
import uuid
from datetime import datetime
import time

from app.modules.workflow.agents.memory import BaseConversationMemory, ConversationMemory

logger = logging.getLogger(__name__)


class WorkflowState:
    """Enhanced class to maintain state during workflow execution with performance tracking"""

    def __init__(self,
                 workflow: dict,
                 initial_values: dict = None,
                 thread_id: str = str(uuid.uuid4())):
        """Initialize the workflow state

        Args:
            thread_id: Unique identifier for the thread
            workflow: Workflow dictionary
            initial_values: Dictionary with dot notation for nested initialization
        """
        self.thread_id = thread_id
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
            "successRate": 0
        }

        # Error tracking
        self.errors = []

        # Edge data and execution context
        self.source_edges = workflow.get(
            "source_edges", {}) if workflow else {}
        self.target_edges = workflow.get(
            "target_edges", {}) if workflow else {}

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
        keys = key_path.split('.')
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

    def add_node_output(self, node_id: str, output: Any, output_key: str = "result") -> None:
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
        return next(
            node for node in self.workflow["nodes"] if node["id"] == node_id)

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
            "timestamp": datetime.now().isoformat()
        }
        self.errors.append(error_entry)

    def clear_errors(self) -> None:
        """Clear all errors"""
        self.errors.clear()

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
        self.errors.clear()
        self.performance_metrics = {
            "totalExecutionTime": 0,
            "averageNodeExecutionTime": 0,
            "slowestNode": "",
            "slowestNodeTime": 0,
            "fastestNode": "",
            "fastestNodeTime": 0,
            "totalNodesExecuted": 0,
            "successRate": 0
        }

    def start_execution(self) -> None:
        """Start workflow execution"""
        self.status = "running"
        self.is_executing = True
        self.execution_start_time = int(time.time() * 1000)
        self.execution_path = []
        self.errors = []
        logger.info(f"Workflow execution started: {self.execution_id}")

    def pause_execution(self) -> None:
        """Pause workflow execution"""
        self.status = "paused"
        self.is_executing = False
        logger.info(f"Workflow execution paused: {self.execution_id}")

    def resume_execution(self) -> None:
        """Resume workflow execution"""
        self.status = "running"
        self.is_executing = True
        logger.info(f"Workflow execution resumed: {self.execution_id}")

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
        logger.error(
            f"Workflow execution failed: {self.execution_id}, Error: {error}")

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
            self.performance_metrics["totalNodesExecuted"] = len(
                execution_times)
            self.performance_metrics["totalExecutionTime"] = sum(
                time for _, time in execution_times)
            self.performance_metrics["averageNodeExecutionTime"] = self.performance_metrics["totalExecutionTime"] / len(
                execution_times)

            # Find fastest and slowest nodes
            fastest = min(execution_times, key=lambda x: x[1])
            slowest = max(execution_times, key=lambda x: x[1])

            self.performance_metrics["fastestNode"] = fastest[0]
            self.performance_metrics["fastestNodeTime"] = fastest[1]
            self.performance_metrics["slowestNode"] = slowest[0]
            self.performance_metrics["slowestNodeTime"] = slowest[1]

            # Calculate success rate
            successful_nodes = sum(1 for _, status in self.node_execution_status.items()
                                   if status.get("status") == "success")
            self.performance_metrics["successRate"] = (
                successful_nodes / len(self.node_execution_status)) * 100

    def start_node_execution(self, node_id: str) -> None:
        """Start execution of a specific node"""
        start_time = int(time.time() * 1000)
        self.node_execution_status[node_id] = {
            "type": self.get_node_config(node_id).get("type", ""),
            "name": self.get_node_config_data(node_id).get("name", ""),
            "status": "running",
            "startTime": start_time,
            "input": self.initial_values,
            "output": None,
            "error": None
        }
        logger.debug(f"Node execution started: {node_id}")

    def complete_node_execution(self, node_id: str, output: Any = None, error: str = None) -> None:
        """Complete execution of a specific node"""
        if node_id in self.node_execution_status:
            end_time = int(time.time() * 1000)
            self.node_execution_status[node_id].update({
                "status": "success" if error is None else "failed",
                "endTime": end_time,
                "output": output,
                "error": error
            })

            if error:
                self.add_error(f"Node {node_id}: {error}", "node_execution")

            logger.debug(f"Node execution completed: {node_id}")

    def get_thread_id(self) -> str:
        """Get the thread ID for this workflow execution"""
        return self.thread_id

    def get_session(self) -> dict:
        """Get the metadata for this workflow execution"""
        return self.get_value("session", {})

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
        return self.node_outputs.get(self.execution_path[-1]) if self.execution_path and self.execution_path[-1] else None

    def set_node_output(self, node_id: str, output: Any) -> None:
        """Set the output of a specific node"""
        self.node_outputs[node_id] = output
        # if node_id not in self.execution_path:
        self.execution_path.append(node_id)

    def set_node_input(self, node_id: str, input_data: Any) -> None:
        """Set the input for a specific node"""
        self.node_inputs[node_id] = input_data
        self.node_execution_status[node_id].update({
            "input": input_data
        })

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
            **self.node_execution_status, **state.node_execution_status}
        self.execution_path = [*self.execution_path, *state.execution_path]
        self.execution_history = [*self.execution_history, *state.execution_history]

    def get_full_state(self) -> Dict[str, Any]:
        """Get the complete state including all execution details"""
        return {
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
            "execution_end_time": self.execution_end_time
        }

    def format_state_as_response(self):
        """
        Format the workflow state as a response and sanitize for JSON compliance.
        """
        state = self.get_full_state()
        summary = self.get_execution_summary()

        _input = self.initial_values.get("message", "") if self.initial_values and self.initial_values.get(
            "message", None) else self.initial_values

        output = state["output"] if state["output"] else summary["node_outputs"][summary["execution_path"]
                                                                               [-1]] if "execution_path" in summary and summary["execution_path"] else None
        performance_metrics = self.performance_metrics
        status = "success"
        response = {
            "status": status,
            "input": _input,
            "output": output,
            "performance_metrics": performance_metrics,
            "state": state
        }

        # Sanitize response to ensure JSON compliance (handle inf, -inf, nan values)
        from app.modules.workflow.engine.nodes.ml import ml_utils
        return ml_utils.sanitize_for_json(response)
