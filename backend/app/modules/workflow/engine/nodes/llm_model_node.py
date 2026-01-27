"""
LLM model node implementation using the BaseNode class.
"""

import base64
import os
from typing import Any, Dict
import logging
from uuid import UUID
from fastapi_injector import Injected
from langchain_core.messages import HumanMessage, SystemMessage

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.modules.workflow.engine.base_node import BaseNode
from app.modules.workflow.llm.provider import LLMProvider
from app.modules.workflow.agents.cot_agent import ChainOfThoughtAgent

logger = logging.getLogger(__name__)


class LLMModelNode(BaseNode):
    """LLM model node using the BaseNode approach"""

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

        logger.info(
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
                chat_history = await memory.get_chat_history(
                    as_string=True, max_messages=10)
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