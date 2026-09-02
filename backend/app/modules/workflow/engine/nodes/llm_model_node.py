"""
LLM model node implementation using the BaseNode class.
"""

import base64
import logging
from typing import Any, Dict, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.utils.token_utils import calculate_history_tokens
from app.modules.workflow.agents.cot_agent import ChainOfThoughtAgent
from app.modules.workflow.engine import BaseNode
from app.modules.workflow.engine.node_result import node_failure
from app.modules.workflow.engine.pii_anonymizer_mixin import PIIAnonymizerMixin
from app.modules.workflow.engine.utils import has_volatile_template_vars
from app.modules.workflow.llm.provider import LLMProvider
from app.services.llm_providers import LlmProviderService

logger = logging.getLogger(__name__)


class LLMModelNode(PIIAnonymizerMixin, BaseNode):
    """LLM model node using the BaseNode approach"""

    async def _get_chat_history_for_context(
        self, memory, config: Dict[str, Any], provider_id: str, system_prompt: str, user_prompt: str
    ) -> str:
        """
        Get chat history based on configured trimming mode.

        Args:
            memory: Conversation memory instance
            config: Node configuration
            provider_id: LLM provider ID
            system_prompt: System prompt text (for token counting)
            user_prompt: User prompt text (for token counting)

        Returns:
            Formatted chat history string
        """
        trimming_mode = config.get("memoryTrimmingMode", "message_count")

        if trimming_mode == "token_budget":
            # Token-based trimming with budget enforcement
            from app.dependencies.injector import injector

            llm_service = injector.get(LlmProviderService)
            provider_info = await llm_service.get_by_id(provider_id)
            provider = provider_info.llm_model_provider
            model = provider_info.llm_model

            actual_history_tokens = calculate_history_tokens(
                config, model, provider, system_prompt, user_prompt
            )

            return await memory.get_chat_history_within_tokens(
                token_budget=actual_history_tokens, provider=provider, model=model, as_string=True
            )
        elif trimming_mode == "message_compacting":
            # Message compacting mode - compact old messages at threshold intervals
            # compactingKeepRecent: minimum raw messages to keep (context grows between compactions)
            # compactingThreshold: compact every N messages (e.g., at 20, 40, 60...)
            keep_recent = config.get("compactingKeepRecent", 10)
            threshold = config.get("compactingThreshold", 20)

            # Check if we've ever compacted before
            existing_summary = await memory.get_compacted_summary()

            if existing_summary or await memory.needs_compaction(threshold):
                # We've compacted before OR need to compact now
                if await memory.needs_compaction(threshold):
                    await self._perform_compaction(memory, config, provider_id)

                # Return compacted summary + ALL uncompacted messages
                # max_messages is only used as a fallback when no compaction exists yet
                return await memory.get_chat_history_with_compaction(
                    max_messages=keep_recent,  # Fallback limit only
                    as_string=True,
                )
            else:
                # Never compacted and below threshold - return ALL messages
                return await memory.get_chat_history(
                    as_string=True,
                    max_messages=999,  # Large number to get all messages
                )
        elif trimming_mode == "rag_retrieval":
            # Note: same structure and code as in AI agent node, this can be extracted to remove code duplication by a benevolent engineer
            # RAG-based retrieval mode:
            # - Below passthrough_threshold: all messages passed verbatim
            # - Above threshold: lazily index message groups into vector DB,
            #   retrieve semantically relevant groups + keep recent messages verbatim
            from app.dependencies.injector import injector
            from app.modules.workflow.agents.conversation_rag_indexer import ConversationRAGIndexer
            from app.modules.workflow.agents.rag import ThreadScopedRAG

            thread_rag = injector.get(ThreadScopedRAG)
            try:
                indexer = ConversationRAGIndexer(
                    thread_rag=thread_rag,
                    group_size=config.get("ragGroupSize", 4),
                    group_overlap=config.get("ragGroupOverlap", 2),
                    top_k=config.get("ragTopK", 3),
                    query_context_messages=config.get("ragQueryContextMessages", 3),
                    passthrough_threshold=config.get("ragPassthroughThreshold", 30),
                    recent_messages=config.get("ragRecentMessages", 6),
                )
            except ValueError as e:
                logger.error(f"Invalid RAG config: {e}. Falling back to message_count.")
                return await memory.get_chat_history(
                    as_string=True,
                    max_messages=config.get("ragRecentMessages", 6),
                )

            context_msgs = await indexer.assemble_context(
                thread_id=memory.thread_id,
                memory=memory,
                current_user_message=user_prompt,
            )
            history_parts = []
            for msg in context_msgs:
                prefix = f"{msg['role'].capitalize()}: "
                history_parts.append(f"{prefix}{msg['content']}")
            return "\n".join(history_parts)
        else:
            # Message count mode - simple last N messages
            max_messages = config.get("maxMessages", 10)
            return await memory.get_chat_history(as_string=True, max_messages=max_messages)

    def _system_prompt_is_cacheable(self, llm: Any, system_prompt: Any) -> tuple[bool, Optional[str]]:
        """Whether the system prompt is stable enough across requests to cache"""
        from app.modules.workflow.engine import prompt_cache_diagnostics as diagnostics

        parts = None if has_volatile_template_vars(self.node_data.get("systemPrompt")) else (system_prompt, "")
        return diagnostics.cache_split_decision(parts, llm)

    async def _perform_compaction(self, memory, config: Dict[str, Any], provider_id: str) -> None:
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

            from app.modules.workflow.engine.llm_usage_tracking import record_compaction_usage

            await record_compaction_usage(self.get_state(), new_summary, self.node_id, compacting_model_id)

            # Store compacted summary
            await memory.set_compacted_summary(new_summary)

            logger.info(f"Successfully compacted {len(to_compact)} messages")

        except Exception as e:
            logger.error(f"Error during compaction: {e}")
            # Don't fail the main request if compaction fails

    async def process(self, config: Dict[str, Any]) -> str:
        """
        Process an LLM model node.

        Args:
            config: The resolved configuration for the node

        Returns:
            The LLM response content
        """
        # Get configuration values (already resolved by BaseNode)
        provider_id = config.get("providerId")
        fallback_chain_id = config.get("fallbackChainId")
        system_prompt = config.get("systemPrompt", "You are a helpful assistant.")
        prompt = config.get("userPrompt", "Hello, how can you help me?")
        _type = config.get("type", "base")
        memory_enabled = config.get("memory", False)
        prompt_caching_enabled = config.get("promptCaching") is True

        logger.debug(f"Input data: system_prompt={system_prompt}, prompt={prompt}")

        try:
            if not provider_id:
                raise AppException(error_key=ErrorKey.MISSING_PARAMETER)

            # Set up the environment for the model
            from app.dependencies.injector import injector

            llm_provider = injector.get(LLMProvider)
            llm = await llm_provider.get_model_for_node(provider_id, fallback_chain_id, prompt_caching_enabled)

            memory = self.get_memory() if memory_enabled else None

            if _type == "Chain-of-Thought":
                if prompt_caching_enabled:
                    from app.modules.workflow.engine import prompt_cache_diagnostics as diagnostics

                    diagnostics.record(
                        self.get_state(), self.node_id,
                        applied=False, reason=diagnostics.REASON_UNSUPPORTED_MODE,
                    )
                agent = ChainOfThoughtAgent(
                    llm_model=llm,
                    system_prompt=system_prompt,
                    memory=memory,
                )
                chat_history = []
                if memory:
                    chat_history = await memory.get_messages()
                result = await agent.invoke(prompt, chat_history=chat_history)

                from app.modules.workflow.engine.llm_usage_tracking import merge_llm_usage_from_result

                await merge_llm_usage_from_result(
                    self.get_state(), result, self.node_id, provider_id, prompt_caching_enabled
                )
                if isinstance(result, dict) and "llm_usage" in result:
                    result = {k: v for k, v in result.items() if k != "llm_usage"}
                return result

            cacheable_prefix, cache_reason = self._system_prompt_is_cacheable(llm, system_prompt)

            chat_history = ""
            if memory:
                chat_history = await self._get_chat_history_for_context(
                    memory, config, provider_id, system_prompt, prompt
                )

            if cacheable_prefix:
                from app.modules.workflow.llm.prompt_caching_chat_model import build_cacheable_system_message

                stable_text = (system_prompt + "\n\n") if memory else system_prompt
                system_message = build_cacheable_system_message(stable_text, chat_history)
            elif memory:
                system_message = SystemMessage(content=system_prompt + "\n\n" + chat_history)
            else:
                system_message = SystemMessage(content=system_prompt)

            # default message content
            message_content = [{"type": "text", "text": prompt}]

            # build message content with attachments
            attachments = self.get_state().get_value("attachments", [])

            if attachments:
                attachments_message_content = self._build_attachments_message_content(attachments)
                message_content.extend(attachments_message_content)

            if prompt_caching_enabled and not cacheable_prefix:
                from app.modules.workflow.engine import prompt_cache_diagnostics as diagnostics

                diagnostics.record(self.get_state(), self.node_id, applied=False, reason=cache_reason)

            # Process the input through the model
            response = await llm.ainvoke([system_message, HumanMessage(content=message_content)])

            from app.modules.workflow.engine.llm_usage_tracking import record_node_llm_usage

            await record_node_llm_usage(
                self.get_state(), response, self.node_id, provider_id, prompt_caching_enabled=prompt_caching_enabled
            )

            if prompt_caching_enabled and cacheable_prefix:
                from app.modules.workflow.engine import prompt_cache_diagnostics as diagnostics

                diagnostics.record(self.get_state(), self.node_id, applied=True)

            return response.content

        except Exception as e:
            logger.error(f"Error processing LLM node: {str(e)}")
            error_message = f"Error: {str(e)}"
            # Preserve the "Error: ..." string as the flow output so downstream
            # text consumers still receive a string, but record the failure.
            return node_failure(str(e), output=error_message)

    def _convert_attachment_to_base64(self, attachment_local_path: str) -> str:
        """Convert attachment local path to base64"""
        import os

        attachment_os_path = os.path.join(attachment_local_path)
        with open(attachment_os_path, "rb") as read_file:
            attachment_base64 = base64.standard_b64encode(read_file.read()).decode("utf-8")
            return attachment_base64

    def _build_attachments_message_content(self, attachments: list) -> list:
        """
        Build message content for image attachments.

        Only images are sent to the vision model here; documents are read by the
        File Reader node.

        Args:
            attachments: List of attachment dictionaries

        Returns:
            List of image message content items
        """
        # create message content with attachments
        message_content = []

        if attachments:
            for attachment in attachments:
                mime_type = attachment.get("type") or attachment.get("file_mime_type") or ""
                is_image = mime_type.startswith("image")

                # Documents are read by the File Reader node, not the vision model.
                if not is_image:
                    continue

                attachment_file_local_path = attachment.get("file_local_path")
                attachment_mime_type = attachment.get("file_mime_type")
                attachment_url = attachment.get("url")

                # if attachment_file_local_path is provided, convert to base64
                if attachment_file_local_path:
                    # get file base64
                    base64_content = self._convert_attachment_to_base64(attachment_file_local_path)
                    attachment_url = f"data:{attachment_mime_type};base64,{base64_content}"

                message_content.append({"type": "image_url", "image_url": {"url": attachment_url}})

        return message_content
