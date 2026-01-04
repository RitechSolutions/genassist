"""
LLM model node implementation using the BaseNode class.
"""

from typing import Any, Dict
import logging
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
        system_prompt = config.get(
            "systemPrompt", "You are a helpful assistant.")
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

            # Process the input through the model
            response = await llm.ainvoke(
                [SystemMessage(content=system_prompt), HumanMessage(content=prompt)])
            result = response.content

            return result

        except Exception as e:
            logger.error(f"Error processing LLM node: {str(e)}")
            error_message = f"Error: {str(e)}"
            return error_message
