from typing import Dict, Any, List
import logging
from app.modules.agents.data.datasource_service import AgentDataSourceService
from app.modules.agents.workflow.base_processor import NodeProcessor
from app.services.agent_knowledge import KnowledgeBaseService


logger = logging.getLogger(__name__)


class KnowledgeToolNodeProcessor(NodeProcessor):

    
    async def _query_knowledge_base(self, base_ids: List[str], query: str) -> str:
        """Query knowledge bases with the given query"""
        knowledge_service = KnowledgeBaseService.get_instance()
        datasource_service = AgentDataSourceService.get_instance()
        try:
            knowledge_configs = await knowledge_service.get_by_ids(base_ids)
            datasource_results = await datasource_service.search_knowledge(
                query=query,
                docs_config=knowledge_configs,
                format_results=True
            )
            
            return datasource_results
        except Exception as e:
            logger.error(f"Error querying knowledge base: {str(e)}")
            return f"Error querying knowledge base: {str(e)}"
    
    async def process(self, input_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Process a knowledge tool node using inputs from connected nodes"""
        # Get base configuration
        node_config = self.get_node_config()
        # node_config = node_config.get("data", {})
        selected_bases = node_config.get("selectedBases", [])
        # Get query from connected nodes
       
        input_data = await self.get_process_input(input_data)
        
        query = ""
        
        # Extract query from input data
        if isinstance(input_data, str):
            query = input_data
        elif isinstance(input_data, dict) and "query" in input_data:
            query = input_data["query"]
        else:
            query = ""
        
        self.set_input(query)
        
        if not selected_bases:
            error_msg = "No knowledge bases selected for query"
            logger.error(error_msg)
            self.save_output(error_msg)
            return self.output
        
        try:
            # Query the knowledge base
            result = await self._query_knowledge_base(selected_bases, query)
            self.save_output(result)
            return result
        except Exception as e:
            error_msg = f"Error processing knowledge tool: {str(e)}"
            logger.error(error_msg)
            self.save_output(error_msg)
            return error_msg

