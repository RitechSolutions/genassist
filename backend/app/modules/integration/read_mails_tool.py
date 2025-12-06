from typing import Dict, Any, List, TYPE_CHECKING
import logging
from app.modules.agents.data.datasource_service import AgentDataSourceService
from app.modules.agents.workflow.base_processor import NodeProcessor
from app.services.agent_knowledge import KnowledgeBaseService
from .gmail_connector import GmailConnector

if TYPE_CHECKING:
    from app.modules.agents.workflow.builder import  WorkflowContext

logger = logging.getLogger(__name__)

class ReadMailsToolProcessor(NodeProcessor):
    """Processor for reading emails from a mailbox using the Gmail API"""

    def __init__(self, context: 'WorkflowContext', node_id: str, node_config: Dict[str, Any]):
        super().__init__(context, node_id, node_config)
        logger.info(f"Node config: {node_config}")
        ds_id = node_config.get('data').get("dataSourceId", None)
        self.gmail_connector = GmailConnector(ds_id)

    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process the node to read emails from the mailbox"""
        logger.info(f"Input data : {input_data}")
        try:
            search_criteria = input_data.get("searchCriteria", None)
            
            logger.info(f"Search criteria : {search_criteria}")
            # If search criteria is provided, use it to filter emails
            emails = await self.gmail_connector.search_emails(search_criteria)
            self.save_output(emails)
            
            return {
                "status": 200,
                "data": {
                    "emails": emails
                }
            }
        
        except Exception as e:
            logger.error(f"Error processing ReadMailsToolProcessor: {e}")
            return {
                "status": 500,
                "data": {"error": str(e)}
            }
        