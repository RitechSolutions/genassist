"""
Dynamic form schemas module.

This module contains all dynamic form schemas used across the application:
- APP_SETTINGS_SCHEMAS: App settings integration schemas
- DATA_SOURCE_SCHEMAS: Data source connection schemas
- LLM_FORM_SCHEMAS: LLM provider configuration schemas
- AGENT_RAG_FORM_SCHEMAS: Agent RAG configuration schemas

All schemas follow the unified structure defined in base.py
"""

from .base import (
    FieldSchema,
    SectionSchema,
    TypeSchema,
    ConditionalField,
    FieldType,
    convert_dict_to_type_schema,
    convert_schemas_dict_to_typed,
    convert_typed_schemas_to_dict,
)

from .app_settings_schemas import (
    APP_SETTINGS_SCHEMAS,
    APP_SETTINGS_SCHEMAS_DICT,
    get_schema_for_type,
    get_all_schemas,
    get_encrypted_fields_for_type,
)

from .data_source_schemas import DATA_SOURCE_SCHEMAS, DATA_SOURCE_SCHEMAS_DICT
from .llm_form_schemas import LLM_FORM_SCHEMAS, LLM_FORM_SCHEMAS_DICT
from .agent_rag_form_schemas import AGENT_RAG_FORM_SCHEMAS, AGENT_RAG_FORM_SCHEMAS_DICT

__all__ = [
    # Base classes
    "FieldSchema",
    "SectionSchema",
    "TypeSchema",
    "ConditionalField",
    "FieldType",
    # Conversion utilities
    "convert_dict_to_type_schema",
    "convert_schemas_dict_to_typed",
    "convert_typed_schemas_to_dict",
    # Schemas
    "APP_SETTINGS_SCHEMAS",
    "APP_SETTINGS_SCHEMAS_DICT",
    "DATA_SOURCE_SCHEMAS",
    "DATA_SOURCE_SCHEMAS_DICT",
    "LLM_FORM_SCHEMAS",
    "LLM_FORM_SCHEMAS_DICT",
    "AGENT_RAG_FORM_SCHEMAS",
    "AGENT_RAG_FORM_SCHEMAS_DICT",
    # Helper functions
    "get_schema_for_type",
    "get_all_schemas",
    "get_encrypted_fields_for_type",
]
