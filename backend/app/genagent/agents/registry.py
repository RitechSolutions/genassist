from typing import Dict, Any, List, Optional
from langgraph.checkpoint.memory import MemorySaver
from app.genagent.agents.agent import Agent
import logging
from app.genagent.models.config import AgentConfig
from app.genagent.models.tool import ToolConfig

logger = logging.getLogger(__name__)

class AgentRegistry:
    """Registry for managing initialized agents"""
    
    _instance = None
    
    @staticmethod
    def get_instance() -> 'AgentRegistry':
        
        if AgentRegistry._instance is None:
            AgentRegistry._instance = AgentRegistry()
            logger.info("AgentRegistry initialized")
        return AgentRegistry._instance
    
    
    def __init__(self, memory: MemorySaver = MemorySaver()):
        self.initialized_agents = {}
        self.memory = memory
        logger.info("AgentRegistry initialized")

    
    def register_agent(self, agent_id: str, config: AgentConfig, tools_config: List[ToolConfig]) -> None:
        """Register an agent in the registry"""
        # Create the agent
        agent = Agent(
            agent_id=agent_id,
            config=config,
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

