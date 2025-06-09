import asyncio
import logging
import os
from typing import Any, Dict, List, Optional

from app.schemas.agent_knowledge import KBBase, KBRead, RagConfigRead

from .datasource_factory import DataSourceFactory
from .providers.i_data_source_provider import DataSourceProvider

logger = logging.getLogger(__name__)


class AgentDataSourceService:
    """Service to manage different data sources based on configuration"""

    _instance = None

    @staticmethod
    def get_instance() -> "AgentDataSourceService":

        if AgentDataSourceService._instance is None:
            AgentDataSourceService._instance = AgentDataSourceService()
            logger.info("AgentDataSourceService instance created")
        return AgentDataSourceService._instance

    def __init__(self):
        self.providers = {}
        self.load_providers()
        asyncio.create_task(self.load_knowledge_base())

    def load_providers(self):
        """Load all available providers using the factory"""
        # Common chunking configuration
        chunk_size = int(os.environ.get("CHUNK_SIZE", "1000"))
        chunk_overlap = int(os.environ.get("CHUNK_OVERLAP", "200"))

        # Vector DB provider (Chroma)
        vector_config = {
            "provider": "chroma",
            "persist_directory": os.environ.get("CHROMA_PERSIST_DIR", "chroma_db"),
            "embedding_model": os.environ.get("EMBEDDING_MODEL", "all-MiniLM-L6-v2"),
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
        }
        vector_provider = DataSourceFactory.create_provider("vector_db", vector_config)
        if vector_provider:
            self.register_provider("vector_db", vector_provider)

        # Graph DB provider (Neo4j)
        graph_config = {
            "provider": "neo4j",
            "uri": os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
            "username": os.environ.get("NEO4J_USER", "neo4j"),
            "password": os.environ.get("NEO4J_PASSWORD", "password"),
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
        }
        graph_provider = DataSourceFactory.create_provider("graph_db", graph_config)
        if graph_provider:
            self.register_provider("graph_db", graph_provider)

        # LightRAG provider
        light_rag_config = {
            "working_dir": os.environ.get("LIGHTRAG_WORKING_DIR", "lightrag_data"),
            "openai_api_key": os.environ.get("OPENAI_API_KEY"),
            "embedding_model": os.environ.get(
                "LIGHTRAG_EMBEDDING_MODEL", "text-embedding-ada-002"
            ),
            "llm_model": os.environ.get("LIGHTRAG_LLM_MODEL", "gpt-3.5-turbo"),
            "search_mode": os.environ.get("LIGHTRAG_SEARCH_MODE", "mix"),
        }
        light_rag_provider = DataSourceFactory.create_provider(
            "light_rag", light_rag_config
        )
        if light_rag_provider:
            self.register_provider("light_rag", light_rag_provider)

    def register_provider(self, name: str, provider: DataSourceProvider):
        """Register a new provider"""
        self.providers[name] = provider
        logger.info(f"Registered data source provider: {name}")

    def get_provider(self, name: str) -> Optional[DataSourceProvider]:
        """Get a provider by name"""
        return self.providers.get(name)

    async def get_document_ids(self, kb: KBRead) -> List[str]:
        """Get all document IDs for a given knowledge base ID"""
        logger.info(f"get_document_ids : kb.id = {kb.id}")

        if kb.rag_config.vector_db.get("enabled", False):
            vector_provider = self.get_provider("vector_db")
            if vector_provider:
                return await vector_provider.get_document_ids(str(kb.id))

        if kb.rag_config.graph_db.get("enabled", False):
            graph_provider = self.get_provider("graph_db")
            if graph_provider:
                return await graph_provider.get_document_ids(str(kb.id))

        if kb.rag_config.light_rag.get("enabled", False):
            light_rag_provider = self.get_provider("light_rag")
            if light_rag_provider:
                return await light_rag_provider.get_document_ids(str(kb.id))

        logger.error("No provider available for the given knowledge base")
        return []

    async def process_document(
        self,
        doc_id: str,
        content: str,
        metadata: Dict[str, Any],
        rag_config: RagConfigRead,
    ) -> Dict[str, bool]:

        doc_id = str(doc_id)

        """Process a document according to its RAG configuration"""
        results = {}
        logger.info(f"process_document {doc_id} :  rag_config = {rag_config}")
        logger.info(f"process_document {doc_id} :  content = {content}")
        logger.info(f"process_document {doc_id} :  metadata = {metadata}")

        # if not rag_config.enabled:
        #     logger.info(f"RAG not enabled for document {doc_id}")
        #     return {"success": False, "reason": "RAG not enabled"}

        # Process for vector database if enabled
        if rag_config.vector_db.get("enabled", False):
            vector_provider = self.get_provider("vector_db")
            if vector_provider:
                success = await vector_provider.add_document(doc_id, content, metadata)
                results["vector_db"] = success
            else:
                results["vector_db"] = False
                logger.error("Vector DB provider not available")

        # Process for graph database if enabled
        if rag_config.graph_db.get("enabled", False):
            graph_provider = self.get_provider("graph_db")
            if graph_provider:
                success = await graph_provider.add_document(doc_id, content, metadata)
                results["graph_db"] = success
            else:
                results["graph_db"] = False
                logger.error("Graph DB provider not available")

        # Process for LightRAG if enabled
        if rag_config.light_rag.get("enabled", False):
            light_rag_provider = self.get_provider("light_rag")
            if light_rag_provider:
                logger.info(
                    "TRYING TO ADD DOCUMENT in LIGHTRAG PROVIDER process_document : light_rag_provider"
                )
                success = await light_rag_provider.add_document(
                    doc_id, content, metadata
                )
                results["light_rag"] = success
                logger.info(
                    "ADDED DOCUMENT  {}\n{}\n{}".format(doc_id, content, metadata)
                )
                logger.info(success)
            else:
                results["light_rag"] = False
                logger.error("LightRAG provider not available")

        return results

    async def load_knowledge_base(self, knowledge_items: List[KBRead] = []):
        """Load and process all documents in the knowledge base"""
        try:
            logger.info(
                f"load_knowledge_base : selected_knowledge_items inside = {knowledge_items}"
            )
            # try:
            results = []
            logger.info(
                "Looping KB load_knowledge_base in path : knowledge_items: {}".format(
                    knowledge_items
                )
            )
            for kbitem in knowledge_items:
                doc_id = f"KB:{str(kbitem.id)}#content"
                content = kbitem.content

                # Handle file-based content
                if kbitem.type == "file" and kbitem.file:
                    file_path = kbitem.file
                    doc_id = f"KB:{str(kbitem.id)}#{file_path}"
                    if os.path.exists(file_path):
                        with open(file_path, "r") as f:
                            content = f.read()
                rag_config = kbitem.rag_config

                metadata = {
                    "name": kbitem.name,
                    "description": kbitem.description,
                    "id": doc_id,
                    "kb_id": str(kbitem.id),
                }

                result = await self.process_document(
                    doc_id, content, metadata, rag_config
                )
                results.append({"id": doc_id, "result": result})

            return results
        except Exception as e:
            logger.error(f"Error loading knowledge base: {str(e)}")
            return []

    def _format_results(self, search_results: List[Dict[str, Any]]) -> str:
        """Format knowledge search results"""
        logger.info("search_knowledge_base")
        try:
            if not search_results:
                return None

            # Format the results
            formatted_results = []
            for result in search_results:
                formatted_results.append(
                    f"--- Document: {result.get('metadata', {}).get('name', 'Unnamed')} ---\n"
                    f"{result.get('content', '')}\n"
                )
            logger.info("search_knowledge_tool : formatted_results")
            logger.info(formatted_results)
            return (
                "Here is the relevant information from the knowledge base:\n\n"
                + "\n".join(formatted_results)
            )
        except Exception as e:
            logger.error(f"Error searching knowledge base: {str(e)}")
            return None

    async def search_knowledge(
        self,
        query: str,
        limit: int = 5,
        docs_config: List[KBRead] = [],
        format_results: bool = False,
    ) -> List[Dict[str, Any] | str]:
        """Search the knowledge base using available data sources

        Args:
            query: The search query
            limit: Maximum number of results to return
            doc_ids: Optional list of document IDs to restrict the search to
        """
        results = []

        doc_ids = [str(doc.id) for doc in docs_config]
        
        search_vector = [doc  for doc in docs_config if doc.rag_config.vector_db.get("enabled", False)]
        search_vector_doc_ids = [str(doc.id) for doc in search_vector]

        search_graph = [doc  for doc in docs_config if doc.rag_config.graph_db.get("enabled", False)]
        search_graph_doc_ids = [str(doc.id) for doc in search_graph]

        search_light_rag = [doc  for doc in docs_config if doc.rag_config.light_rag.get("enabled", False)]
        search_light_rag_doc_ids = [str(doc.id) for doc in search_light_rag]
        
        no_rag = [doc  for doc in docs_config if not (doc.rag_config.light_rag.get("enabled", False) or doc.rag_config.graph_db.get("enabled", False) or doc.rag_config.vector_db.get("enabled", False))]
        
        
        logger.info(
            f"search_knowledge : search_vector = {search_vector}, search_graph = {search_graph}, search_light_rag = {search_light_rag} doc_ids = {doc_ids}"
        )

        logger.info("Entered datasource_service.search_knowledge")
        
        

        # Search vector DB if available
        vector_provider = self.get_provider("vector_db")
        if vector_provider and len(search_vector_doc_ids) > 0:
            vector_results = await vector_provider.search(query, limit, search_vector_doc_ids)
            results.extend(vector_results)
            logger.info("search_knowledge : vector_results")
            logger.info(vector_results)

        # Search graph DB if available
        graph_provider = self.get_provider("graph_db")
        if graph_provider and len(search_graph_doc_ids) > 0:
            graph_results = await graph_provider.search(query, limit, search_graph_doc_ids)

            logger.info("search_knowledge : graph_results")
            logger.info(graph_results)

            # Merge results, avoiding duplicates
            existing_ids = {r["id"] for r in results}
            for result in graph_results:
                if result["id"] not in existing_ids:
                    results.append(result)
                    existing_ids.add(result["id"])


        # Search LightRAG if available
        light_rag_provider = self.get_provider("light_rag")

        if light_rag_provider and len(search_light_rag_doc_ids) > 0:
            light_rag_results = await light_rag_provider.search(query, limit, search_light_rag_doc_ids)
            print(" searchlight_rag_results : ", light_rag_results)
            logger.info("search_knowledge : light_rag_results")
            logger.info(light_rag_results)
            # Merge results, avoiding duplicates
            existing_ids = {r["id"] for r in results}
            for result in light_rag_results:
                if result["id"] not in existing_ids:
                    results.append(result)
                    existing_ids.add(result["id"])

        if len(no_rag) > 0:
            logger.info("search_knowledge : no_rag")
            logger.info(no_rag)
            for kbitem in no_rag:
                doc_id = f"KB:{str(kbitem.id)}#content"
                content = kbitem.content

                # Handle file-based content
                if kbitem.type == "file" and kbitem.file:
                    file_path = kbitem.file
                    doc_id = f"KB:{str(kbitem.id)}#{file_path}"
                    if os.path.exists(file_path):
                        with open(file_path, "r") as f:
                            content = f.read()
                results.append({
                        "id": doc_id,
                        "content": content,
                        "metadata": {
                        },
                        "score": 1,
                        "chunk_count": 1,
                    })
        # Sort by score and limit results
        results.sort(key=lambda x: x.get("score", 0), reverse=True)
        if format_results:
            return self._format_results(results)
        return results[:limit]

    async def delete_kb(self, kb: KBRead):
        """Delete a knowledge base item"""

        ids = await self.get_document_ids(kb)
        for item_id in ids:
            await self.delete_doc(kb, doc_id=item_id)

    async def delete_doc(self, kb: KBRead, doc_id: str):
        """Delete a knowledge base item"""

        #check if the document ID is in the format "KB:{kb_id}#{doc_id}"
        if not doc_id.startswith("KB:"):
             doc_id = f"KB:{kb.id}#{doc_id}"

        vector_provider = self.get_provider("vector_db")
        if kb.rag_config.vector_db.get("enabled", False) and vector_provider:
            await vector_provider.delete_document(doc_id)

        graph_provider = self.get_provider("graph_db")
        if kb.rag_config.graph_db.get("enabled", False) and graph_provider:
            await graph_provider.delete_document(doc_id)
            
        light_rag_provider = self.get_provider("light_rag")
        if kb.rag_config.light_rag.get("enabled", False) and light_rag_provider:
            await light_rag_provider.delete_document(doc_id)
