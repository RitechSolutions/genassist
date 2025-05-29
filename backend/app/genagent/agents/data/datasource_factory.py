from typing import Dict, Any, Optional
import logging
from .providers.i_data_source_provider import DataSourceProvider
from .providers.vector_db_provider import VectorDBProvider
from .providers.graph_db_provider import GraphDBProvider
from .providers.light_rag_provider import LightRAGProvider

logger = logging.getLogger(__name__)

class DataSourceFactory:
    """Factory for creating data source providers"""
    
    @staticmethod
    def create_provider(provider_type: str, config: Dict[str, Any] = None) -> Optional[DataSourceProvider]:
        """
        Create a data source provider based on type and configuration
        
        Args:
            provider_type: Type of provider ('vector_db', 'graph_db', etc.)
            config: Configuration parameters for the provider
        
        Returns:
            DataSourceProvider instance or None if provider type is not supported
        """
        if not config:
            config = {}
        
        if provider_type == "vector_db":
            provider_name = config.get("provider", "chroma")
            
            if provider_name == "chroma":
                persist_dir = config.get("persist_directory", "chroma_db")
                embedding_model = config.get("embedding_model", "all-MiniLM-L6-v2")
                chunk_size = config.get("chunk_size", 1000)
                chunk_overlap = config.get("chunk_overlap", 200)
                
                return VectorDBProvider(
                    persist_directory=persist_dir,
                    embedding_model_name=embedding_model,
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap
                )
            # Add more vector DB providers here as needed
            # elif provider_name == "pinecone":
            #     return PineconeVectorDBProvider(...)
            else:
                logger.error(f"Unsupported vector DB provider: {provider_name}")
                return None
                
        elif provider_type == "graph_db":
            provider_name = config.get("provider", "neo4j")
            
            if provider_name == "neo4j":
                uri = config.get("uri", "bolt://localhost:7687")
                username = config.get("username", "neo4j")
                password = config.get("password", "password")
                chunk_size = config.get("chunk_size", 1000)
                chunk_overlap = config.get("chunk_overlap", 200)
                
                return GraphDBProvider(
                    uri=uri, 
                    username=username, 
                    password=password,
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap
                )
            # Add more graph DB providers here as needed
            # elif provider_name == "tigergraph":
            #     return TigerGraphProvider(...)
            else:
                logger.error(f"Unsupported graph DB provider: {provider_name}")
                return None
        
        elif provider_type == "light_rag":
            return LightRAGProvider()
        
        else:
            logger.error(f"Unsupported provider type: {provider_type}")
            return None 