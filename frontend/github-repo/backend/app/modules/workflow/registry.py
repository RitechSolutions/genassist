"""Registry for managing initialized agents"""

import asyncio
import logging
from typing import Any, Optional
from injector import inject
from app.db.models import AgentModel
from app.repositories.agent import AgentRepository
from app.db.multi_tenant_session import multi_tenant_manager
from app.core.tenant_scope import get_tenant_context


logger = logging.getLogger(__name__)


class RegistryItem:
    """Item in the registry"""

    def __init__(self, agent_model: AgentModel):
        self.agent_model = agent_model
        self.workflow_model = agent_model.workflow.to_dict()
        from app.modules.workflow.engine.workflow_engine import WorkflowEngine

        self.workflow_engine = WorkflowEngine.get_instance()
        self.workflow_engine.build_workflow(self.workflow_model)

        logger.info(f"Workflow model: {self.workflow_model}")

    async def execute(self, session_message: str, metadata: dict) -> dict:
        """Execute a workflow"""
        thread_id = metadata.get("thread_id", None)
        state = await self.workflow_engine.execute_from_node(
            self.workflow_model["id"],
            input_data={"message": session_message, **metadata},
            thread_id=thread_id,
        )
        return state.format_state_as_response()


@inject
class AgentRegistry:
    """Tenant-aware singleton registry for managing initialized agents.

    Each tenant gets their own registry instance with isolated agents.
    This ensures agent configurations, workflows, and state remain tenant-specific.
    """

    def __init__(self):
        self.initialized_agents: dict[str, Any] = {}
        # Keep reference for synchronous, in-request usage only. Do NOT use this in background tasks.
        logger.info("AgentRegistry initialized")
        #asyncio.create_task(self._initialize())

    async def initialize(self):
        """Initialize the registry using a fresh tenant-aware AsyncSession.

        This avoids reusing the request-scoped session during background initialization,
        preventing concurrent operations during request teardown.
        """
        try:
            tenant_id = get_tenant_context()
            session_factory = (
                multi_tenant_manager.get_tenant_session_factory(tenant_id)
                if tenant_id
                else multi_tenant_manager.get_tenant_session_factory()
            )

            async with session_factory() as session:
                temp_repo = AgentRepository(session)
                agents: list[AgentModel] = await temp_repo.get_all_full()

            for agent in agents:
                if agent.is_active:
                    if not self.is_agent_initialized(str(agent.id)):
                        self.register_agent(str(agent.id), agent)
                        logger.info(f"Agent {agent.id} registered")
                    else:
                        logger.info(f"Agent {agent.id}, {agent.name} already registered")
                else:
                    logger.info(f"Agent {agent.id}, {agent.name} skipped as it is not active")
        except Exception as e:
            logger.error(f"Error initializing agent registry: {str(e)}")
            # Don't re-raise in background task to avoid unhandled exception noise

    def register_agent(self, agent_id: str, agent_model: AgentModel) -> RegistryItem:
        """Register an agent in the registry"""
        self.initialized_agents[agent_id] = RegistryItem(agent_model)
        logger.info(f"Agent {agent_id} registered")
        return self.initialized_agents[agent_id]

    def get_agent(self, agent_id: str) -> Optional[RegistryItem]:
        """Get an agent from the registry"""
        return self.initialized_agents.get(agent_id)

    async def execute_workflow(
        self, agent_id: str, session_message: str, metadata: dict
    ) -> dict:
        """Execute a workflow"""
        agent = self.get_agent(agent_id)
        if agent is None:
            raise KeyError(f"Agent {agent_id} is not initialized")
        return await agent.execute(session_message, metadata)

    def is_agent_initialized(self, agent_id: str) -> bool:
        """Check if an agent is initialized"""
        return agent_id in self.initialized_agents

    def cleanup_agent(self, agent_id: str) -> bool:
        """Remove an agent from the registry"""
        if agent_id in self.initialized_agents:
            self.initialized_agents.pop(agent_id)
            logger.info(f"Agent {agent_id} cleaned up")
            return True
        return False

    def cleanup_all(self) -> None:
        """Clean up all agents"""
        self.initialized_agents = {}
        logger.info("All agents cleaned up")
