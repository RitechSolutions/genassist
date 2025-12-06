from typing import List, Dict, Any, Optional
import logging
from langchain_core.language_models import BaseChatModel
from langchain_core.messages.base import BaseMessage
from langchain_core.tools import StructuredTool
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.prebuilt import create_react_agent
from app.modules.workflow.agents.base_tool import BaseTool
from app.modules.workflow.agents.base_tool_agent import BaseToolAgent
from app.modules.workflow.agents.agent_utils import (
    create_error_response,
    create_success_response,
)


logger = logging.getLogger(__name__)


class ReActAgentLC(BaseToolAgent):
    """ReAct Agent implementation using LangGraph's prebuilt React agent"""

    def __init__(
        self,
        llm_model: BaseChatModel,
        system_prompt: str,
        tools: List[BaseTool],
        verbose: bool = False,
        max_iterations: int = 5
    ):
        """Initialize a LangGraph ReAct agent

        Args:
            llm_model: The language model to use for reasoning and decision making
            system_prompt: System prompt that defines the agent's behavior and role
            tools: List of tools the agent can use to take actions
            verbose: Whether to enable verbose logging of reasoning cycles
            max_iterations: Maximum number of reasoning/action cycles
        """
        super().__init__(llm_model, system_prompt, tools,
                         verbose=verbose, max_iterations=max_iterations)

        # Convert BaseTool instances to LangChain StructuredTool instances
        self.lc_tools = self._convert_tools_to_langchain(self.tools)

        # Create LangGraph React agent
        self.agent_executor = self._create_langgraph_agent()

        logger.info(
            f"ReActAgentLC initialized with {len(self.tools)} tools using LangGraph")

    def _convert_tools_to_langchain(self, tools: List[BaseTool]) -> List[StructuredTool]:
        """Convert BaseTool instances to LangChain StructuredTool instances"""
        lc_tools = []

        for tool in tools:
            # Create a wrapper function that handles the BaseTool interface
            # Use default parameter to capture the tool reference in closure
            def create_tool_wrapper(original_tool: BaseTool):
                async def tool_wrapper(**kwargs):
                    try:
                        result = await original_tool.invoke(**kwargs)
                        return result
                    except Exception as e:
                        logger.error(
                            f"Error executing tool {original_tool.name}: {str(e)}")
                        return f"Error executing tool {original_tool.name}: {str(e)}"
                return tool_wrapper

            # Create LangChain StructuredTool - use func instead of coroutine since our tools are sync
            lc_tool = StructuredTool.from_function(
                coroutine=create_tool_wrapper(tool),
                name=tool.name,
                description=tool.description,
                # Use the tool's parameters if available, otherwise empty schema
                args_schema=self._create_tool_schema(tool),
                # Pass through return_direct setting
                return_direct=getattr(tool, 'return_direct', False)
            )
            lc_tools.append(lc_tool)

        return lc_tools

    def _create_tool_schema(self, tool: BaseTool):
        """Create a Pydantic schema for the tool parameters"""
        from pydantic import Field, create_model

        # If the tool has parameters, create a dynamic Pydantic model
        if hasattr(tool, 'parameters') and tool.parameters:
            fields = {}
            for param_name, param_info in tool.parameters.items():
                # Extract parameter info
                param_type = param_info.get('type', 'string')
                param_description = param_info.get(
                    'description', f'Parameter {param_name}')
                param_default = param_info.get('defaultValue', None)
                required = param_info.get('required', False)

                # Map parameter types to Python types
                if param_type == 'string':
                    field_type = str
                elif param_type == 'integer':
                    field_type = int
                elif param_type == 'number':
                    field_type = float
                elif param_type == 'boolean':
                    field_type = bool
                else:
                    field_type = str  # Default to string

                # Create field definition for create_model
                if required:
                    fields[param_name] = (field_type, Field(
                        default=param_default, description=param_description))
                else:
                    fields[param_name] = (Optional[field_type], Field(
                        default=param_default, description=param_description))

            # Use create_model for Pydantic v2 compatibility
            schema_class = create_model(f"{tool.name.title()}Schema", **fields)
            return schema_class

        # Return None if no parameters (LangChain will handle this)
        return None

    def _create_langgraph_agent(self):
        """Create the LangGraph React agent executor"""
        # Create the agent with system prompt
        agent_executor = create_react_agent(
            model=self.llm_model,
            tools=self.lc_tools,
        )

        return agent_executor

    def _convert_chat_history_to_messages(self, chat_history: List[Dict[str, str]]):
        """Convert chat history to LangChain message format"""
        messages: List[BaseMessage] = []
        for message in chat_history:
            role = message.get('role', 'user')
            content = message.get('content', '')

            if role == 'user':
                messages.append(HumanMessage(content=content))
            elif role == 'agent':
                messages.append(AIMessage(content=content))

        return messages

    async def invoke(self, query: str, chat_history: Optional[List] = None, **kwargs) -> Dict[str, Any]:
        """Execute a query using the LangGraph ReAct agent"""
        chat_history = chat_history or []
        thread_id = kwargs.get("thread_id", "default")

        try:
            # Prepare the input for LangGraph
            # Add system prompt as the first message if it exists
            messages: List[BaseMessage] = []
            if self.system_prompt:
                messages.append(SystemMessage(content=self.system_prompt))

            # Add chat history if available
            if chat_history:
                history_messages = self._convert_chat_history_to_messages(
                    chat_history)
                messages.extend(history_messages)

            # Add the current query
            messages.append(HumanMessage(content=query))

            input_data = {"messages": messages}

            # Configure the execution
            # config = {"configurable": {"thread_id": thread_id}}

            # Track reasoning steps and tools used
            reasoning_steps = []
            tools_used = []

            # Execute the agent
            if self.verbose:
                logger.info(
                    f"Executing LangGraph ReAct agent with query: {query}")

            # Execute the agent and get the final result
            result = await self.agent_executor.ainvoke(input_data)

            if self.verbose:
                logger.info(f"LangGraph agent result: {result}")

            # Extract final response from the result
            final_response = None
            if "messages" in result and result["messages"]:
                # Get the last AI message as the final response
                for message in reversed(result["messages"]):
                    if hasattr(message, 'content') and message.content:
                        # Skip empty messages or tool call messages
                        if not hasattr(message, 'tool_calls') or not message.tool_calls:
                            final_response = message.content
                            break

            # For debugging, also extract intermediate steps from the result
            if "messages" in result:
                for message in result["messages"]:
                    if hasattr(message, 'content') and message.content:
                        if hasattr(message, 'tool_calls') and message.tool_calls:
                            # This is a tool calling message
                            for tool_call in message.tool_calls:
                                tools_used.append({
                                    "tool_name": tool_call.get("name", "unknown"),
                                    "args": tool_call.get("args", {}),
                                    "iteration": len(tools_used) + 1
                                })
                        elif not hasattr(message, 'tool_calls'):
                            # This is a reasoning step
                            reasoning_steps.append({
                                "iteration": len(reasoning_steps) + 1,
                                "thought": message.content,
                                "full_response": message.content
                            })

            # Extract final answer
            if final_response:

                return create_success_response(
                    final_response,
                    self._get_agent_name(),
                    iterations=len(reasoning_steps),
                    reasoning_steps=reasoning_steps,
                    tools_used=tools_used,
                    thread_id=thread_id
                )
            else:
                return create_error_response(
                    "No response generated by LangGraph agent",
                    self._get_agent_name(),
                    thread_id=thread_id
                )

        except Exception as e:
            logger.error(f"Error executing ReActAgentLC query: {str(e)}")
            return create_error_response(
                str(e),
                self._get_agent_name(),
                thread_id=thread_id
            )

    async def stream(self, query: str, chat_history: Optional[List] = None, **kwargs):
        """Stream the agent's reasoning and action process"""
        chat_history = chat_history or []
        thread_id = kwargs.get("thread_id", "default")

        try:
            # Prepare the input for LangGraph
            # Add system prompt as the first message if it exists
            messages: List[BaseMessage] = []
            if self.system_prompt:
                messages.append(SystemMessage(content=self.system_prompt))

            # Add chat history if available
            if chat_history:
                history_messages = self._convert_chat_history_to_messages(
                    chat_history)
                messages.extend(history_messages)

            # Add the current query
            messages.append(HumanMessage(content=query))

            input_data = {"messages": messages}

            # Configure the execution
            config = {"configurable": {"thread_id": thread_id}}

            # Stream the agent execution
            reasoning_steps = []
            tools_used = []
            iteration_count = 0

            async for chunk in self.agent_executor.astream(input_data, config):
                # Process each chunk and yield intermediate results
                for node_name, node_data in chunk.items():
                    if node_name == "agent":
                        # Agent reasoning step
                        messages = node_data.get("messages", [])
                        if messages:
                            last_message = messages[-1]
                            if hasattr(last_message, 'content'):
                                step = {
                                    "iteration": iteration_count + 1,
                                    "thought": last_message.content,
                                    "full_response": last_message.content
                                }
                                reasoning_steps.append(step)
                                iteration_count += 1

                                # Yield intermediate step
                                yield {
                                    "type": "reasoning_step",
                                    "data": step,
                                    "agent": self._get_agent_name()
                                }

                    elif node_name == "tools":
                        # Tool execution step
                        messages = node_data.get("messages", [])
                        if messages:
                            for msg in messages:
                                if hasattr(msg, 'name') and hasattr(msg, 'content'):
                                    tool_step = {
                                        "tool_name": msg.name,
                                        "result": msg.content,
                                        "iteration": iteration_count
                                    }
                                    tools_used.append(tool_step)

                                    # Yield tool execution
                                    yield {
                                        "type": "tool_execution",
                                        "data": tool_step,
                                        "agent": self._get_agent_name()
                                    }

            # Yield final result
            final_result = await self.invoke(query, chat_history, **kwargs)
            yield {
                "type": "final_result",
                "data": final_result,
                "agent": self._get_agent_name()
            }

        except Exception as e:
            logger.error(f"Error streaming ReActAgentLC query: {str(e)}")
            yield {
                "type": "error",
                "data": create_error_response(str(e), self._get_agent_name(), thread_id=thread_id),
                "agent": self._get_agent_name()
            }

    # ==================== TOOL MANAGEMENT ====================
    # Tool management methods are inherited from BaseToolAgent

    def add_tool(self, tool: BaseTool):
        """Add a new tool to the agent and recreate the LangGraph agent"""
        super().add_tool(tool)
        # Convert new tools and recreate agent
        self.lc_tools = self._convert_tools_to_langchain(self.tools)
        self.agent_executor = self._create_langgraph_agent()

    def remove_tool(self, tool_name: str) -> bool:
        """Remove a tool from the agent and recreate the LangGraph agent"""
        success = super().remove_tool(tool_name)
        if success:
            # Convert remaining tools and recreate agent
            self.lc_tools = self._convert_tools_to_langchain(self.tools)
            self.agent_executor = self._create_langgraph_agent()
        return success
