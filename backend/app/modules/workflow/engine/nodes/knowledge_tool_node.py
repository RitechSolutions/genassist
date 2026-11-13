"""
Knowledge tool node implementation using the BaseNode class.
"""

from typing import Dict, Any, List, Optional, Tuple
from uuid import UUID
import logging

from app.modules.workflow.engine.base_node import BaseNode
from app.modules.workflow.engine.node_result import node_failure
from app.modules.data.manager import AgentRAGServiceManager
from app.modules.data.providers import KnowledgeSearchError, SearchResult
from app.modules.data.service import capped_failure_text, error_type_names
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


def comparable_id(value: Any) -> Any:
    """The id as a UUID, so its spelling does not matter; other text is compared as written"""
    try:
        return UUID(str(value))
    except ValueError:
        return str(value)


def missing_base_ids(base_ids: List[str], found_bases: List[Any]) -> List[str]:
    """The selected ids that no longer point at a knowledge base"""
    found_ids = {comparable_id(knowledge_base.id) for knowledge_base in found_bases}
    return [str(base_id) for base_id in base_ids if comparable_id(base_id) not in found_ids]


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
        limit = config.get("limit") or 5
        force_limit = config.get("force", False)

        if not selected_bases:
            error_msg = "No knowledge bases selected for query"
            logger.error(error_msg)
            return node_failure(error_msg)

        try:
            result = await self._query_knowledge_base(selected_bases, query, limit, force_limit)
            return result

        except Exception as e:
            error_msg = f"Error processing knowledge tool: {capped_failure_text(str(e))}"
            logger.error(f"{error_msg} [{error_type_names(e)}]")
            return node_failure(error_msg)

    async def _query_knowledge_base(self, base_ids: List[str], query: str, limit: int = 5, force_limit: bool = False) -> str:
        """Query knowledge bases with the given query using simplified manager"""
        from app.dependencies.injector import injector

        knowledge_service = injector.get(KnowledgeBaseService)
        rag_manager = injector.get(AgentRAGServiceManager)

        knowledge_configs = await knowledge_service.get_by_ids(base_ids)
        missing_ids = missing_base_ids(base_ids, knowledge_configs)
        if not knowledge_configs:
            raise KnowledgeSearchError(
                f"none of the selected knowledge bases exists any more (ids: {', '.join(missing_ids)})"
            )

        search_results, search_error = await self._search(rag_manager, knowledge_configs, query, limit, force_limit)
        self._record_search_problems(missing_ids, search_error)
        self.state.annotate_node_execution(self.node_id, sources=summarize_sources(search_results))
        return format_search_results(search_results, include_metadata=False)

    async def _search(
        self, rag_manager: AgentRAGServiceManager, knowledge_bases: List[Any], query: str, limit: int, force_limit: bool
    ) -> Tuple[List[SearchResult], Optional[KnowledgeSearchError]]:
        """The results, with the error when part of the search failed; a failure that left no results is raised"""
        try:
            results = await rag_manager.search(
                knowledge_bases, query, limit=limit, format_results=False, force_limit=force_limit
            )
            return results, None
        except KnowledgeSearchError as error:
            if not error.results:
                raise
            return error.results, error

    def _record_search_problems(self, missing_ids: List[str], search_error: Optional[KnowledgeSearchError]) -> None:
        """Notes skipped knowledge bases and a partly failed search on the node run"""
        warnings = []
        if missing_ids:
            warnings.append(capped_failure_text(f"Knowledge bases not found and skipped: {', '.join(missing_ids)}"))
        if search_error:
            incomplete_search = f"Knowledge search incomplete. {capped_failure_text(str(search_error))}"
            warnings.append(incomplete_search)
            # The run status and its failed-step list read this note; the step details read the warnings.
            self.state.annotate_node_execution(self.node_id, partial_failure=incomplete_search)
        if warnings:
            error_types = f" [{error_type_names(search_error)}]" if search_error else ""
            logger.warning(f"Knowledge tool {self.node_id}: {' '.join(warnings)}{error_types}")
            self.state.annotate_node_execution(self.node_id, warnings=warnings)
