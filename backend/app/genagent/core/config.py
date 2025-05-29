from pydantic import Field, field_validator
from pydantic_settings import BaseSettings
from functools import lru_cache
import os
from dotenv import load_dotenv
from typing import Dict, Any, Optional, List

# Load environment variables from .env file
load_dotenv()

class Settings(BaseSettings):
    """Application settings"""
    
    # Basic application settings
    app_name: str = "GenAgent Service"
    version: str = "0.1.0"
    environment: str = "development"
    debug: bool = True
    
    # API settings
    api_prefix: str = "/api"
    
    # OpenAI settings
    openai_api_key: Optional[str] = None
    
    # Anthropic settings
    anthropic_api_key: Optional[str] = None
    
    # Pinecone settings
    pinecone_api_key: Optional[str] = None
    pinecone_environment: Optional[str] = None
    
    # RAG settings
    rag_vector_db_type: Optional[str] = None
    rag_chroma_persist_directory: Optional[str] = None
    rag_chroma_collection_name: Optional[str] = None
    rag_chroma_host: Optional[str] = None
    rag_chroma_port: Optional[int] = None
    
    rag_graph_db_type: Optional[str] = None
    rag_neo4j_url: Optional[str] = None
    rag_neo4j_username: Optional[str] = None
    rag_neo4j_password: Optional[str] = None
    rag_neo4j_database: Optional[str] = None
    
    rag_embedding_type: Optional[str] = None
    rag_huggingface_model_name: Optional[str] = None
    
    rag_top_k: Optional[int] = 5
    rag_chunk_size: Optional[int] = 500
    rag_chunk_overlap: Optional[int] = 100
    
    # Ollama settings
    ollama_host: Optional[str] = None
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        
    @field_validator('*')
    def check_empty_strings(cls, v, info):
        if isinstance(v, str) and v == "":
            return None
        return v
    
    def get_rag_config(self) -> Dict[str, Any]:
        """Get RAG configuration as a dictionary"""
        return {
            "vector_db_type": self.rag_vector_db_type,
            "chroma_persist_directory": self.rag_chroma_persist_directory,
            "chroma_collection_name": self.rag_chroma_collection_name,
            "chroma_host": self.rag_chroma_host,
            "chroma_port": self.rag_chroma_port,
            "graph_db_type": self.rag_graph_db_type,
            "neo4j_url": self.rag_neo4j_url,
            "neo4j_username": self.rag_neo4j_username,
            "neo4j_password": self.rag_neo4j_password,
            "neo4j_database": self.rag_neo4j_database,
            "embedding_type": self.rag_embedding_type,
            "huggingface_model_name": self.rag_huggingface_model_name,
            "top_k": self.rag_top_k,
            "chunk_size": self.rag_chunk_size,
            "chunk_overlap": self.rag_chunk_overlap,
        }


@lru_cache()
def get_settings() -> Settings:
    """Get application settings"""
    return Settings()


def get_rag_defaults() -> Dict[str, Any]:
    """Get default RAG configuration values as a dictionary."""
    settings = get_settings()
    
    return {
        # Vector DB defaults
        "vector_db": {
            "type": settings.rag_vector_db_type,
            "chroma": {
                "persist_directory": settings.rag_chroma_persist_directory,
                "collection_name": settings.rag_chroma_collection_name,
                "host": settings.rag_chroma_host,
                "port": settings.rag_chroma_port,
            },
            "faiss": {
                "index_name": "default", #settings.faiss_index_name,
            },
            "pinecone": {
                "index_name": "default", #settings.pinecone_index_name,
                "api_key": settings.pinecone_api_key,
                "environment": settings.pinecone_environment,
            },
            "embeddings": {
                "type": settings.rag_embedding_type,
                "model_name": settings.rag_huggingface_model_name,
            },
        },
        
        # Graph DB defaults
        "graph_db": {
            "type": settings.rag_graph_db_type,
            "neo4j": {
                "url": settings.rag_neo4j_url,
                "username": settings.rag_neo4j_username,
                "password": settings.rag_neo4j_password,
                "database": settings.rag_neo4j_database,
            },
        },
        
        # Retrieval defaults
        "retrieval": {
            "top_k": settings.rag_top_k,
            "chunk_size": settings.rag_chunk_size,
            "chunk_overlap": settings.rag_chunk_overlap,
        },
    } 