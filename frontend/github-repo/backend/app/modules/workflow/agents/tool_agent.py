from typing import List, Dict, Any, Optional
import logging
import json
from langchain_core.language_models import BaseChatModel

from app.modules.workflow.agents.base_tool import BaseTool
from app.modules.workflow.agents.base_tool_agent import BaseToolAgent
from app.modules.workflow.agents.agent_utils import (
    validate_tool_parameters,
    format_tool_parameters,
    create_tool_descriptions,
    create_error_response,
    create_success_response,
    handle_parameter_validation_error,
    handle_tool_execution_error,
    parse_json_response,
    extract_direct_response
)
from app.modules.workflow.agents.agent_prompts import (
    create_tool_agent_tools_available_prompt,
    create_tool_agent_no_tools_prompt,
    create_tool_agent_no_tools_query_prompt,
    create_tool_agent_tools_query_prompt,
    create_tool_agent_iteration_continuation_prompt,
    create_tool_selection_prompt,
    create_conversation_context as build_conversation_context
)

logger = logging.getLogger(__name__)


class ToolAgent(BaseToolAgent):
    """Tool-focused agent that specializes in selecting and executing the right tools for tasks"""

    def __init__(
        self,
        llm_model: BaseChatModel,
        system_prompt: str,
        tools: List[BaseTool],
        verbose: bool = False,
        max_iterations: int = 6
    ):
        """Initialize a Tool agent

        Args:
            llm_model: The language model to use for tool selection and coordination
            system_prompt: System prompt that defines the agent's behavior and tool usage guidelines
            tools: List of tools the agent can use to accomplish tasks
            verbose: Whether to enable verbose logging of tool execution
            max_iterations: Maximum number of tool execution iterations
        """
        super().__init__(llm_model, system_prompt, tools,
                         verbose=verbose, max_iterations=max_iterations)

    # ==================== PROMPT GENERATION ====================

    def _create_enhanced_system_prompt(self) -> str:
        """Create an enhanced system prompt using centralized prompt templates"""
        if self.tools:
            tool_descriptions = create_tool_descriptions(self.tools)
            return create_tool_agent_tools_available_prompt(self.system_prompt, tool_descriptions)
        else:
            return create_tool_agent_no_tools_prompt(self.system_prompt)

    # ==================== RESPONSE PARSING ====================

    def _parse_tool_call(self, response: str) -> Optional[Dict[str, Any]]:
        """Parse tool call from LLM response with JSON format support"""
        # Try JSON parsing first
        json_result = self._parse_json_response(response)
        if json_result is not None:
            return json_result

        # Fall back to legacy text parsing
        return self._parse_legacy_response(response)

    def _parse_json_response(self, response: str) -> Optional[Dict[str, Any]]:
        """Parse JSON formatted response"""
        parsed_response = parse_json_response(response)
        if parsed_response:
            action = parsed_response.get("action")
            tool_name = parsed_response.get("tool_name")

            # Handle different action types that should be treated as tool calls
            if action in ["tool_call", "knowledge_base", "search", "query"] or tool_name or (action and action != "direct_response" and action.strip()):
                # For tool_call, use tool_name; for others, use the action as the tool name
                final_tool_name = tool_name or action
                return {
                    "tool": final_tool_name,
                    "args": parsed_response.get("parameters", {}),
                    "reasoning": parsed_response.get("reasoning", "")
                }
        return None

    def _parse_legacy_response(self, response: str) -> Optional[Dict[str, Any]]:
        """Parse legacy text format for backward compatibility"""
        lines = response.split('\n')

        for i, line in enumerate(lines):
            line = line.strip()
            if line.startswith('TOOL:') or line.startswith('Tool:'):
                tool_name = line.split(':', 1)[1].strip()
                args = self._extract_legacy_args(lines, i)
                return {"tool": tool_name, "args": args}

        return None

    def _extract_legacy_args(self, lines: List[str], start_index: int) -> Dict[str, Any]:
        """Extract arguments from legacy format"""
        args = {}
        for j in range(start_index + 1, min(start_index + 10, len(lines))):
            arg_line = lines[j].strip()
            if arg_line.startswith('ARGS:') or arg_line.startswith('Args:'):
                args_text = arg_line.split(':', 1)[1].strip()
                try:
                    args = json.loads(args_text)
                except json.JSONDecodeError:
                    if '=' in args_text:
                        args = self._parse_key_value_pairs(args_text)
                    else:
                        args = {"input": args_text}
                break
        return args

    def _parse_key_value_pairs(self, args_text: str) -> Dict[str, str]:
        """Parse key=value pairs from text"""
        args = {}
        pairs = args_text.split(',')
        for pair in pairs:
            if '=' in pair:
                key, value = pair.split('=', 1)
                args[key.strip()] = value.strip().strip('"').strip("'")
        return args

    # ==================== WORKFLOW EXECUTION ====================

    async def _execute_tools_workflow(self, query: str, chat_history: List[Dict[str, str]]) -> Dict[str, Any]:
        """Execute the tool-based workflow with enhanced parameter handling"""
        if not self.tools:
            return await self._handle_no_tools_workflow(query, chat_history)

        return await self._handle_tools_workflow(query, chat_history)

    async def _handle_no_tools_workflow(self, query: str, chat_history: List[Dict[str, str]]) -> Dict[str, Any]:
        """Handle workflow when no tools are available"""
        enhanced_prompt = self._create_enhanced_system_prompt()
        context = build_conversation_context(chat_history)
        prompt = create_tool_agent_no_tools_query_prompt(
            enhanced_prompt, context, query)

        try:
            response = await self.llm_model.ainvoke(
                [{"role": "user", "content": prompt}])
            response_content = response.content if hasattr(
                response, 'content') else str(response)
            logger.info(f"Response: {response}")
            direct_response = extract_direct_response(response_content)

            return create_success_response(
                direct_response or response_content,
                self._get_agent_name(),
                steps=[{"step": 1, "response": response_content,
                        "note": "Direct response - no tools available"}],
                tools_used=[],
                no_tools_available=True
            )
        except Exception as e:
            logger.error(f"Error generating direct response: {str(e)}")
            return create_error_response(
                f"Error generating response: {str(e)}",
                self._get_agent_name(),
                no_tools_available=True
            )

    async def _handle_tools_workflow(self, query: str, chat_history: List[Dict[str, str]]) -> Dict[str, Any]:
        """Handle workflow when tools are available"""
        enhanced_prompt = self._create_enhanced_system_prompt()
        context = build_conversation_context(chat_history)
        prompt = create_tool_agent_tools_query_prompt(
            enhanced_prompt, context, query)

        workflow_steps: List[Dict[str, Any]] = []
        tools_used: List[Dict[str, Any]] = []

        for iteration in range(self.max_iterations):
            try:
                result = await self._execute_workflow_iteration(
                    prompt, iteration, workflow_steps, tools_used
                )

                if result is not None:
                    return result

                # Update prompt for next iteration if needed
                if tools_used:
                    last_tool = tools_used[-1]
                    continuation_prompt = create_tool_agent_iteration_continuation_prompt(
                        last_tool['tool_name'],
                        last_tool['result']
                    )
                    prompt += continuation_prompt

            except Exception as e:
                logger.error(
                    f"Error in tool workflow iteration {iteration}: {str(e)}")
                return create_error_response(
                    f"Error in iteration {iteration}: {str(e)}",
                    self._get_agent_name(),
                    steps=workflow_steps
                )

        return create_error_response(
            f"Max iterations ({self.max_iterations}) reached",
            self._get_agent_name(),
            steps=workflow_steps,
            tools_used=tools_used
        )

    async def _execute_workflow_iteration(
        self,
        prompt: str,
        iteration: int,
        workflow_steps: List[Dict],
        tools_used: List[Dict]
    ) -> Optional[Dict[str, Any]]:
        """Execute a single workflow iteration"""
        response = await self.llm_model.ainvoke([{"role": "user", "content": prompt}])
        response_content = response.content if hasattr(
            response, 'content') else str(response)
        workflow_steps.append(
            {"step": iteration + 1, "response": response_content})

        if self.verbose:
            logger.info(
                f"Tool workflow step {iteration + 1}: {response_content}")

        tool_call = self._parse_tool_call(response_content)

        if not tool_call:
            # No tool needed, extract direct response
            direct_response = extract_direct_response(response_content)
            return create_success_response(
                direct_response or response_content,
                self._get_agent_name(),
                steps=workflow_steps,
                tools_used=tools_used
            )

        # Execute the tool
        return await self._execute_single_tool(tool_call, workflow_steps, tools_used, iteration)

    async def _execute_single_tool(
        self,
        tool_call: Dict[str, Any],
        workflow_steps: List[Dict],
        tools_used: List[Dict],
        iteration: int
    ) -> Optional[Dict[str, Any]]:
        """Execute a single tool and handle the result"""
        tool_name = tool_call["tool"]
        tool_args = tool_call["args"]
        tool_reasoning = tool_call.get("reasoning", "")

        if tool_name not in self.tool_map:
            error_msg = f"Tool '{tool_name}' not found. Available tools: {list(self.tool_map.keys())}"
            return create_error_response(
                error_msg,
                self._get_agent_name(),
                available_tools=list(self.tool_map.keys())
            )

        try:
            tool = self.tool_map[tool_name]
            validated_args = validate_tool_parameters(tool, tool_args)
            tool_result = await tool.invoke(**validated_args)

            logger.info(f"Tool result: {tool_result}")

            # Record execution
            tool_execution_info = {
                "step": f"{iteration + 1}_tool_result",
                "tool": tool_name,
                "args": validated_args,
                "reasoning": tool_reasoning,
                "result": tool_result
            }
            workflow_steps.append(tool_execution_info)
            tools_used.append({
                "tool_name": tool_name,
                "args": validated_args,
                "reasoning": tool_reasoning,
                "result": tool_result
            })

            if self.verbose:
                logger.info(
                    f"Tool {tool_name} executed successfully with args {validated_args}")

            # Check if tool has return_direct=True
            if hasattr(tool, 'return_direct') and tool.return_direct:
                # Return tool result directly, ending the workflow
                return create_success_response(
                    str(tool_result),
                    self._get_agent_name(),
                    steps=workflow_steps,
                    tools_used=tools_used,
                    return_direct=True,
                    tool=tool_name,
                    parameters=validated_args
                )

            return None  # Continue workflow

        except ValueError as e:
            return handle_parameter_validation_error(
                e, tool_name, self.tool_map[tool_name], self._get_agent_name(),
                steps=workflow_steps, iteration=iteration
            )
        except Exception as e:
            return handle_tool_execution_error(
                e, tool_name, self._get_agent_name(),
                steps=workflow_steps, iteration=iteration
            )

    # ==================== PUBLIC API ====================

    async def invoke(self, query: str, chat_history: Optional[List] = None, **kwargs) -> Dict[str, Any]:
        """Execute a query using available tools"""
        chat_history = chat_history or []
        result = await self._execute_tools_workflow(query, chat_history)
        return result

    async def stream(self, query: str, chat_history: Optional[List] = None, **kwargs):
        """Stream the agent's tool selection and execution process"""
        try:
            result = await self.invoke(query, chat_history)
            yield result
        except Exception as e:
            logger.error(f"Error streaming ToolAgent query: {str(e)}")
            yield create_error_response(str(e), self._get_agent_name())

    async def select_tool(self, query: str) -> Dict[str, Any]:
        """Select the most appropriate tool for a given query without executing it"""
        try:
            if not self.tools:
                return create_success_response(
                    "No tools are available. I can only provide direct responses based on my knowledge.",
                    self._get_agent_name(),
                    recommendation="No tools are available. I can only provide direct responses based on my knowledge.",
                    available_tools=[],
                    tool_parameters={},
                    no_tools_available=True
                )

            tool_descriptions = self._create_tool_descriptions_for_selection()
            selection_prompt = create_tool_selection_prompt(
                query, tool_descriptions)

            response = await self.llm_model.ainvoke(
                [{"role": "user", "content": selection_prompt}])
            response_content = response.content if hasattr(
                response, 'content') else str(response)

            return create_success_response(
                response_content,
                self._get_agent_name(),
                recommendation=response_content,
                available_tools=[tool.name for tool in self.tools],
                tool_parameters={tool.name: tool.parameters for tool in self.tools if hasattr(
                    tool, 'parameters')}
            )

        except Exception as e:
            logger.error(f"Error selecting tool: {str(e)}")
            return create_error_response(str(e), self._get_agent_name())

    def _create_tool_descriptions_for_selection(self) -> List[str]:
        """Create detailed tool descriptions for selection"""
        tool_descriptions = []
        for tool in self.tools:
            desc = f"- {tool.name}: {tool.description}"
            param_info = format_tool_parameters(tool)
            if param_info != "No parameters required":
                desc += f"\n  Parameters:\n{param_info}"
            tool_descriptions.append(desc)
        return tool_descriptions

    # ==================== TOOL MANAGEMENT ====================
    # Tool management methods are inherited from BaseToolAgent
