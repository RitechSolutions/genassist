from typing import List, Dict, Any, Optional
import logging
from langchain_core.language_models import BaseChatModel
from app.modules.workflow.agents.base_tool import BaseTool
from app.modules.workflow.agents.base_tool_agent import BaseToolAgent
from app.modules.workflow.agents.agent_utils import (
    create_tool_descriptions,
    execute_tool_safely,
    create_tool_execution_info,
    create_error_response,
    create_success_response,
    extract_final_answer,
    extract_thought,
    parse_react_action,
)
from app.modules.workflow.agents.agent_prompts import (
    create_react_tools_available_prompt,
    create_react_no_tools_prompt,
    create_react_query_prompt,
    create_conversation_context as build_conversation_context,
)

logger = logging.getLogger(__name__)


class ReActAgent(BaseToolAgent):
    """ReAct (Reason and Act) Agent that combines reasoning and action-taking capabilities"""

    def __init__(
        self,
        llm_model: BaseChatModel,
        system_prompt: str,
        tools: List[BaseTool],
        verbose: bool = False,
        max_iterations: int = 5,
    ):
        """Initialize a ReAct agent

        Args:
            llm_model: The language model to use for reasoning and decision making
            system_prompt: System prompt that defines the agent's behavior and role
            tools: List of tools the agent can use to take actions
            verbose: Whether to enable verbose logging of reasoning cycles
            max_iterations: Maximum number of reasoning/action cycles
        """
        super().__init__(llm_model, system_prompt, tools, verbose, max_iterations)

    # ==================== PROMPT GENERATION ====================

    def _create_enhanced_system_prompt(self) -> str:
        """Create an enhanced system prompt using centralized prompt templates"""
        if self.tools:
            tool_descriptions = create_tool_descriptions(self.tools)
            return create_react_tools_available_prompt(
                self.system_prompt, tool_descriptions
            )
        else:
            return create_react_no_tools_prompt(self.system_prompt)

    # ==================== TOOL EXECUTION ====================

    async def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> str:
        """Execute a tool with given input and parameter validation"""
        if tool_name == "none" or tool_name not in self.tool_map:
            return f"Tool '{tool_name}' not found. Available tools: {list(self.tool_map.keys())}"

        tool = self.tool_map[tool_name]
        return await execute_tool_safely(tool, tool_input, tool_name)

    # ==================== WORKFLOW EXECUTION ====================
    async def _run_react_cycle(
        self, query: str, chat_history: List[Dict[str, str]], thread_id: str = "default"
    ) -> Dict[str, Any]:
        """Run the ReAct reasoning cycle with enhanced workflow and RAG context"""
        enhanced_prompt = self._create_enhanced_system_prompt()
        # Retrieve RAG context for this chat
        context = build_conversation_context(chat_history)

        current_prompt = create_react_query_prompt(enhanced_prompt, context, query)

        reasoning_steps = []
        tools_used = []

        for iteration in range(self.max_iterations):
            try:
                response = await self.llm_model.ainvoke(
                    [{"role": "user", "content": current_prompt}]
                )
                response_content = (
                    response.content if hasattr(response, "content") else str(response)
                )

                if self.verbose:
                    logger.info(f"ReAct iteration {iteration + 1}: {response_content}")

                # Record reasoning step
                thought = extract_thought(response_content)
                reasoning_steps.append(
                    {
                        "iteration": iteration + 1,
                        "thought": thought,
                        "full_response": response_content,
                    }
                )

                # Check for Final Answer
                final_answer = extract_final_answer(response_content)
                if final_answer:
                    return create_success_response(
                        final_answer,
                        self._get_agent_name(),
                        iterations=iteration + 1,
                        reasoning_steps=reasoning_steps,
                        tools_used=tools_used,
                    )

                # Parse action
                parsed = parse_react_action(response_content)
                action = parsed["action"]
                action_input = parsed["action_input"]

                if action == "none":
                    # No action needed, but no final answer yet - continue reasoning
                    current_prompt += f"\n\n{response_content}\nObservation: No tool used. Continue reasoning.\n"
                    continue

                # Execute tool
                observation = await self._execute_tool(action, action_input)

                # Record tool usage
                tool_execution = create_tool_execution_info(
                    iteration + 1, action, action_input, observation
                )
                tools_used.append(tool_execution)

                # Check if the tool has return_direct=True
                if action in self.tool_map:
                    tool = self.tool_map[action]
                    if hasattr(tool, "return_direct") and tool.return_direct:
                        # Return tool result directly, ending the ReAct cycle
                        return create_success_response(
                            str(observation),
                            self._get_agent_name(),
                            iterations=iteration + 1,
                            reasoning_steps=reasoning_steps,
                            tools_used=tools_used,
                            return_direct=True,
                            tool=action,
                        )

                # Update prompt with observation
                current_prompt += (
                    f"\n\n{response_content}\nObservation: {observation}\n"
                )

            except Exception as e:
                logger.error(f"Error in ReAct cycle iteration {iteration}: {str(e)}")
                return create_error_response(
                    f"Error in iteration {iteration}: {str(e)}",
                    self._get_agent_name(),
                    reasoning_steps=reasoning_steps,
                    tools_used=tools_used,
                )

        # Max iterations reached
        return create_error_response(
            f"Max iterations ({self.max_iterations}) reached without final answer",
            self._get_agent_name(),
            reasoning_steps=reasoning_steps,
            tools_used=tools_used,
        )

    # ==================== PUBLIC API ====================

    async def invoke(
        self, query: str, chat_history: Optional[List] = None, **kwargs
    ) -> Dict[str, Any]:
        """Execute a query using the ReAct pattern"""
        chat_history = chat_history or []
        thread_id = kwargs.get("thread_id", "default")
        try:
            result = await self._run_react_cycle(query, chat_history, thread_id)
            result["thread_id"] = thread_id
            return result
        except Exception as e:
            logger.error(f"Error executing ReActAgent query: {str(e)}")
            return create_error_response(
                str(e), self._get_agent_name(), thread_id=thread_id
            )

    async def stream(self, query: str, chat_history: Optional[List] = None, **kwargs):
        """Stream the agent's reasoning and action process"""
        try:
            # For now, just yield the final result
            # In a full implementation, you'd stream each reasoning step
            result = await self.invoke(query, chat_history, **kwargs)
            yield result
        except Exception as e:
            logger.error(f"Error streaming ReActAgent query: {str(e)}")
            thread_id = kwargs.get("thread_id", "default")
            yield create_error_response(
                str(e), self._get_agent_name(), thread_id=thread_id
            )
