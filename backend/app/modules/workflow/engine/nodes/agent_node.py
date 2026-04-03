"""
Agent node implementation using the BaseNode class.
"""

import datetime
from typing import Dict, Any
import logging

from app.core.utils.token_utils import calculate_history_tokens
from app.modules.workflow.engine import BaseNode
from app.modules.workflow.engine.pii_anonymizer_mixin import PIIAnonymizerMixin
from app.modules.workflow.llm.provider import LLMProvider
from app.modules.workflow.agents.react_agent import ReActAgent
from app.modules.workflow.agents.react_agent_lc import ReActAgentLC
from app.modules.workflow.agents.simple_tool_agent import SimpleToolAgent
from app.modules.workflow.agents.tool_agent import ToolAgent
from app.services.llm_providers import LlmProviderService


logger = logging.getLogger(__name__)


class AgentNode(PIIAnonymizerMixin, BaseNode):
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
        elif trimming_mode == "rag_retrieval":
            # RAG-based retrieval mode:
            # - Below passthrough_threshold: all messages passed verbatim
            # - Above threshold: lazily index message groups into vector DB,
            #   retrieve semantically relevant groups + keep recent messages verbatim
            from app.dependencies.injector import injector
            from app.modules.workflow.agents.rag import ThreadScopedRAG
            from app.modules.workflow.agents.conversation_rag_indexer import ConversationRAGIndexer

            thread_rag = injector.get(ThreadScopedRAG)

            indexer = ConversationRAGIndexer(
                thread_rag=thread_rag,
                group_size=config.get("ragGroupSize", 4),
                group_overlap=config.get("ragGroupOverlap", 2),
                top_k=config.get("ragTopK", 3),
                query_context_messages=config.get("ragQueryContextMessages", 3),
                passthrough_threshold=config.get("ragPassthroughThreshold", 30),
                recent_messages=config.get("ragRecentMessages", 6),
                max_history_hours=config.get("ragMaxHistoryHours", 0),
                rag_config_overrides={
                    **(config.get("ragVectorConfig") or {}),
                    # Always override chunking: ConversationRAGIndexer already
                    # groups messages into the correct semantic unit, so each
                    # group must be stored as a single vector document.
                    "chunk_size": 100_000,
                    "chunk_overlap": 0,
                },
            )

            return await indexer.assemble_context(
                thread_id=memory.thread_id,
                memory=memory,
                current_user_message=user_prompt,
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
            important_entities = config.get("compactingImportantEntities") or None

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
            new_summary = await compactor.compact_messages(to_compact, existing_summary, important_entities)

            # Store compacted summary
            await memory.set_compacted_summary(new_summary)

            logger.info(f"Successfully compacted {len(to_compact)} messages")

        except Exception as e:
            logger.error(f"Error during compaction: {e}")
            # Don't fail the main request if compaction fails

    def _wrap_tools_for_pii_unmask(self, tools) -> None:
        """Patch each tool's invoke so string arguments are unmasked before execution."""
        for tool in tools:
            original_invoke = tool.invoke

            def _make_wrapper(orig):
                def _unmasked_invoke(**kwargs):
                    unmasked = {
                        k: self._unmask_for_tool(v) if isinstance(v, str) else v
                        for k, v in kwargs.items()
                    }
                    return orig(**unmasked)
                return _unmasked_invoke

            tool.invoke = _make_wrapper(original_invoke)

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

        # When PII masking is enabled, wrap tools so they receive unmasked
        # (original) values instead of anonymization tokens like <EMAIL_ADDRESS_1>.
        if config.get("piiMasking") and tools:
            self._wrap_tools_for_pii_unmask(tools)

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

            from app.modules.workflow.engine.llm_usage_tracking import merge_llm_usage_from_result

            await merge_llm_usage_from_result(
                self.get_state(), result, self.node_id, provider_id
            )

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
