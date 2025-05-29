from typing import Any
import logging
from langchain_core.messages import HumanMessage,SystemMessage
from langchain.chat_models import init_chat_model
import os


from app.modules.agents.llm.provider import LLMProvider
from app.modules.agents.workflow.base_processor import NodeProcessor
from app.schemas.llm import LlmProviderUpdate

logger = logging.getLogger(__name__)




class LLMModelNodeProcessor(NodeProcessor):
    """Processor for LLM model nodes"""
    
    async def process(self, input_data: Any = None) -> str:
        """Process an LLM model node"""
        
        node_config = self.get_node_config()
        
        # new_llm_provider = LlmProviderUpdate(
        #     llm_model=node_config.get("model", "gpt-3.5-turbo"),
        #     llm_model_provider=node_config.get("provider", "openai"),
        #     connection_data={"apiKey": node_config.get("apiKey", ""),
        #                     "temperature": node_config.get("temperature", 0.7),
        #                     "maxTokens": node_config.get("maxTokens", 1024)
        #                     },
        # )
        provider_id = node_config.get("providerId", None)
        process_input = await self.get_process_input(input_data)
        self.set_input(process_input)
        
        input_data = await self.get_process_input(input_data)
        logger.info(f"Input data: {input_data}")
        system_prompt = input_data.get("system_prompt")
        logger.info(f"System prompt: {system_prompt}")
        
        system_prompt_messages = []
        if system_prompt:
            system_prompt_messages.append(SystemMessage(content=system_prompt))

        prompt = input_data.get("prompt")
        self.set_input(prompt)
        
        
        
        
        try:
            logger.info(f"LLMModelNodeProcessor input_text: {process_input}")
            # Set up the environment for the model
            llm = LLMProvider.get_instance().get_model(provider_id);
          
            # Process the input through the model
            response = llm.invoke([*system_prompt_messages, HumanMessage(content=prompt)])
            result = response.content
            logger.info(f"LLMModelNodeProcessor result: {result}")
            
            # Save the result
            self.save_output(result)
            
            return result
        except Exception as e:
            logger.error(f"Error processing LLM node: {str(e)}")
            error_message = f"Error: {str(e)}"
            self.save_output(error_message)
            return error_message

