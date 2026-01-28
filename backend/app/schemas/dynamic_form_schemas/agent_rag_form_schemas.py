"""
Agent RAG configuration schemas.

This module defines form schemas for configuring AgentRAGService instances,
including vector and LEGRA provider configurations.
All schemas use the unified TypeSchema structure from base.py.
"""

from typing import Dict
from .base import FieldSchema, SectionSchema, TypeSchema
from .base import convert_typed_schemas_to_dict
from app.constants.embedding_models import (
    FORM_OPTIONS_VECTOR,
    FORM_OPTIONS_LEGRA,
    DEFAULT_MODEL
)

# Define RAG schemas using direct Pydantic models
AGENT_RAG_FORM_SCHEMAS_VECTOR_AND_LEGRA: Dict[str, TypeSchema] = {
    "vector": TypeSchema(
        name="Vector Database",
        description="Use only vector database for semantic search",
        sections=[
            SectionSchema(
                name="vector_db",
                label="Vector Database",
                fields=[
                    FieldSchema(
                        name="vector_db_type",
                        type="select",
                        label="Database Type",
                        required=True,
                        default="chroma",
                        options=[
                            {"value": "chroma", "label": "ChromaDB"},
                            {"value": "pgvector", "label": "PostgreSQL (pgvector)"},
                            {"value": "qdrant", "label": "Qdrant"},
                        ],
                        description="Vector database backend",
                    ),
                    FieldSchema(
                        name="vector_db_collection_name",
                        type="text",
                        label="Collection Name",
                        required=False,
                        default="default",
                        description="Name of the vector collection (auto-generated if empty)",
                    ),
                ],
                conditional_fields={
                    "chroma": [
                        FieldSchema(
                            name="vector_db_host",
                            type="text",
                            label="ChromaDB Host",
                            required=False,
                            default="localhost",
                            description="ChromaDB server hostname",
                        ),
                        FieldSchema(
                            name="vector_db_port",
                            type="number",
                            label="ChromaDB Port",
                            required=False,
                            default=8000,
                            min=1,
                            max=65535,
                            description="ChromaDB server port",
                        ),
                    ],
                    "pgvector": [
                        FieldSchema(
                            name="vector_db_host",
                            type="text",
                            label="PostgreSQL Host",
                            required=False,
                            default="localhost",
                            description="PostgreSQL server hostname (uses existing DB connection if not specified)",
                        ),
                        FieldSchema(
                            name="vector_db_port",
                            type="number",
                            label="PostgreSQL Port",
                            required=False,
                            default=5432,
                            min=1,
                            max=65535,
                            description="PostgreSQL server port",
                        ),
                    ],
                    "qdrant": [
                        FieldSchema(
                            name="vector_db_host",
                            type="text",
                            label="Qdrant Host",
                            required=False,
                            default="localhost",
                            description="Qdrant server hostname (leave empty for local storage)",
                        ),
                        FieldSchema(
                            name="vector_db_port",
                            type="number",
                            label="Qdrant Port",
                            required=False,
                            default=6333,
                            min=1,
                            max=65535,
                            description="Qdrant server port",
                        ),
                        FieldSchema(
                            name="vector_db_persist_directory",
                            type="text",
                            label="Local Storage Path",
                            required=False,
                            description="Local directory for Qdrant data (if not using remote server)",
                        ),
                    ],
                },
            ),
            SectionSchema(
                name="chunking",
                label="Text Chunking",
                fields=[
                    FieldSchema(
                        name="chunk_strategy",
                        type="select",
                        label="Chunking Strategy",
                        required=True,
                        default="recursive",
                        options=[
                            {
                                "value": "recursive",
                                "label": "Recursive Character Text Splitter",
                            },
                            {"value": "semantic", "label": "Semantic Chunking"},
                            {
                                "value": "simple",
                                "label": "Simple Separator-based Chunking",
                            },
                        ],
                        description="Method used to split text into chunks",
                    )
                ],
                conditional_fields={
                    "recursive": [
                        FieldSchema(
                            name="chunk_size",
                            type="number",
                            label="Chunk Size",
                            required=True,
                            default=1000,
                            min=100,
                            max=8000,
                            step=100,
                            description="Size of text chunks in characters",
                        ),
                        FieldSchema(
                            name="chunk_overlap",
                            type="number",
                            label="Chunk Overlap",
                            required=True,
                            default=200,
                            min=0,
                            max=1000,
                            step=50,
                            description="Overlap between chunks in characters",
                        ),
                        FieldSchema(
                            name="chunk_separators",
                            type="text",
                            label="Text Separators",
                            required=True,
                            default="\\n\\n,\\n, ,",
                            description="Comma-separated list of text separators for recursive splitting (e.g., \\n\\n,\\n, ,). Leave empty for default separators.",
                        ),
                        FieldSchema(
                            name="chunk_keep_separator",
                            type="boolean",
                            label="Keep Separators",
                            required=True,
                            default=True,
                            description="Whether to keep the separator characters in the chunks",
                        ),
                        FieldSchema(
                            name="chunk_strip_whitespace",
                            type="boolean",
                            label="Strip Whitespace",
                            required=False,
                            default=True,
                            description="Whether to strip leading and trailing whitespace from chunks",
                        ),
                    ],
                    "semantic": [
                        FieldSchema(
                            name="chunk_size",
                            type="number",
                            label="Chunk Size",
                            required=True,
                            default=1000,
                            min=100,
                            max=8000,
                            step=100,
                            description="Maximum size of text chunks in characters",
                        ),
                        FieldSchema(
                            name="chunk_overlap",
                            type="number",
                            label="Chunk Overlap",
                            required=True,
                            default=200,
                            min=0,
                            max=1000,
                            step=50,
                            description="Overlap between chunks in characters for semantic continuity",
                        ),
                    ],
                    "simple": [
                        FieldSchema(
                            name="chunk_size",
                            type="number",
                            label="Chunk Size",
                            required=True,
                            default=1000,
                            min=100,
                            max=8000,
                            step=100,
                            description="Maximum size of text chunks in characters",
                        ),
                        FieldSchema(
                            name="chunk_separators",
                            type="text",
                            label="Text Separators",
                            required=True,
                            default=". ,! ,? , ",
                            description="Comma-separated list of text separators for simple splitting (e.g., '. ,! ,? , '). These separators will be tried in order.",
                        ),
                        FieldSchema(
                            name="chunk_keep_separator",
                            type="boolean",
                            label="Keep Separators",
                            required=False,
                            default=True,
                            description="Whether to keep the separator characters in the chunks",
                        ),
                        FieldSchema(
                            name="chunk_strip_whitespace",
                            type="boolean",
                            label="Strip Whitespace",
                            required=False,
                            default=True,
                            description="Whether to strip leading and trailing whitespace from chunks",
                        ),
                    ],
                },
            ),
            SectionSchema(
                name="embedding",
                label="Text Embedding",
                fields=[
                    FieldSchema(
                        name="embedding_model_name",
                        type="select",
                        label="Embedding Model",
                        required=True,
                        default=DEFAULT_MODEL,
                        options=FORM_OPTIONS_VECTOR,
                        description="HuggingFace model for generating embeddings",
                    ),
                    FieldSchema(
                        name="embedding_device_type",
                        type="select",
                        label="Device",
                        required=False,
                        default="cpu",
                        options=[
                            {"value": "cpu", "label": "CPU"},
                            {"value": "cuda", "label": "GPU (CUDA)"},
                            {"value": "mps", "label": "Apple Silicon (MPS)"},
                        ],
                        description="Device to use for embedding generation",
                    ),
                    FieldSchema(
                        name="embedding_batch_size",
                        type="number",
                        label="Batch Size",
                        required=False,
                        default=32,
                        min=1,
                        max=256,
                        step=1,
                        description="Batch size for embedding generation",
                    ),
                    FieldSchema(
                        name="embedding_normalize_embeddings",
                        type="boolean",
                        label="Normalize Embeddings",
                        required=False,
                        default=True,
                        description="Whether to normalize embedding vectors",
                    ),
                ],
            ),
        ],
    ),
    "legra": TypeSchema(
        name="LEGRA",
        description="Use only LEGRA for graph-based retrieval and generation",
        sections=[
            SectionSchema(
                name="embedding",
                label="Embedding Configuration",
                fields=[
                    FieldSchema(
                        name="embedding_model",
                        type="select",
                        label="Embedding Model",
                        required=True,
                        default=f"sentence-transformers/{DEFAULT_MODEL}",
                        options=FORM_OPTIONS_LEGRA,
                        description="Sentence transformer model for LEGRA embeddings",
                    )
                ],
            ),
            SectionSchema(
                name="chunking",
                label="Document Chunking",
                fields=[
                    FieldSchema(
                        name="chunk_min_sentences",
                        type="number",
                        label="Min Sentences",
                        required=False,
                        default=1,
                        min=1,
                        max=10,
                        step=1,
                        description="Minimum number of sentences per chunk",
                    ),
                    FieldSchema(
                        name="chunk_max_sentences",
                        type="number",
                        label="Max Sentences",
                        required=False,
                        default=30,
                        min=5,
                        max=100,
                        step=5,
                        description="Maximum number of sentences per chunk",
                    ),
                    FieldSchema(
                        name="chunk_min_sentence_length",
                        type="number",
                        label="Min Sentence Length",
                        required=False,
                        default=32,
                        min=10,
                        max=200,
                        step=5,
                        description="Minimum character length for sentences",
                    ),
                ],
            ),
            SectionSchema(
                name="graph",
                label="Graph Construction",
                fields=[
                    FieldSchema(
                        name="graph_n_neighbors",
                        type="number",
                        label="Number of Neighbors",
                        required=False,
                        default=10,
                        min=3,
                        max=50,
                        step=1,
                        description="Number of nearest neighbors for kNN graph",
                    ),
                    FieldSchema(
                        name="graph_distance_metric",
                        type="select",
                        label="Distance Metric",
                        required=False,
                        default="cosine",
                        options=[
                            {"value": "cosine", "label": "Cosine Distance"},
                            {"value": "euclidean", "label": "Euclidean Distance"},
                            {"value": "manhattan", "label": "Manhattan Distance"},
                        ],
                        description="Distance metric for graph construction",
                    ),
                ],
            ),
            SectionSchema(
                name="clustering",
                label="Community Detection",
                fields=[
                    FieldSchema(
                        name="cluster_resolution",
                        type="number",
                        label="Cluster Resolution",
                        required=False,
                        default=0.5,
                        min=0.1,
                        max=2.0,
                        step=0.1,
                        description="Resolution parameter for Leiden clustering",
                    )
                ],
            ),
            SectionSchema(
                name="generation",
                label="Text Generation",
                fields=[
                    FieldSchema(
                        name="generation_model",
                        type="select",
                        label="Generator Model",
                        required=False,
                        default="gpt2",
                        options=[
                            {"value": "gpt2", "label": "GPT-2 (Small, Fast)"},
                            {"value": "gpt2-medium", "label": "GPT-2 Medium"},
                            {"value": "gpt2-large", "label": "GPT-2 Large"},
                            {
                                "value": "microsoft/DialoGPT-medium",
                                "label": "DialoGPT Medium",
                            },
                            {
                                "value": "microsoft/DialoGPT-large",
                                "label": "DialoGPT Large",
                            },
                        ],
                        description="HuggingFace model for text generation",
                    ),
                    FieldSchema(
                        name="generation_max_tokens",
                        type="number",
                        label="Max Tokens",
                        required=False,
                        default=1024,
                        min=128,
                        max=4096,
                        step=128,
                        description="Maximum number of tokens to generate",
                    ),
                    FieldSchema(
                        name="generation_use_gpu",
                        type="boolean",
                        label="Use GPU",
                        required=False,
                        default=False,
                        description="Whether to use GPU for generation",
                    ),
                ],
            ),
            SectionSchema(
                name="storage",
                label="Storage Configuration",
                fields=[
                    FieldSchema(
                        name="storage_working_directory",
                        type="text",
                        label="Working Directory",
                        required=False,
                        description="Directory to store LEGRA data (auto-generated if empty)",
                    )
                ],
            ),
        ],
    ),
    # "lightrag": TypeSchema(
    #     name="LightRAG",
    #     description="Use only LightRAG for graph-based retrieval with LLM completion",
    #     sections=[
    #         SectionSchema(
    #             name="core",
    #             label="Core Configuration",
    #             fields=[
    #                 FieldSchema(
    #                     name="working_directory",
    #                     type="text",
    #                     label="Working Directory",
    #                     required=False,
    #                     default="lightrag_data",
    #                     description="Directory to store LightRAG data",
    #                 ),
    #                 FieldSchema(
    #                     name="search_mode",
    #                     type="select",
    #                     label="Search Mode",
    #                     required=True,
    #                     default="mix",
    #                     options=[
    #                         {"value": "local", "label": "Local Search"},
    #                         {"value": "global", "label": "Global Search"},
    #                         {"value": "mix", "label": "Mixed Search"},
    #                     ],
    #                     description="Search strategy for LightRAG",
    #                 ),
    #             ],
    #         ),
    #         SectionSchema(
    #             name="functions",
    #             label="Function Configuration",
    #             fields=[
    #                 FieldSchema(
    #                     name="embedding_func_name",
    #                     type="select",
    #                     label="Embedding Function",
    #                     required=True,
    #                     default="openai_embed",
    #                     options=[
    #                         {"value": "openai_embed", "label": "OpenAI Embeddings"}
    #                     ],
    #                     description="Embedding function for LightRAG",
    #                 ),
    #                 FieldSchema(
    #                     name="llm_model_func_name",
    #                     type="select",
    #                     label="LLM Model Function",
    #                     required=True,
    #                     default="gpt_4o_mini_complete",
    #                     options=[
    #                         {"value": "gpt_4o_mini_complete", "label": "GPT-4o Mini"}
    #                     ],
    #                     description="LLM model function for completion",
    #                 ),
    #             ],
    #         ),
    #         SectionSchema(
    #             name="chunking",
    #             label="Chunking Configuration",
    #             fields=[
    #                 FieldSchema(
    #                     name="chunk_token_size",
    #                     type="number",
    #                     label="Chunk Token Size",
    #                     required=True,
    #                     default=512,
    #                     min=128,
    #                     max=2048,
    #                     step=32,
    #                     description="Size of chunks in tokens",
    #                 ),
    #                 FieldSchema(
    #                     name="chunk_overlap_token_size",
    #                     type="number",
    #                     label="Chunk Overlap Token Size",
    #                     required=True,
    #                     default=50,
    #                     min=0,
    #                     max=200,
    #                     step=10,
    #                     description="Overlap between chunks in tokens",
    #                 ),
    #             ],
    #         ),
    #         SectionSchema(
    #             name="vector_storage",
    #             label="Vector Storage Configuration",
    #             fields=[
    #                 FieldSchema(
    #                     name="vector_storage",
    #                     type="select",
    #                     label="Vector Storage Type",
    #                     required=False,
    #                     default="ChromaVectorDBStorage",
    #                     options=[
    #                         {
    #                             "value": "ChromaVectorDBStorage",
    #                             "label": "ChromaDB Storage",
    #                         }
    #                     ],
    #                     description="Vector storage backend for LightRAG",
    #                 ),
    #                 FieldSchema(
    #                     name="embedding_batch_num",
    #                     type="number",
    #                     label="Embedding Batch Number",
    #                     required=False,
    #                     default=32,
    #                     min=1,
    #                     max=128,
    #                     step=1,
    #                     description="Number of embeddings to process in a batch",
    #                 ),
    #             ],
    #         ),
    #         SectionSchema(
    #             name="query",
    #             label="Query Configuration",
    #             fields=[
    #                 FieldSchema(
    #                     name="top_k",
    #                     type="number",
    #                     label="Top K Results",
    #                     required=False,
    #                     default=5,
    #                     min=1,
    #                     max=20,
    #                     step=1,
    #                     description="Maximum number of results to return",
    #                 ),
    #                 FieldSchema(
    #                     name="response_type",
    #                     type="text",
    #                     label="Response Type",
    #                     required=False,
    #                     default="Single Paragraph",
    #                     description="Format for query responses",
    #                 ),
    #             ],
    #         ),
    #     ],
    # ),
}

# For backwards compatibility, alias to the main schema (includes all types: vector, legra, lightrag)
AGENT_RAG_FORM_SCHEMAS = AGENT_RAG_FORM_SCHEMAS_VECTOR_AND_LEGRA

AGENT_RAG_FORM_SCHEMAS_DICT = convert_typed_schemas_to_dict(AGENT_RAG_FORM_SCHEMAS)
