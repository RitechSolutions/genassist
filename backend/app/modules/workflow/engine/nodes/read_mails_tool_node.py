"""
Read mails tool node implementation using the BaseNode class.
"""

from typing import Dict, Any
import logging

from app.modules.workflow.engine.base_node import BaseNode
from app.modules.integration.gmail_connector import GmailConnector

logger = logging.getLogger(__name__)


class ReadMailsToolNode(BaseNode):
    """Processor for reading emails from a mailbox using the BaseNode approach"""

    async def process(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process the node to read emails from the mailbox.

        Args:
            config: The resolved configuration for the node

        Returns:
            Dictionary with email data or error information
        """

        try:
            ds_id = config.get('data').get("dataSourceId", None)
            gmail_connector = GmailConnector(ds_id)
            search_criteria = config.get("searchCriteria", None)

            logger.info(f"Search criteria : {search_criteria}")
            # If search criteria is provided, use it to filter emails
            emails = await gmail_connector.search_emails(search_criteria)

            return {
                "status": 200,
                "data": emails
            }

        except Exception as e:
            logger.error(f"Error processing ReadMailsToolProcessor: {e}")
            return {
                "status": 500,
                "error": str(e)
            }
