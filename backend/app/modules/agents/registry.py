import asyncio
import logging
from typing import List, Optional
from langgraph.checkpoint.memory import MemorySaver
from app.db.models import AgentModel
from app.db.session import get_db
from app.modules.agents.agent import Agent
from app.repositories.agent import AgentRepository
from app.repositories.tool import ToolRepository
from app.schemas.agent import AgentRead
from app.schemas.agent_tool import ToolConfigRead


logger = logging.getLogger(__name__)

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
            tool_repository = ToolRepository(db)
            agents: list[AgentModel] = await agent_repository.get_all_full()
            for agent in agents:
                if agent.is_active:
                    tools = await tool_repository.get_by_ids([tool.id for tool in agent.agent_tools])
                    self.register_agent(str(agent.id), agent,
                                        [ToolConfigRead.model_validate(tool) for tool in tools])
                    logger.info(f"Agent {agent.id} registered")
            logger.info("AgentRegistry initialized with active agents")


    def register_agent(self, agent_id: str, agent_model: AgentModel, tools_config: List[ToolConfigRead]) -> None:
        """Register an agent in the registry"""
        # Create the agent
        agent = Agent(
            agent_id=agent_id,
            agent_model=agent_model,
            memory=self.memory,
            tool_configs=tools_config,
        )
        self.initialized_agents[agent_id] = agent
        logger.info(f"Agent {agent_id} registered")
        return agent
    
    def get_agent(self, agent_id: str) -> Optional[Agent]:
        """Get an agent from the registry"""
        return self.initialized_agents.get(agent_id)
    
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

