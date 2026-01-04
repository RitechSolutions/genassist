"""
Tool builder node implementation using the BaseNode class.
"""

from typing import Dict, Any, List
import logging
import time
import json

from app.modules.workflow.engine.base_node import BaseNode

logger = logging.getLogger(__name__)


class ToolBuilderNode(BaseNode):
    """Tool builder node that executes subflows and returns tool references using the BaseNode approach"""

    async def process(self, config: Dict[str, Any]) -> Dict[str, Any]:  # pylint: disable=unused-argument
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
        template = json.loads(config.get("forwardTemplate", "{}"))
        source_input = self.get_state().get_session_flat()
        
        workflow_engine = WorkflowEngine.get_instance()
        next_node = self.get_connected_nodes("starter")
        
        if len(next_node) == 0:
            no_source_template = config.get("forwardTemplate", "{}").replace("source.", "")
            return {**json.loads(no_source_template), **source_input}
        start_node_id = next_node[0]
        state = await workflow_engine.execute_from_node(self.get_state().workflow_id, start_node_id=start_node_id, input_data={**template, **source_input}, thread_id=self.get_state().get_thread_id())
        self.get_state().update_nodes_from_another_state(state)
        return state.get_last_node_output()
