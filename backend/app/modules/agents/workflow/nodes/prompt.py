import asyncio
from typing import Any, Dict
import logging


from app.core.utils.string_utils import replace_template_vars
from app.modules.agents.workflow.base_processor import NodeProcessor

logger = logging.getLogger(__name__)



class PromptNodeProcessor(NodeProcessor):
    """Processor for prompt template nodes"""
    def __init__(self, context, node_id, node_data):
        super().__init__(context, node_id, node_data)
        self.on_init()

    def on_init(self):
        # input_edges = self.get_inputs_from_source_nodes()
        # logger.info(f"Input edges: {input_edges}")

        # if not input_edges:
        asyncio.create_task(self.process(None))
        

    async def process(self, input_data: Any = None) -> str:
        logger.info(f"PromptNodeProcessor input_data")
        """Process a prompt template node"""
        node_config = self.get_node_config()
        
        template = node_config.get("template", "")
        
        include_history = node_config.get("includeHistory", False)
        
        # Get inputs from connected edges
        edge_inputs = await self.get_process_input(input_data)
        user_metadata = self.get_state().get_session_metadata()
        # Merge all inputs
        input_object = {
            **edge_inputs,  # Edge-based inputs
            **user_metadata  # Session data
        }
        self.set_input(input_object)
        
        logger.debug(f"PromptNodeProcessor input_object: {input_object}")

        # Process the template with input values
        processed_prompt = replace_template_vars(template, input_object)
        
        if include_history:
            # Get conversation history and insert it
            history = self.get_memory().get_chat_history(as_string=True)
            processed_prompt = f"{processed_prompt}\n\nConversation History:\n{history}"

        self.save_output(processed_prompt)
        logger.info(f"PromptNodeProcessor output: {self.output}")
        return processed_prompt

