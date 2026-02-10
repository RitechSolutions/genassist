"""
Workflow executor node implementation using the BaseNode class.
This node allows selecting a workflow from the workflow list, passing parameters,
and executing it, returning the response.
"""

from typing import Dict, Any
import logging
import uuid
from uuid import UUID
from app.modules.workflow.engine.base_node import BaseNode
from app.services.workflow import WorkflowService

logger = logging.getLogger(__name__)


class WorkflowExecutorNode(BaseNode):
    """Workflow executor node that can select and execute workflows"""

    async def process(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a workflow executor node by selecting a workflow and executing it.

        Args:
            config: The resolved configuration for the node containing:
                - workflowId: UUID of the workflow to execute
                - params: Dictionary of parameters to pass to the workflow
                - threadId: Optional thread ID for the workflow execution

        Returns:
            Dictionary with workflow execution results
        """
        workflow_id_str = config.get("workflowId")
        params: Dict[str, Any] = config.get("inputParameters", {})
        thread_id = params.get("threadId", config.get("threadId", str(uuid.uuid4())))

        if not workflow_id_str:
            error_msg = "workflowId is required for workflow executor node"
            logger.error(error_msg)
            return {"error": error_msg, "status": "error"}

        try:
            # Convert workflow_id to UUID if it's a string
            try:
                workflow_id = UUID(workflow_id_str) if isinstance(workflow_id_str, str) else workflow_id_str
            except (ValueError, AttributeError, TypeError) as e:
                error_msg = f"Invalid workflowId format: {workflow_id_str}"
                logger.error(error_msg)
                return {"error": error_msg, "status": "error"}

            # Get workflow service to fetch workflow details
            from app.dependencies.injector import injector
            workflow_service = injector.get(WorkflowService)

            # Fetch the workflow by ID
            workflow = await workflow_service.get_by_id(workflow_id)

            if not workflow:
                error_msg = f"Workflow with id {workflow_id} not found"
                logger.error(error_msg)
                return {"error": error_msg, "status": "error"}

            # Build workflow configuration
            workflow_config = {
                "id": str(workflow.id),
                "name": workflow.name,
                "nodes": workflow.nodes,
                "edges": workflow.edges,
            }

            # Import WorkflowEngine here to avoid circular import
            from app.modules.workflow.engine.workflow_engine import WorkflowEngine

            # Create workflow engine instance
            workflow_engine = WorkflowEngine(workflow_config)

            # Execute the workflow with provided parameters
            state = await workflow_engine.execute_from_node(
                input_data=params,
                thread_id=thread_id,
                persist=False  # Don't persist nested workflow executions
            )

            # Format and return the response
            result = state.format_state_as_response()

            logger.info(
                f"Workflow executor node executed workflow {workflow_id} successfully"
            )

            return {
                "status": "success",
                "workflow_id": str(workflow_id),
                "workflow_name": workflow.name,
                "result": result,
                "output": state.output,
            }

        except Exception as e:
            error_msg = f"Error executing workflow {workflow_id_str}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                "error": error_msg,
                "status": "error",
                "workflow_id": str(workflow_id_str) if workflow_id_str else None,
            }
