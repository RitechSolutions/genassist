import json
import os
from typing import Dict, List, Any, Optional
import logging
from .datasource_factory import DataSourceFactory
from .providers.i_data_source_provider import DataSourceProvider
from app.genagent.models.knowledge import KnowledgeItem
logger = logging.getLogger(__name__)


class DataSourceService:
    """Service to manage different data sources based on configuration"""
    
    def __init__(self):
        self.providers = {}
        self.load_providers()
    
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
            "chunk_overlap": chunk_overlap
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
            "chunk_overlap": chunk_overlap
        }
        graph_provider = DataSourceFactory.create_provider("graph_db", graph_config)
        if graph_provider:
            self.register_provider("graph_db", graph_provider)
            
        # LightRAG provider
        light_rag_config = {
            "working_dir": os.environ.get("LIGHTRAG_WORKING_DIR", "lightrag_data"),
            "openai_api_key": os.environ.get("OPENAI_API_KEY"),
            "embedding_model": os.environ.get("LIGHTRAG_EMBEDDING_MODEL", "text-embedding-ada-002"),
            "llm_model": os.environ.get("LIGHTRAG_LLM_MODEL", "gpt-3.5-turbo"),
            "search_mode": os.environ.get("LIGHTRAG_SEARCH_MODE", "mix")
        }
        light_rag_provider = DataSourceFactory.create_provider("light_rag", light_rag_config)
        if light_rag_provider:
            self.register_provider("light_rag", light_rag_provider)
    
    def register_provider(self, name: str, provider: DataSourceProvider):
        """Register a new provider"""
        self.providers[name] = provider
        logger.info(f"Registered data source provider: {name}")
    
    def get_provider(self, name: str) -> Optional[DataSourceProvider]:
        """Get a provider by name"""
        return self.providers.get(name)
    
    async def process_document(self, doc_id: str, content: str, metadata: Dict[str, Any], 
                         rag_config: Dict[str, Any]) -> Dict[str, bool]:
        
        """Process a document according to its RAG configuration"""
        results = {}
        logger.info(f"process_document {doc_id} :  rag_config = {rag_config}")

        if not rag_config.get("enabled", False):
            logger.info(f"RAG not enabled for document {doc_id}")
            return {"success": False, "reason": "RAG not enabled"}
        
        # Process for vector database if enabled
        if rag_config.get("vector_db", {}).get("enabled", False):
            vector_provider = self.get_provider("vector_db")
            if vector_provider:
                success = vector_provider.add_document(doc_id, content, metadata)
                results["vector_db"] = success
            else:
                results["vector_db"] = False
                logger.error("Vector DB provider not available")
        
        # Process for graph database if enabled
        if rag_config.get("graph_db", {}).get("enabled", False):
            graph_provider = self.get_provider("graph_db")
            if graph_provider:
                success = graph_provider.add_document(doc_id, content, metadata)
                results["graph_db"] = success
            else:
                results["graph_db"] = False
                logger.error("Graph DB provider not available")
        
        # Process for LightRAG if enabled
        if rag_config.get("light_rag", {}).get("enabled", False):
            light_rag_provider = self.get_provider("light_rag")
            if light_rag_provider:
                logger.info("TRYING TO ADD DOCUMENT in LIGHTRAG PROVIDER process_document : light_rag_provider")
                success = await light_rag_provider.add_document(doc_id, content, metadata)
                results["light_rag"] = success
                logger.info("ADDED DOCUMENT  {}\n{}\n{}".format(doc_id, content, metadata))
                logger.info(success)
            else:
                results["light_rag"] = False
                logger.error("LightRAG provider not available")
        
        return results
    
    async def load_knowledge_base(self, selected_knowledge_items: List[KnowledgeItem] = []):
        """Load and process all documents in the knowledge base"""
        try:
            logger.info(f"load_knowledge_base : selected_knowledge_items inside = {selected_knowledge_items}")
            # try:
            knowledge_items = selected_knowledge_items
            
            results = []
            logger.info("Looping KB load_knowledge_base in path : knowledge_items: {}".format(knowledge_items))
            for item in knowledge_items:
                doc_id = item.id
                content = item.content
                
                # Handle file-based content
                if item.type == "file" and item.file:
                    file_path = item.file
                    if os.path.exists(file_path):
                        with open(file_path, 'r') as f:
                            content = f.read()
                rag_config = item.rag_config

                metadata = {
                    "name": item.name,
                    "description": item.description,
                    "id": doc_id
                }
                
                rag_config = item.rag_config
                result = await self.process_document(doc_id, content, metadata, rag_config)
                results.append({
                    "id": doc_id,
                    "result": result
                })
            
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
            return "Here is the relevant information from the knowledge base:\n\n" + "\n".join(formatted_results)
        except Exception as e:
            logger.error(f"Error searching knowledge base: {str(e)}")
            return None
    
    
    async def search_knowledge(self, query: str, limit: int = 5, docs_config: List[KnowledgeItem] = [], format_results: bool = False) -> List[Dict[str, Any] | str]:
        """Search the knowledge base using available data sources
        
        Args:
            query: The search query
            limit: Maximum number of results to return
            doc_ids: Optional list of document IDs to restrict the search to    
        """
        results = []

        doc_ids = [doc.id for doc in docs_config]
        search_vector = any(doc.rag_config.get("vector_db", {}).get("enabled", False) for doc in docs_config)
        search_graph = any(doc.rag_config.get("graph_db", {}).get("enabled", False) for doc in docs_config)
        search_light_rag = any(doc.rag_config.get("light_rag", {}).get("enabled", False) for doc in docs_config)
        logger.info(f"search_knowledge : search_vector = {search_vector}, search_graph = {search_graph}, search_light_rag = {search_light_rag} doc_ids = {doc_ids}")

        
        logger.info("Entered datasource_service.search_knowledge")
        

        # Search vector DB if available
        vector_provider = self.get_provider("vector_db")
        if vector_provider and search_vector:
            vector_results = await vector_provider.search(query, limit, doc_ids)                
            results.extend(vector_results)
            logger.info("search_knowledge : vector_results")
            logger.info(vector_results)
        
        # Search graph DB if available
        graph_provider = self.get_provider("graph_db")
        if graph_provider and search_graph:
            graph_results = await graph_provider.search(query, limit, doc_ids)
            
            logger.info("search_knowledge : graph_results")
            logger.info(graph_results)
            
            # Merge results, avoiding duplicates
            existing_ids = {r["id"] for r in results}
            for result in graph_results:
                if result["id"] not in existing_ids:
                    results.append(result)
                    existing_ids.add(result["id"])
                    
                    
        print("query : ",query)
        print("limit : ",limit)
        print("doc_ids : ",doc_ids)
        print("provider:",self.get_provider("light_rag"))
        # Search LightRAG if available
        light_rag_provider = self.get_provider("light_rag")

        if light_rag_provider and search_light_rag:
            light_rag_results = await light_rag_provider.search(query, limit, doc_ids)
            print(" searchlight_rag_results : ",light_rag_results)

            logger.info("search_knowledge : light_rag_results")
            logger.info(light_rag_results)
            
            # Merge results, avoiding duplicates
            existing_ids = {r["id"] for r in results}
            for result in light_rag_results:
                if result["id"] not in existing_ids:
                    results.append(result)
                    existing_ids.add(result["id"])
        
        # Sort by score and limit results
        results.sort(key=lambda x: x.get("score", 0), reverse=True)
        if format_results:
            return self._format_results(results)
        return results[:limit]  
    
    
    async def delete_knowledge_base_item(self, item_id: str):
        """Delete a knowledge base item"""
            
        vector_provider = self.get_provider("vector_db")
        if vector_provider:
            vector_provider.delete_document(item_id)
        graph_provider = self.get_provider("graph_db")
        if graph_provider:
            graph_provider.delete_document(item_id)
        light_rag_provider = self.get_provider("light_rag")
        if light_rag_provider:
            light_rag_provider.delete_document(item_id)
            
