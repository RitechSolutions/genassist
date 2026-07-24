"""Registry for managing initialized agents"""

import logging
from typing import Union

from app.db.models import AgentModel
from app.modules.workflow.agents.sub_agents.turn_router import SubAgentTurnRouter
from app.schemas.agent import AgentRead

logger = logging.getLogger(__name__)


class RegistryItem:
    """Item in the registry"""

    def __init__(self, agent: Union[AgentModel, AgentRead]):
        if isinstance(agent, AgentRead):
            self.agent_id = str(agent.id)
            self.agent_name = agent.name
            self.workflow_model = agent.workflow
        else:
            self.agent_id = str(agent.id)
            self.agent_name = agent.name
            self.workflow_model = agent.workflow.to_dict() if agent.workflow else None

        from app.modules.workflow.engine.workflow_engine import WorkflowEngine

        # Only create workflow engine if workflow exists
        if self.workflow_model is not None:
            self.workflow_engine = WorkflowEngine(self.workflow_model)
            self._router = SubAgentTurnRouter(self.workflow_engine, owner_id=self.agent_id)
            logger.debug(f"Workflow model: {self.workflow_model}")
        else:
            self.workflow_engine = None
            self._router = None
            logger.warning(f"Agent {self.agent_name} ({self.agent_id}) has no workflow assigned")

    async def execute(self, session_message: str, metadata: dict, persist: bool = True) -> dict:
        """Execute a workflow, optionally resuming from a specific node"""
        if self.workflow_engine is None:
            raise ValueError(
                f"Cannot execute workflow for agent {self.agent_name} ({self.agent_id}): "
                f"No workflow is assigned to this agent"
            )

        thread_id = metadata.get("thread_id", None)
        start_node_id = metadata.get("human_in_the_loop_node_id")

        input_data = {"message": session_message, **metadata}

        # Sub-agent delegation only kicks in for workflows that have sub-agents; a
        # HITL resume (client-driven) always takes precedence over frame routing
        if self._router.has_sub_agents():
            input_data["agent_id"] = self.agent_id
            if not start_node_id and thread_id:
                routed = await self._router.route_turn(session_message, thread_id, input_data, persist)
                if routed is not None:
                    return routed

        state = await self.workflow_engine.execute_from_node(
            start_node_id=start_node_id,
            input_data=input_data,
            thread_id=thread_id,
            persist=persist,
            registry_managed=True,
        )
        return self._router.finalize(state.format_state_as_response())
