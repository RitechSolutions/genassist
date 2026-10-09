"""
Knowledge tool node implementation using the BaseNode class.
"""

from typing import Dict, Any, List
import logging

from app.modules.workflow.engine.base_node import BaseNode
from app.modules.workflow.engine.node_result import node_failure
from app.modules.data.manager import AgentRAGServiceManager
from app.modules.data.providers import SearchResult
from app.modules.data.utils.doc import format_search_results
from app.services.agent_knowledge import KnowledgeBaseService

logger = logging.getLogger(__name__)


def summarize_sources(results: List[SearchResult]) -> List[Dict[str, Any]]:
    """Article references for the response log, the content is left out"""
    return [
        {
            "id": result.id,
            "title": result.metadata.get("name") or None,
            "score": result.score,
            "source": result.source,
            "kb_id": result.metadata.get("kb_id"),
        }
        for result in results
    ]


class KnowledgeToolNode(BaseNode):
    """Knowledge tool node using the BaseNode approach"""

    async def process(self, config: Dict[str, Any]) -> Any:
        """
        Process a knowledge tool node using inputs from connected nodes.

        Args:
            config: The resolved configuration for the node

        Returns:
            Dictionary with knowledge base query results
        """
        selected_bases = config.get("selectedBases", [])
        query = config.get("query", "What information do you have?")
        limit = config.get("limit", 5)
        force_limit = config.get("force", False)

        if not selected_bases:
            error_msg = "No knowledge bases selected for query"
            logger.error(error_msg)
            return node_failure(error_msg)

        try:
            result = await self._query_knowledge_base(selected_bases, query, limit, force_limit)
            return result

        except Exception as e:
            error_msg = f"Error processing knowledge tool: {str(e)}"
            logger.error(error_msg)
            return node_failure(error_msg)

    async def _query_knowledge_base(self, base_ids: List[str], query: str, limit: int = 5, force_limit: bool = False) -> str:
        """Query knowledge bases with the given query using simplified manager"""
        from app.dependencies.injector import injector

        knowledge_service = injector.get(KnowledgeBaseService)
        rag_manager = injector.get(AgentRAGServiceManager)

        try:
            knowledge_configs = await knowledge_service.get_by_ids(base_ids)

            # Search using simplified manager
            search_results = await rag_manager.search(knowledge_configs, query, limit=limit, format_results=False, force_limit=force_limit)
            self.state.annotate_node_execution(self.node_id, sources=summarize_sources(search_results))
            results = format_search_results(search_results, include_metadata=False)

            if results:
                return results
            else:
                return "No relevant information found in the knowledge bases."

        except Exception as e:
            # Propagate so process() records this as a node failure instead of
            # returning an error string that looks like a normal result.
            logger.error(f"Error querying knowledge base: {str(e)}")
            raise
