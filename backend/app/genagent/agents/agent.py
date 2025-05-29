from typing import Dict, Any, List
from langchain_core.messages import HumanMessage
from langchain.chat_models import init_chat_model
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
import os
import logging
from app.genagent.models.config import AgentConfig
from app.genagent.models.tool import ToolConfig
from app.genagent.agents.tools import DynamicToolGenerator

logger = logging.getLogger(__name__)

class Agent:
    """Base class for a configurable agent"""
    
    def __init__(self, agent_id: str, config: AgentConfig, memory: MemorySaver, 
                 tool_configs: List[ToolConfig] = None):
        """Initialize a configurable agent
        
        Args:
            agent_id: Unique identifier for the agent
            config: Configuration for the agent
            memory: MemorySaver instance for storing agent state
            tool_configs: List of tool configurations
            tool_implementation: Implementation to execute tools
        """
        self.agent_id = agent_id
        self.config = config
        self.memory = memory
        self.tool_configs = tool_configs or []
        self.agent = None

        self._initialize()
    
    def _initialize(self) -> Dict[str, Any]:
        """Initialize the agent based on its configuration"""
        try:
            # Initialize the agent based on the provider
            llm_provider = self.config.provider.lower()
            llm_model = self.config.model
            
            # Create the LLM based on the provider
            if llm_provider == "openai":
                os.environ["OPENAI_API_KEY"] = self.config.api_key
                
            model = init_chat_model(
                model_provider=llm_provider,
                model=llm_model,
                temperature=0.7
            )
            
            tools = DynamicToolGenerator.generate_tools_from_configs(self.tool_configs)

            model.bind_tools(tools)
           
            user_system_prompt = self.config.system_prompt
            
            # Base system prompt
            system_prompt_parts = [
                "You are an AI assistant designed to be helpful, harmless, and honest.",
                f"Your primary role: {user_system_prompt}"
            ]
            
            # Add knowledge base instructions if knowledge base IDs are provided
            if self.config.knowledge_base_ids:
                system_prompt_parts.extend([
                    "",
                    "IMPORTANT KNOWLEDGE BASE INSTRUCTIONS:",
                    "- ONLY provide information that is explicitly available in the knowledge base",
                    "- If the information is not in the knowledge base, CLEARLY state that",
                    "- DO NOT make up or infer information",
                    "- DO NOT use your general knowledge unless confirmed by the knowledge base"
                ])
            
            # Add tools instructions if tool configs are provided
            if self.tool_configs:
                system_prompt_parts.extend([
                    "",
                    "IMPORTANT TOOLS INSTRUCTIONS:",
                    "- You have access to external tools that can help you answer questions",
                    "- Use these tools when appropriate to gather information",
                    "- Format tool parameters as valid JSON"
                ])
            
            # Combine all parts
            system_prompt = "\n".join(system_prompt_parts)
                            
            # Create the agent
            self.agent = create_react_agent(
                model,
                tools,
                prompt=system_prompt,
                checkpointer=self.memory,
            )
            
            # Return initialization status
            return {
                "status": "initialized", 
                "agent_id": self.agent_id,
                "provider": llm_provider,
                "model": llm_model   
            }
            
        except Exception as e:
            logger.error(f"Error initializing agent: {str(e)}")
            return {"status": "error", "message": str(e)}
                
    
    def run_query(self, thread_id: str, query: str, knowledge_search_results: str = None) -> Dict[str, Any]:
        """Run a query against the agent with optional knowledge context
        
        Args:
            thread_id: ID of the conversation thread
            query: User's query
            knowledge_search_results: Optional pre-fetched knowledge base search results
        """
        try:
            enhanced_query = query
            rag_used = False
            
            # Add knowledge context if provided
            if knowledge_search_results:
                enhanced_query = f"I need information about: {query}\n\nHere's some context that might help:\n{knowledge_search_results}\n\nPlease use this context to provide a comprehensive answer."
                rag_used = True
                
            logger.info("run_query : enhanced_query")
            logger.info(enhanced_query)
            
            try:      
                # Run the query through the agent
                response = self.agent.invoke(
                    {"messages": [HumanMessage(content=enhanced_query)]},
                    {"configurable": {"thread_id": thread_id}}
                )
                
                last_message = response["messages"][-1].content
            except Exception as e:
                logger.error(f"Agent failed to run query: {str(e)}")
                return {
                    "status": "error",
                    "response": f"Agent failed to run query: {str(e)}"
                }
            
            return {
                "status": "success",
                "response": last_message,
                "agent_id": self.agent_id,
                "thread_id": thread_id,
                "rag_used": rag_used
            }
        except Exception as e:
            logger.error(f"Error running query: {str(e)}")
            return {
                "status": "error",
                "message": f"Error running query: {str(e)}"
            }
