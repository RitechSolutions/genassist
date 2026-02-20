"""
Agent node implementation using the BaseNode class.
"""

import datetime
from typing import Dict, Any
import logging

from app.core.utils.token_utils import calculate_history_tokens
from app.modules.workflow.engine import BaseNode
from app.modules.workflow.llm.provider import LLMProvider
from app.modules.workflow.agents.react_agent import ReActAgent
from app.modules.workflow.agents.react_agent_lc import ReActAgentLC
from app.modules.workflow.agents.simple_tool_agent import SimpleToolAgent
from app.modules.workflow.agents.tool_agent import ToolAgent
from app.services.llm_providers import LlmProviderService


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

            llm_service = injector.get(LlmProviderService)
            provider_info = await llm_service.get_by_id(provider_id)
            provider = provider_info.llm_model_provider
            model = provider_info.llm_model

            actual_history_tokens = calculate_history_tokens(config, model, provider,
                                                                   system_prompt, user_prompt)

            return await memory.get_chat_history_within_tokens(
                token_budget=actual_history_tokens,
                provider=provider,
                model=model,
                as_string=False
            )
        elif trimming_mode == "message_compacting":
         # Message compacting mode - compact old messages at threshold intervals
            # compactingKeepRecent: minimum raw messages to keep (context grows between compactions)
            # compactingThreshold: compact every N messages (e.g., at 20, 40, 60...)
            keep_recent = config.get("compactingKeepRecent", 10)
            threshold = config.get("compactingThreshold", 20)

            # Check if we've ever compacted before
            existing_summary = await memory.get_compacted_summary()
            needs_compaction = await memory.needs_compaction(threshold)
            if existing_summary or needs_compaction:
                # We've compacted before OR need to compact now
                if needs_compaction:
                    await self._perform_compaction(memory, config, provider_id)

                # Return compacted summary + ALL uncompacted messages
                # max_messages is only used as a fallback when no compaction exists yet
                return await memory.get_chat_history_with_compaction(
                    max_messages=keep_recent,  # Fallback limit only
                    as_string=False
                )
            else:
                # Never compacted and below threshold - return ALL messages
                return await memory.get_messages(
                    max_messages=999  # Large number to get all messages
                )
        else:
            # Message count mode - simple last N messages
            max_messages = config.get("maxMessages", 10)
            return await memory.get_messages(max_messages=max_messages)

    async def _perform_compaction(
        self, memory, config: Dict[str, Any], provider_id: str
    ) -> None:
        """
        Perform message compaction using configured settings.

        Args:
            memory: Conversation memory instance
            config: Node configuration
            provider_id: LLM provider ID for compaction
        """
        try:
            keep_recent = config.get("compactingKeepRecent", 10)

            # Get messages to compact
            to_compact = await memory.get_messages_for_compaction(keep_recent)

            if not to_compact:
                logger.info("No messages available for compaction")
                return

            # Get or create LLM for compaction
            compacting_model_id = config.get("compactingModel") or provider_id
            from app.dependencies.injector import injector
            llm_provider = injector.get(LLMProvider)
            llm_model = await llm_provider.get_model(compacting_model_id)

            # Create compactor and perform compaction
            from app.modules.workflow.agents.memory_compactor import MemoryCompactor
            compactor = MemoryCompactor(llm_model)

            existing_summary = await memory.get_compacted_summary()
            new_summary = await compactor.compact_messages(to_compact, existing_summary)

            # Store compacted summary
            await memory.set_compacted_summary(new_summary)

            logger.info(f"Successfully compacted {len(to_compact)} messages")

        except Exception as e:
            logger.error(f"Error during compaction: {e}")
            # Don't fail the main request if compaction fails

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
