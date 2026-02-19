"""Registry for managing initialized agents"""

import logging
from typing import Union

from app.db.models import AgentModel
from app.schemas.agent import AgentRead


logger = logging.getLogger(__name__)


class RegistryItem:
    """
    Item in the registry.

    Accepts either AgentModel (SQLAlchemy) or AgentRead (Pydantic).
    AgentRead is preferred for better performance (already has workflow dict).
    """

    def __init__(self, agent: Union[AgentModel, AgentRead]):
        # Handle both SQLAlchemy and Pydantic models
        if isinstance(agent, AgentRead):
            # Pydantic model - workflow dict is already present
            self.agent_id = str(agent.id)
            self.agent_name = agent.name
            self.workflow_model = agent.workflow
        else:
            # SQLAlchemy model - extract workflow dict
            self.agent_id = str(agent.id)
            self.agent_name = agent.name
            self.workflow_model = agent.workflow.to_dict() if agent.workflow else None

        from app.modules.workflow.engine.workflow_engine import WorkflowEngine

        # Only create workflow engine if workflow exists
        if self.workflow_model is not None:
            self.workflow_engine = WorkflowEngine(self.workflow_model)
            logger.debug(f"Workflow model: {self.workflow_model}")
        else:
            self.workflow_engine = None
            logger.warning(f"Agent {self.agent_name} ({self.agent_id}) has no workflow assigned")

    async def execute(self, session_message: str, metadata: dict) -> dict:
        """Execute a workflow, or resume a paused one if user_input_from_form is present."""
        if self.workflow_engine is None:
            raise ValueError(
                f"Cannot execute workflow for agent {self.agent_name} ({self.agent_id}): "
                f"No workflow is assigned to this agent"
            )

        thread_id = metadata.get("thread_id", None)
        user_input_from_form = metadata.get("user_input_from_form")

        if user_input_from_form and thread_id:
            # Resume a paused workflow with user-provided form data
            state = await self.workflow_engine.resume_from_pause(
                thread_id=thread_id,
                user_input_data=user_input_from_form,
            )
        else:
            # Normal execution
            input_data = {
                "message": session_message,
                **metadata,
            }

            state = await self.workflow_engine.execute_from_node(
                input_data=input_data,
                thread_id=thread_id,
            )

        # Return a special response when workflow is paused for user input
        if state.status == "paused":
            return {
                "status": "awaiting_input",
                "form_schema": state.paused_form_schema,
                "node_id": state.paused_node_id,
            }

        return state.format_state_as_response()