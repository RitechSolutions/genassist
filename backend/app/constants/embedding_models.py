"""
Centralized configuration for embedding models.
This is the single source of truth for all supported embedding models.
"""

from typing import List, Dict, TypedDict


class EmbeddingModelInfo(TypedDict):
    """Information about an embedding model"""
    value: str
    label: str
    dimensions: int
    description: str


# [DO NOT CHANGE THESE MODELS WITHOUT CHECKING IF THEY HAVE SAFETENSORS FORMAT IN HUGGINGFACE]
# https: // www.cve.org / CVERecord?id = CVE - 2025 - 14921
# Untrusted Data Remote Code Execution Vulnerability
# https: // www.cve.org / CVERecord?id = CVE - 2025 - 14927
# Code Injection Remote Code Execution Vulnerability
EMBEDDING_MODELS: List[EmbeddingModelInfo] = [
    {
        "value": "all-MiniLM-L6-v2",
        "label": "all-MiniLM-L6-v2 (Fast, 384 dim)",
        "dimensions": 384,
        "description": "Fast and efficient model, good for most use cases"
    },
    {
        "value": "all-mpnet-base-v2",
        "label": "all-mpnet-base-v2 (High quality, 768 dim)",
        "dimensions": 768,
        "description": "Higher quality embeddings, slower but more accurate"
    },
    {
        "value": "multi-qa-MiniLM-L6-cos-v1",
        "label": "multi-qa-MiniLM-L6-cos-v1 (Q&A optimized)",
        "dimensions": 384,
        "description": "Optimized for question-answering tasks"
    },
    {
        "value": "all-distilroberta-v1",
        "label": "all-distilroberta-v1 (Balanced)",
        "dimensions": 768,
        "description": "Balanced performance and quality"
    },
    {
        "value": "paraphrase-multilingual-MiniLM-L12-v2",
        "label": "paraphrase-multilingual-MiniLM-L12-v2 (Multilingual)",
        "dimensions": 384,
        "description": "Supports multiple languages"
    },
]

# Derived constants for different use cases

# List of allowed model names (short names without 'sentence-transformers/' prefix)
ALLOWED_MODEL_NAMES: List[str] = [model["value"] for model in EMBEDDING_MODELS]

# For download script - full HuggingFace model paths
MODELS_FOR_DOWNLOAD: List[str] = [
    f'sentence-transformers/{model["value"]}' for model in EMBEDDING_MODELS
]

# For form schemas - vector database options (short names)
FORM_OPTIONS_VECTOR: List[Dict[str, str]] = [
    {"value": model["value"], "label": model["label"]}
    for model in EMBEDDING_MODELS
]

# For form schemas - LEGRA options (full paths with sentence-transformers/ prefix)
FORM_OPTIONS_LEGRA: List[Dict[str, str]] = [
    {"value": f'sentence-transformers/{model["value"]}', "label": model["label"]}
    for model in EMBEDDING_MODELS
]

# Default model
DEFAULT_MODEL = "all-MiniLM-L6-v2"