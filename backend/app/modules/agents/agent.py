from typing import Dict, Any, List
from langchain_core.messages import HumanMessage
from langchain.chat_models import init_chat_model
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
import os
import logging

from app.core.utils.encryption_utils import decrypt_key
from app.db.models import AgentModel
from app.modules.agents.llm.provider import LLMProvider
from app.modules.agents.tools import DynamicToolGenerator
from app.schemas.agent_tool import ToolConfigRead
from app.schemas.llm import LlmProviderRead


logger = logging.getLogger(__name__)

class Agent:
    """Base class for a configurable agent"""


    def __init__(self, agent_id: str, agent_model: AgentModel, memory: MemorySaver,
                 tool_configs: List[ToolConfigRead] = None):
        """Initialize a configurable agent
        
        Args:
            agent_id: Unique identifier for the agent
            agent_model: Configuration for the agent
            memory: MemorySaver instance for storing agent state
            tool_configs: List of tool configurations
            tool_implementation: Implementation to execute tools
        """
        self.agent_id = agent_id
        self.agent_model = agent_model
        self.memory = memory
        self.tool_configs = tool_configs or []
        self.agent = None
        self.tool_implementation = None
        self._initialize()
    
    def _initialize(self) -> Dict[str, Any]:
        """Initialize the agent based on its configuration"""
        try:
            # Initialize the agent based on the provider
            
            # # Create the LLM based on the provider
            # if llm_provider == "openai":
            #     os.environ["OPENAI_API_KEY"] = decrypt_key(llm_provider_read.connection_data['api_key'])
                
            model = LLMProvider.get_instance().get_model("")
            model_config = LLMProvider.get_instance().get_configuration("")
            logger.error(f"Model config: {model_config.llm_model_provider}, {model_config.llm_model}")
            logger.error(f"Model: {model}")

            tools = DynamicToolGenerator.generate_tools_from_configs(self.tool_configs)

            model.bind_tools(tools)
           
            user_system_prompt = self.agent_model.system_prompt
            
            # Base system prompt
            system_prompt_parts = [
                "You are an AI assistant designed to be helpful, harmless, and honest.",
                f"Your primary role: {user_system_prompt}"
            ]
            
            # Add knowledge base instructions if knowledge base IDs are provided
            if self.agent_model.agent_knowledge_bases:
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
                "provider": model_config.llm_model_provider,
                "model": model_config.llm_model   
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
            logger.error(f"Running query: {query}")
            
            enhanced_query = query
            rag_used = False

            if knowledge_search_results is not None and len(knowledge_search_results) > 0:
                knowledge_search_results = knowledge_search_results[:1000]
            
            # Add knowledge context if provided
            if knowledge_search_results:
                enhanced_query = f"I need information about: {query}\n\nHere's some context that might help:\n{knowledge_search_results}\n\nPlease use this context to provide a comprehensive answer."
                rag_used = True
                
            logger.info("run_query : enhanced_query")
            logger.info(enhanced_query)
            logger.error(f"Thread ID: {thread_id}")
            logger.error(f"enhanced_query: {enhanced_query}")
            try:      
                
                # Run the query through the agent
                response = self.agent.invoke(
                    {"messages": [HumanMessage(content=enhanced_query)]},
                    {"configurable": {"thread_id": thread_id}}
                )
                logger.error(f"Response: {response}")
                
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


    def run_query_llm(self, query: str) -> Dict[str, Any]:
        """Run a query against the agent without any context

        Args:
            query: User's query
        """
        try:
            logger.info(query)

            try:
                # Run the query through the agent
                response = self.agent.invoke(
                        {"messages": [HumanMessage(content=query)]}
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
                "agent_id": self.agent_id
                }
        except Exception as e:
            logger.error(f"Error running query: {str(e)}")
            return {
                "status": "error",
                "message": f"Error running query: {str(e)}"
                }
