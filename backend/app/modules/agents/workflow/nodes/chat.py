from typing import Dict, Any, List
from app.modules.agents.workflow.base_processor import NodeProcessor
import logging

logger = logging.getLogger(__name__)

class ChatInputNodeProcessor(NodeProcessor):
    """Processor for chat input nodes"""
    
    
    
    async def process(self, input_data: Any = None) -> str:
        """Process a chat input node"""
        # For chat input nodes, the input_data is the user's message
        if input_data is None:
            input_data = self.context.state.get_user_query()
        self.set_input(input_data)

        self.save_output(input_data)
        logger.info(f"ChatInputNodeProcessor output: {self.output}")
        return input_data



class ChatOutputNodeProcessor(NodeProcessor):
    """Processor for chat output nodes"""
    
    async def process(self, input_data: Any = None) -> List[Dict[str, str]]:
        """Process a chat output node"""
        # Get input from connected edges
        input_data = await self.get_process_input()
        self.set_input(input_data)
        if input_data is None:
            logger.warning("No input data received for chat output node")
            return None
        
        self.save_output(input_data)
        logger.info(f"ChatOutputNodeProcessor output: {self.output}")
        return {
            # **input_data,
            "status": "success",
            "response": self.output,
            "agent_id": self.context.workflow_id,
            "thread_id": self.context.state.thread_id,
        }

