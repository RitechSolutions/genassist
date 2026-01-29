"""
Centralized schema utilities for extracting default values from AGENT_RAG_FORM_SCHEMAS
"""

from typing import Any
from app.schemas.dynamic_form_schemas import AGENT_RAG_FORM_SCHEMAS_DICT


def get_schema_default(
    schema_section: str, field_name: str, fallback: Any = None
) -> Any:
    """
    Extract default value from AGENT_RAG_FORM_SCHEMAS for a specific field.

    Args:
        schema_section: The section name (e.g., "vector", "legra", "lightrag")
        field_name: The field name to get the default for
        fallback: Fallback value if field not found in schema

    Returns:
        The default value from schema or fallback
    """
    try:
        sections = AGENT_RAG_FORM_SCHEMAS_DICT[schema_section]["sections"]
        for section in sections:
            for field in section.get("fields", []):
                if field.get("name") == field_name:
                    return field.get("default", fallback)
    except (KeyError, TypeError):
        pass
    return fallback


def get_vector_default(field_name: str, fallback: Any = None) -> Any:
    """Get default value for vector configuration fields"""
    return get_schema_default("vector", field_name, fallback)


def get_legra_default(field_name: str, fallback: Any = None) -> Any:
    """Get default value for LEGRA configuration fields"""
    return get_schema_default("legra", field_name, fallback)


def get_lightrag_default(field_name: str, fallback: Any = None) -> Any:
    """Get default value for LightRAG configuration fields"""
    return get_schema_default("lightrag", field_name, fallback)


# Pre-defined default values for common fields
VECTOR_DEFAULTS = {
    "chunk_size": get_vector_default("chunk_size", 1000),
    "chunk_overlap": get_vector_default("chunk_overlap", 200),
    "chunk_strategy": get_vector_default("chunk_strategy", "recursive"),
    "chunk_separators": get_vector_default("chunk_separators", ""),
    "chunk_keep_separator": get_vector_default("chunk_keep_separator", True),
    "chunk_strip_whitespace": get_vector_default("chunk_strip_whitespace", True),
    "embedding_type": get_vector_default("embedding_type", "bedrock"),
    "embedding_model_name": get_vector_default(
        "embedding_model_name", "all-MiniLM-L6-v2"
    ),
    "embedding_model_id": get_vector_default(
        "embedding_model_id", "amazon.titan-embed-text-v2:0"
    ),
    "embedding_region_name": get_vector_default("embedding_region_name", "ca-central-1"),
    "embedding_device_type": get_vector_default("embedding_device_type", "cpu"),
    "embedding_batch_size": get_vector_default("embedding_batch_size", 32),
    "embedding_normalize_embeddings": get_vector_default(
        "embedding_normalize_embeddings", True
    ),
    "vector_db_type": get_vector_default("vector_db_type", "chroma"),
    "vector_db_collection_name": get_vector_default(
        "vector_db_collection_name", "default"
    ),
}

LEGRA_DEFAULTS = {
    "embedding_model": get_legra_default(
        "embedding_model", "sentence-transformers/all-MiniLM-L6-v2"
    ),
    "chunk_min_sentences": get_legra_default("chunk_min_sentences", 1),
    "chunk_max_sentences": get_legra_default("chunk_max_sentences", 30),
    "chunk_min_sentence_length": get_legra_default("chunk_min_sentence_length", 32),
    "graph_n_neighbors": get_legra_default("graph_n_neighbors", 10),
    "graph_distance_metric": get_legra_default("graph_distance_metric", "cosine"),
    "cluster_resolution": get_legra_default("cluster_resolution", 0.5),
    "generation_model": get_legra_default("generation_model", "gpt2"),
    "generation_max_tokens": get_legra_default("generation_max_tokens", 1024),
    "generation_use_gpu": get_legra_default("generation_use_gpu", False),
    "storage_working_directory": get_legra_default("storage_working_directory", None),
}

LIGHTRAG_DEFAULTS = {
    "working_directory": get_lightrag_default("working_directory", "lightrag_data"),
    "search_mode": get_lightrag_default("search_mode", "mix"),
    "embedding_func_name": get_lightrag_default("embedding_func_name", "openai_embed"),
    "llm_model_func_name": get_lightrag_default(
        "llm_model_func_name", "gpt_4o_mini_complete"
    ),
    "chunk_token_size": get_lightrag_default("chunk_token_size", 512),
    "chunk_overlap_token_size": get_lightrag_default("chunk_overlap_token_size", 50),
    "vector_storage": get_lightrag_default("vector_storage", "ChromaVectorDBStorage"),
    "embedding_batch_num": get_lightrag_default("embedding_batch_num", 32),
    "top_k": get_lightrag_default("top_k", 5),
    "response_type": get_lightrag_default("response_type", "Single Paragraph"),
}
