"""
Tool builder node implementation using the BaseNode class.
"""

import logging
import json
from typing import Dict, Any

from app.modules.workflow.engine.base_node import BaseNode

logger = logging.getLogger(__name__)


class ToolBuilderNode(BaseNode):
    """Tool builder node that executes subflows and returns tool references using the BaseNode approach"""

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

        template_str = config.get("forwardTemplate", "{}")
        logger.debug(f"Template string: {template_str}")
        try:
            template = json.loads(template_str)
        except Exception as e:
            logger.error(f"Error loading template: {e}")
            return {
                "status": 500,
                "data": {
                    "template": template_str,
                    "error": f"Error loading tool builder parameters: {e}",
                },
            }
        source_input = self.get_state().get_session_flat()

        next_node = self.get_connected_nodes("starter")

        if len(next_node) == 0:
            no_source_template = config.get("forwardTemplate", "{}").replace(
                "source.", ""
            )
            return {**json.loads(no_source_template), **source_input}
        start_node_id = next_node[0]
        temp_data: Dict[str, Any] = {"node_outputs": {}}

        no_source_template = config.get("forwardTemplate", "{}").replace("source.", "")
        temp_data["node_outputs"][self.node_id] = json.loads(no_source_template)

        # Create a new workflow engine with the current workflow configuration
        current_workflow = self.get_state().workflow
        if not current_workflow:
            raise ValueError("No workflow found in state")
        
        workflow_config = {
            "id": self.get_state().workflow_id,
            "nodes": current_workflow.get("nodes", []),
            "edges": current_workflow.get("edges", []),
        }
        workflow_engine = WorkflowEngine(workflow_config)

        state = await workflow_engine.execute_from_node(
            start_node_id=start_node_id,
            input_data={**template, **source_input, **temp_data},
            thread_id=self.get_state().get_thread_id(),
            persist=False,
        )
        self.get_state().update_nodes_from_another_state(state)
        return state.get_last_node_output()
