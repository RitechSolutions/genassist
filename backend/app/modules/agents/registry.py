import asyncio
import logging
from typing import Optional
from langgraph.checkpoint.memory import MemorySaver
from app.db.models import AgentModel
from app.db.session import get_db
from app.modules.agents.workflow.builder import WorkflowBuilder
from app.repositories.agent import AgentRepository


logger = logging.getLogger(__name__)

class RegistryItem:
    """Item in the registry"""
    def __init__(self, agent_model: AgentModel):
        self.agent_model = agent_model
        self.workflow_model = agent_model.workflow
        logger.info(f"Workflow model: {self.workflow_model.__dict__}")
        self.executor = WorkflowBuilder(workflow_model=agent_model.workflow)

class AgentRegistry:
    """Registry for managing initialized agents"""
    
    _instance = None

    @staticmethod
    def get_instance() -> 'AgentRegistry':
        
        if AgentRegistry._instance is None:
            AgentRegistry._instance = AgentRegistry()
        return AgentRegistry._instance


    def __init__(self, memory: MemorySaver = MemorySaver()):
        self.initialized_agents = {}
        self.memory = memory
        logger.info("AgentRegistry initialized")
        asyncio.create_task(self._initialize())

        
    async def _initialize(self):
        """Initialize the registry"""
        async for db in get_db():
            agent_repository = AgentRepository(db)
            agents: list[AgentModel] = await agent_repository.get_all_full()
            for agent in agents:
                if agent.is_active:
                    self.register_agent(str(agent.id), agent)
                    logger.info(f"Agent {agent.id} registered")
                


    def register_agent(self, agent_id: str, agent_model: AgentModel) -> RegistryItem:
        """Register an agent in the registry"""
        self.initialized_agents[agent_id] = RegistryItem(agent_model)
        logger.info(f"Agent {agent_id} registered")
        return self.initialized_agents[agent_id]
    

    def get_agent(self, agent_id: str) -> Optional[RegistryItem]:
        """Get an agent from the registry"""
        return self.initialized_agents.get(agent_id)
    
    def execute_workflow(self, agent_id: str, user_query: str, metadata: dict) -> dict:
        """Execute a workflow"""
        agent = self.get_agent(agent_id)
        return agent.executor.execute(user_query, metadata)
    
    
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

