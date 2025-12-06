from langchain_core.language_models import BaseChatModel
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import logging

from app.modules.workflow.agents.base_tool import BaseTool
from app.modules.workflow.agents.memory import ConversationMemory
from app.modules.workflow.agents.agent_utils import (
    validate_tool_parameters,
    create_error_response,
    create_success_response,
    handle_parameter_validation_error,
    handle_tool_execution_error,
    get_available_tools_info,
    get_tool_schemas,
    get_tool_parameter_info,
    add_tool_to_agent,
    remove_tool_from_agent,
)

logger = logging.getLogger(__name__)


class BaseToolAgent(ABC):
    """Abstract base class for all tool-based agents providing common functionality"""

    def __init__(
        self,
        llm_model: BaseChatModel,
        system_prompt: str,
        tools: Optional[List[BaseTool]] = None,
        memory: Optional[ConversationMemory] = None,
        verbose: bool = False,
        max_iterations: int = 5
    ):
        """Initialize base tool agent with common parameters

        Args:
            llm_model: The language model to use for reasoning and decision making
            system_prompt: System prompt that defines the agent's behavior and role
            tools: List of tools the agent can use (optional, defaults to empty list)
            memory: Optional memory for conversation state management
            verbose: Whether to enable verbose logging
            max_iterations: Maximum number of reasoning/action cycles
        """
        self.llm_model = llm_model
        self.system_prompt = system_prompt
        self.tools = tools if tools is not None else []
        self.memory = memory
        self.verbose = verbose
        self.max_iterations = max_iterations
        self.tool_map = {tool.name: tool for tool in self.tools}

        agent_name = self.__class__.__name__
        logger.info(f"{agent_name} initialized with {len(self.tools)} tools")

    # ==================== ABSTRACT METHODS ====================

    @abstractmethod
    async def invoke(self, query: str, chat_history: Optional[List] = None, **kwargs) -> Dict[str, Any]:
        """Execute a query using the agent's specific implementation"""
        pass

    @abstractmethod
    async def stream(self, query: str, chat_history: Optional[List] = None, **kwargs):
        """Stream the agent's execution process"""
        pass

    # ==================== TOOL EXECUTION ====================

    async def execute_tool_by_name(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """Execute a specific tool by name with provided arguments and parameter validation"""
        agent_name = self.__class__.__name__
        try:
            if tool_name not in self.tool_map:
                return create_error_response(
                    f"Tool '{tool_name}' not found",
                    agent_name,
                    available_tools=list(self.tool_map.keys())
                )

            tool = self.tool_map[tool_name]

            try:
                validated_args = validate_tool_parameters(tool, kwargs)
            except ValueError as e:
                return handle_parameter_validation_error(
                    e, tool_name, tool, agent_name, provided_args=kwargs
                )

            result = await tool.invoke(**validated_args)

            # Check if tool has return_direct=True
            response_data = {
                "tool_name": tool_name,
                "validated_args": validated_args
            }
            if hasattr(tool, 'return_direct') and tool.return_direct:
                response_data["return_direct"] = True

            return create_success_response(
                str(result),
                agent_name,
                **response_data
            )

        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {str(e)}")
            return handle_tool_execution_error(e, tool_name, agent_name)

    # ==================== TOOL MANAGEMENT ====================

    def add_tool(self, tool: BaseTool):
        """Add a new tool to the agent"""
        add_tool_to_agent(self.tools, self.tool_map, tool)

    def remove_tool(self, tool_name: str) -> bool:
        """Remove a tool from the agent"""
        return remove_tool_from_agent(self.tools, self.tool_map, tool_name)

    def get_available_tools(self) -> List[Dict[str, str]]:
        """Get list of available tools with their descriptions and parameter info"""
        return get_available_tools_info(self.tools)

    def get_tool_schemas(self) -> Dict[str, Dict]:
        """Get comprehensive schemas for all available tools including parameters"""
        return get_tool_schemas(self.tools)

    def get_tool_parameter_info(self, tool_name: str) -> Dict[str, Any]:
        """Get detailed parameter information for a specific tool"""
        return get_tool_parameter_info(self.tool_map, tool_name)

    # ==================== UTILITY METHODS ====================

    def _get_agent_name(self) -> str:
        """Get the agent's class name for logging and responses"""
        return self.__class__.__name__

    def _extract_response_content(self, response) -> str:
        """Extract content from LLM response object"""
        return response.content if hasattr(response, 'content') else str(response)

    def _log_if_verbose(self, message: str):
        """Log message if verbose mode is enabled"""
        if self.verbose:
            logger.info(message)
