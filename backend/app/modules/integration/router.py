from typing import Dict, Any
import logging
import re
from injector import inject
from app.modules.agents.workflow.base_processor import NodeProcessor

logger = logging.getLogger(__name__)

@inject
class RouterNodeProcessor(NodeProcessor):
    """A node that routes the workflow based on conditional logic or AI classifier"""
    condition_compare_options = ['equal','not_equal','contains','not_contain','starts_with','not_starts_with','ends_with','not_ends_with','regex']
    async def process(self, input_data: Any = None) -> Any:
        # 1. Gather input
        input_data = await self.get_process_input(input_data)
        
        input_text = input_data.get("message").lower()
        self.set_input(input_text)

        # 2. Pull the value to compare
        path_name = self.node_data.get("path_name")
        compare_condition = self.node_data.get("compare_condition")
        value_condition = self.node_data.get("value_condition").lower()

        if path_name is None or compare_condition is None or value_condition is None:
            logger.warning(f"[RouterNode] missing one or more values in input condition: {input_data}")
            route = "message_default" # 'message_default' is the route path if none of the conditions are meet
        else:
            # 3. Custom logic: compare and set route
            if compare_condition=='equal':
                route = path_name if input_text==value_condition else 'message_default'
            elif compare_condition=='not_equal':
                route = path_name if input_text!=value_condition else 'message_default'
            elif compare_condition=='contains':
                route = path_name if value_condition in input_text else 'message_default'
            elif compare_condition=='not_contain':
                route = path_name if value_condition not in input_text else 'message_default'
            elif compare_condition=='starts_with':
                route = path_name if input_text and input_text.startswith(value_condition) else 'message_default'
            elif compare_condition=='not_starts_with':
                route = path_name if input_text and not input_text.startswith(value_condition) else 'message_default'
            elif compare_condition=='ends_with':
                route = path_name if input_text and input_text.endswith(value_condition) else 'message_default'
            elif compare_condition=='not_ends_with':
                route = path_name if input_text and not input_text.endswith(value_condition) else 'message_default'
            elif compare_condition=='regex':
                route = path_name if input_text and re.search(value_condition, input_text) else 'message_default'
            else:
                logger.warning(f"[RouterNode] doesn't support compare_condition: {compare_condition}")
                route = "message_default"

            logger.info(f"[RouterNode] Routed to {route} based on value={compare_condition}('{value_condition}')")

        self.node_data["selected_route"]=route        
        # 4. Save output (including the routing recommendation)
        self.save_output({route: input_text, "selected_route": route})
        logger.info(f"RouterNode route: {route} output: {self.output}")
        return self.get_output()