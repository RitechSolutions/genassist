"""
LLM model node implementation using the BaseNode class.
"""

import base64
from typing import Any, Dict
import logging
from langchain_core.messages import HumanMessage, SystemMessage
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.utils.token_utils import calculate_history_tokens
from app.modules.workflow.engine import BaseNode
from app.modules.workflow.llm.provider import LLMProvider
from app.modules.workflow.agents.cot_agent import ChainOfThoughtAgent
from app.services.llm_providers import LlmProviderService


logger = logging.getLogger(__name__)


class LLMModelNode(BaseNode):
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

            actual_history_tokens, model, provider = calculate_history_tokens(config, model, provider,
                                                                                    system_prompt, user_prompt)

            return await memory.get_chat_history_within_tokens(
                token_budget=actual_history_tokens,
                provider=provider,
                model=model,
                as_string=True
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
                    as_string=True
                )
            else:
                # Never compacted and below threshold - return ALL messages
                return await memory.get_chat_history(
                    as_string=True,
                    max_messages=999  # Large number to get all messages
                )
        else:
            # Message count mode - simple last N messages
            max_messages = config.get("maxMessages", 10)
            return await memory.get_chat_history(
                as_string=True,
                max_messages=max_messages
            )

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
        system_prompt = config.get("systemPrompt", "You are a helpful assistant.")
        prompt = config.get("userPrompt", "Hello, how can you help me?")
        _type = config.get("type", "base")
        memory_enabled = config.get("memory", False)

        logger.debug(
            f"Input data: system_prompt={system_prompt}, prompt={prompt}")

        try:
            if not provider_id:
                raise AppException(error_key=ErrorKey.MISSING_PARAMETER)

            # Set up the environment for the model
            from app.dependencies.injector import injector
            llm_provider = injector.get(LLMProvider)
            llm = await llm_provider.get_model(provider_id)

            memory = self.get_memory() if memory_enabled else None

            if _type == "Chain-of-Thought":
                agent = ChainOfThoughtAgent(
                    llm_model=llm,
                    system_prompt=system_prompt,
                    memory=memory,
                )
                chat_history = []
                if memory:
                    chat_history = await memory.get_messages()
                result = await agent.invoke(prompt, chat_history=chat_history)

                return result

            if memory:
                chat_history = await self._get_chat_history_for_context(
                    memory, config, provider_id, system_prompt, prompt
                )
                system_prompt = system_prompt + "\n\n" + chat_history

            # default message content
            message_content = [{ "type": "text", "text": prompt }]

            # build message content with attachments
            attachments = self.get_state().get_value("attachments", [])

            if attachments:
                attachments_message_content = self._build_attachments_message_content(attachments)
                message_content.extend(attachments_message_content)
            
            # Process the input through the model
            response = await llm.ainvoke([SystemMessage(content=system_prompt), HumanMessage(content=message_content)])
            result = response.content

            return result

        except Exception as e:
            logger.error(f"Error processing LLM node: {str(e)}")
            error_message = f"Error: {str(e)}"
            return error_message

    def _convert_attachment_to_base64(self, attachment_local_path: str) -> str:
        """Convert attachment local path to base64"""
        import os
        attachment_os_path = os.path.join(attachment_local_path)
        with open(attachment_os_path, "rb") as read_file:
            attachment_base64 = base64.standard_b64encode(read_file.read()).decode("utf-8")
            return attachment_base64

    def _build_attachments_message_content(self, attachments: list) -> list:
        """
        Build message content with attachments.
        
        Args:
            attachments: List of attachment dictionaries
            
        Returns:
            List of message content items (text, images, files)
        """
        # create message content with attachments
        message_content = []

        if attachments:
            for attachment in attachments:
                attachment_type = "image" if attachment.get("type").startswith("image") else "file"
                attachment_file_local_path = attachment.get("file_local_path")
                attachment_mime_type = attachment.get("file_mime_type")
                attachment_url = attachment.get("url")
                attachment_file_id = attachment.get("openai_file_id")  # OpenAI file_id for file inputs

                if attachment_type == "image":
                    # if attachment_file_local_path is provided, convert to base64
                    if attachment_file_local_path:
                        # get file base64
                        base64_content = self._convert_attachment_to_base64(attachment_file_local_path)
                        attachment_url = f"data:{attachment_mime_type};base64,{base64_content}"
                    
                    message_content.append({
                        "type": "image_url",
                        "image_url": {"url": attachment_url}
                    })
                else:
                    # Priority: OpenAI file_id > URL > base64
                    if attachment_file_id:
                        # Use OpenAI file_id (preferred for PDFs and supported file types)
                        message_content.append({
                            "type": "file",
                            "file": {
                                "file_id": attachment_file_id
                            }
                        })
                        logger.info(f"Using OpenAI file_id: {attachment_file_id} for file attachment")
                    elif attachment_url:
                        # Fallback to URL if file_id not available
                        message_content.append({
                            "type": "file",
                            "url": attachment_url,
                        })
                        logger.warning(f"Using URL fallback for file attachment (file_id not available)")
                    else:
                        logger.warning(f"No file_id or URL available for attachment, skipping")
        
        return message_content