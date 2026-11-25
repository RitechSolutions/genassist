"""
Tool builder node implementation using the BaseNode class.
"""

import logging
import json
import re
from typing import Any, Dict, List

from app.modules.workflow.engine.base_node import BaseNode
from app.modules.workflow.engine.node_result import INPUT_REJECTED, input_rejection, node_failure
from app.modules.workflow.engine.utils import _is_in_string_context
from app.modules.workflow.engine.workflow_state import (
    SAVED_WORKFLOW_ID_KEY,
    WorkflowPausedException,
    failed_nodes_summary,
)

logger = logging.getLogger(__name__)


def _subflow_failure(blocking_failures: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Failure of a tool whose subflow stopped at a failed node."""
    reason = failed_nodes_summary({"failed_nodes": blocking_failures})
    only_refused_input = all(failure.get("code") == INPUT_REJECTED for failure in blocking_failures)
    if only_refused_input:
        return input_rejection(reason)
    return node_failure(reason)


def _is_optional_text(parameter: Any) -> bool:
    """Whether a tool parameter is text the agent may leave out."""
    if not isinstance(parameter, dict):
        return False
    is_text = parameter.get("type", "string") == "string"
    return is_text and not parameter.get("required", False)


def _is_used_without_quotes(template: str, name: str) -> bool:
    """Whether the forward template uses the parameter outside a quoted text value."""
    placeholder = re.escape(f"{{{{direct_input.parameters.{name}}}}}")
    positions = [match.start() for match in re.finditer(placeholder, template)]
    return any(not _is_in_string_context(template, position) for position in positions)


class ToolBuilderNode(BaseNode):
    """Tool builder node that executes subflows and returns tool references using the BaseNode approach"""

    async def execute(self, direct_input: Any = None) -> Any:
        """Run the tool. Optional text the agent left out reaches the subflow empty, not as the word null."""
        return await super().execute(self._with_left_out_text_filled(direct_input))

    def _with_left_out_text_filled(self, direct_input: Any) -> Any:
        """The tool call with each left-out optional text parameter set to its default, or empty."""
        given = direct_input.get("parameters") if isinstance(direct_input, dict) else None
        if not isinstance(given, dict):
            return direct_input
        left_out = {
            name: parameter.get("defaultValue") or ""
            for name, parameter in (self.get_input_schema() or {}).items()
            if given.get(name) is None and self._takes_empty_text(name, parameter)
        }
        return {**direct_input, "parameters": {**given, **left_out}}

    def _takes_empty_text(self, name: str, parameter: Any) -> bool:
        """Whether the parameter is optional text that the forward template keeps inside quotes."""
        template = self.get_node_data().get("forwardTemplate") or ""
        return _is_optional_text(parameter) and not _is_used_without_quotes(template, name)

    async def process(
        self, config: Dict[str, Any]
    ) -> Dict[str, Any]:  # pylint: disable=unused-argument
        """
        Process the tool builder node by executing its subflow.

        The tool builder node is responsible for:
        1. Finding the subflow boundaries (start and end nodes)
        2. Executing the subflow in isolation
        3. Collecting and returning the results

        Args:
            config: The resolved configuration for the node

        Returns:
            Dictionary with subflow execution results
        """
        from app.modules.workflow.engine.workflow_engine import WorkflowEngine

        template_str = config.get("forwardTemplate") or "{}"
        logger.debug(f"Template string: {template_str}")
        try:
            template = json.loads(template_str)
        except Exception as e:
            logger.error(f"Error loading template: {e}")
            error_msg = f"Error loading tool builder parameters: {e}"
            return node_failure(
                error_msg,
                code=500,
                output={"status": 500, "data": {"template": template_str, "error": error_msg}},
            )
        source_input = self.get_state().get_session_flat()

        next_node = self.get_connected_nodes("starter")

        if len(next_node) == 0:
            no_source_template = (config.get("forwardTemplate") or "{}").replace(
                "source.", ""
            )
            return {**json.loads(no_source_template), **source_input}
        start_node_id = next_node[0]
        temp_data: Dict[str, Any] = {"node_outputs": {}}

        no_source_template = (config.get("forwardTemplate") or "{}").replace("source.", "")
        temp_data["node_outputs"][self.node_id] = json.loads(no_source_template)

        # Build a workflow engine from the current workflow configuration
        current_workflow = self.get_state().workflow
        if not current_workflow:
            raise ValueError("No workflow found in state")
        
        workflow_config = {
            "id": self.get_state().workflow_id,
            "nodes": current_workflow.get("nodes", []),
            "edges": current_workflow.get("edges", []),
            SAVED_WORKFLOW_ID_KEY: (current_workflow.get("config") or {}).get(SAVED_WORKFLOW_ID_KEY),
        }
        workflow_engine = WorkflowEngine(workflow_config)

        state = await workflow_engine.execute_from_node(
            start_node_id=start_node_id,
            input_data={**template, **source_input, **temp_data},
            thread_id=self.get_state().get_thread_id(),
            persist=False,
            usage_sink=self.get_state().llm_usage,
        )
        self.get_state().update_nodes_from_another_state(state)

        # If the subflow was paused (e.g. HumanInTheLoop), propagate the pause
        # up through the agent so the top-level engine can return the form to the user
        if isinstance(state.output, dict) and state.output.get("status") == "awaiting_input":
            raise WorkflowPausedException(state.output)

        blocking_failures = state.blocking_failures()
        if blocking_failures:
            return _subflow_failure(blocking_failures)

        return state.get_last_node_output()
