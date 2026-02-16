"""
Agent node implementation using the BaseNode class.
"""

import datetime
from typing import Dict, Any
import logging

from app.modules.workflow.engine.base_node import BaseNode
from app.modules.workflow.llm.provider import LLMProvider
from app.modules.workflow.agents.react_agent import ReActAgent
from app.modules.workflow.agents.react_agent_lc import ReActAgentLC
from app.modules.workflow.agents.simple_tool_agent import SimpleToolAgent
from app.modules.workflow.agents.tool_agent import ToolAgent

logger = logging.getLogger(__name__)


class AgentNode(BaseNode):
    """Agent node that can select and execute tools using the BaseNode approach"""

    async def _get_chat_history_for_agent(
        self, memory, config: Dict[str, Any], provider_id: str, system_prompt: str, user_prompt: str
    ) -> list:
        """
        Get chat history based on configured trimming mode.

        Args:
            memory: Conversation memory instance
            config: Node configuration
            provider_id: LLM provider ID
            system_prompt: System prompt text (for token counting)
            user_prompt: User prompt text (for token counting)

        Returns:
            List of message dictionaries
        """
        trimming_mode = config.get("memoryTrimmingMode", "message_count")

        if trimming_mode == "token_budget":
            # Token-based trimming with budget enforcement
            from app.dependencies.injector import injector
            from app.services.llm_providers import LlmProviderService
            from app.core.utils.token_utils import get_token_counter

            llm_service = injector.get(LlmProviderService)
            provider_info = await llm_service.get_by_id(provider_id)
            provider = provider_info.llm_model_provider
            model = provider_info.llm_model

            # Get token counter
            counter = get_token_counter(provider, model)

            # Count actual tokens in prompts
            system_tokens = counter.count_tokens(system_prompt)
            user_tokens = counter.count_tokens(user_prompt)

            # Get configuration
            total_budget = config.get("tokenBudget", 12000)
            requested_history_tokens = config.get("conversationHistoryTokens", 5000)

            # Calculate if we need to reduce history allocation
            needed = system_tokens + user_tokens + requested_history_tokens

            if needed > total_budget:
                # Reduce history to fit within budget
                actual_history_tokens = total_budget - system_tokens - user_tokens
                actual_history_tokens = max(0, actual_history_tokens)  # Ensure non-negative
                logger.warning(
                    f"Token budget exceeded. Requested history: {requested_history_tokens}, "
                    f"reduced to: {actual_history_tokens} (Total: {total_budget}, "
                    f"System: {system_tokens}, User: {user_tokens})"
                )
            else:
                # Within budget, use requested allocation
                actual_history_tokens = requested_history_tokens

            return await memory.get_chat_history_within_tokens(
                token_budget=actual_history_tokens,
                provider=provider,
                model=model,
                as_string=False
            )
        else:
            # Message count-based trimming (existing behavior)
            max_messages = config.get("maxMessages", 10)
            return await memory.get_messages(max_messages=max_messages)

    async def process(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process an agent node with tool selection and execution.

        Args:
            config: The resolved configuration for the node

        Returns:
            Dictionary with agent response and execution steps
        """
        # Get configuration values (already resolved by BaseNode)
        provider_id: str | None = config.get("providerId", None)
        # ToolSelector, ReActAgent
        agent_type: str = config.get("type", "ToolSelector")
        max_iterations = config.get("maxIterations", 7)
        memory_enabled = config.get("memory", False)

        # Get input data from state (this would typically come from connected nodes)
        # For now, we'll use default values
        system_prompt = config.get(
            "systemPrompt", "You are a helpful assistant.")
        prompt = config.get("userPrompt", "What is the capital of France?")

        # Get tools from connected nodes using the new generic method
        tools = self.get_connected_nodes("tools")

        # Add current time to system prompt
        system_prompt += f" Current time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

        # Set input for tracking
        self.set_node_input({
            "system_prompt": system_prompt,
            "prompt": prompt,
            "tools_reference": tools
        })

        logger.info("Agent type: %s", agent_type)

        try:
            from app.dependencies.injector import injector
            llm_provider = injector.get(LLMProvider)
            llm_model = await llm_provider.get_model(provider_id)
            logger.info("Agent type selected: %s, LLM model: %s",
                        agent_type, llm_model)

            # Create agent based on type
            if agent_type == "ReActAgent":
                agent = ReActAgent(
                    llm_model=llm_model,
                    system_prompt=system_prompt,
                    tools=tools,
                    max_iterations=max_iterations
                )
            elif agent_type == "ReActAgentLC":
                agent = ReActAgentLC(
                    llm_model=llm_model,
                    system_prompt=system_prompt,
                    tools=tools,
                    max_iterations=max_iterations
                )
            elif agent_type == "SimpleToolExecutor":
                agent = SimpleToolAgent(
                    llm_model=llm_model,
                    system_prompt=system_prompt,
                    tools=tools,
                )
            else:
                agent = ToolAgent(
                    llm_model=llm_model,
                    system_prompt=system_prompt,
                    tools=tools,
                    max_iterations=max_iterations
                )

            # Get chat history if memory is enabled
            chat_history = []
            if memory_enabled:
                chat_history = await self._get_chat_history_for_agent(
                    self.get_memory(), config, provider_id, system_prompt, prompt
                )

            # Invoke the agent
            result = await agent.invoke(prompt, chat_history=chat_history)
            logger.debug("Agent result: %s", result)

            # Prepare output
            output = {
                "message": result.get("response", "Something went wrong"),
                "steps": result.get("reasoning_steps", []) if agent_type in ["ReActAgent", "ReActAgentLC"] else result.get("steps", [])
            }

            return output

        except Exception as e:
            logger.error("Error processing agent node: %s", str(e))
            error_message = f"Error: {str(e)}"
            return {"error": error_message}
