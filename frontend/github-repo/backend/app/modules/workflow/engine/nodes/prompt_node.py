"""
Prompt node implementation using the BaseNode class.
"""

from typing import Any, Dict
import logging

from app.modules.workflow.engine.base_node import BaseNode


logger = logging.getLogger(__name__)


class TemplateNode(BaseNode):
    """Prompt template node using the BaseNode approach"""

    async def process(self, config: Dict[str, Any]) -> str:
        """
        Process a prompt template node.

        Args:
            config: The resolved configuration for the node

        Returns:
            The processed prompt string
        """
        logger.info("TemplateNode processing")

        # Get configuration values (already resolved by BaseNode)
        template = config.get("template", "")

        return template
