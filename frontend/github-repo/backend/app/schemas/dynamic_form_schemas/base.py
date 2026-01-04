"""
Unified schema definitions for dynamic field schemas.

This module provides a unified structure for all dynamic field schemas
to ensure consistency and maintainability.
"""
from typing import List, Dict, Any, Optional, Literal, Union
from pydantic import BaseModel, Field


# Field types supported across all schemas
FieldType = Literal[
    "text", "number", "password", "select", "boolean", "tags"
]


class ConditionalField(BaseModel):
    """Conditional field definition for showing/hiding fields based on other field values."""
    field: str = Field(..., description="Field name to check")
    value: Union[str, int, bool] = Field(..., description="Value to match")


class FieldSchema(BaseModel):
    """Unified field schema definition for all dynamic schemas."""
    name: str = Field(..., description="Field name/identifier")
    type: FieldType = Field(..., description="Field type")
    label: str = Field(..., description="Display label for the field")
    required: bool = Field(default=False, description="Whether field is required")
    description: Optional[str] = Field(default=None, description="Field description")
    placeholder: Optional[str] = Field(default=None, description="Placeholder text")
    default: Optional[Union[str, int, float, bool]] = Field(default=None, description="Default value")

    # For select fields
    options: Optional[List[Dict[str, str]]] = Field(default=None, description="Options for select fields")

    # For number fields
    min: Optional[Union[int, float]] = Field(default=None, description="Minimum value for number fields")
    max: Optional[Union[int, float]] = Field(default=None, description="Maximum value for number fields")
    step: Optional[Union[int, float]] = Field(default=None, description="Step value for number fields")

    # For conditional fields (DATA_SOURCE style)
    conditional: Optional[ConditionalField] = Field(default=None, description="Conditional field logic")

    # For encryption (APP_SETTINGS style)
    encrypted: bool = Field(default=False, description="Whether field should be encrypted")

    # For advanced fields (DATA_SOURCE style)
    advanced: Optional[bool] = Field(default=None, description="Whether field is advanced/optional to show")

    class Config:
        extra = "allow"  # Allow extra fields for backwards compatibility


class SectionSchema(BaseModel):
    """Section schema for grouping fields."""
    name: str = Field(..., description="Section name/identifier")
    label: str = Field(..., description="Display label for the section")
    fields: List[FieldSchema] = Field(default_factory=list, description="Fields in this section")
    conditional_fields: Optional[Dict[str, List[FieldSchema]]] = Field(
        default=None,
        description="Conditional fields based on field values (e.g., {'recursive': [FieldSchema, ...]})"
    )

    class Config:
        extra = "allow"

    def model_dump(self, **kwargs) -> Dict[str, Any]:
        """Convert to dictionary format compatible with existing code."""
        # Ignore kwargs for now - we always return the full structure
        _ = kwargs
        result: Dict[str, Any] = {
            "name": self.name,
            "label": self.label,
            "fields": [field.model_dump(exclude_none=True) for field in self.fields]
        }
        if self.conditional_fields is not None:
            result["conditional_fields"] = {
                str(key): [field.model_dump(exclude_none=True) for field in fields_list]
                for key, fields_list in self.conditional_fields.items()  # type: ignore[attr-defined]
            }
        return result


class TypeSchema(BaseModel):
    """Unified type schema definition for all dynamic schemas.

    Supports two patterns:
    1. Flat structure: Direct 'fields' array (DATA_SOURCE, APP_SETTINGS, LLM_FORM)
    2. Sectioned structure: 'sections' array (AGENT_RAG_FORM)
    """
    name: str = Field(..., description="Type name")
    description: Optional[str] = Field(default=None, description="Type description")

    # For flat structure (DATA_SOURCE, APP_SETTINGS, LLM_FORM)
    fields: Optional[List[FieldSchema]] = Field(default=None, description="Direct fields array")

    # For sectioned structure (AGENT_RAG_FORM)
    sections: Optional[List[SectionSchema]] = Field(default=None, description="Sections with fields")

    class Config:
        extra = "allow"

    def model_dump_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format compatible with existing code."""
        result: Dict[str, Any] = {
            "name": self.name,
        }

        if self.description:
            result["description"] = self.description

        # If sections exist, use sectioned structure (only add if not None)
        if self.sections is not None:
            result["sections"] = [section.model_dump() for section in self.sections]  # type: ignore[arg-type]
        # If fields exist and no sections, use flat structure
        elif self.fields is not None:
            result["fields"] = [field.model_dump(exclude_none=True) for field in self.fields]  # type: ignore[arg-type]

        return result


def convert_dict_to_type_schema(data: Dict[str, Any]) -> TypeSchema:
    """Convert a dictionary schema to TypeSchema.

    This helper function allows backwards compatibility by converting
    existing dict-based schemas to TypeSchema objects.
    """
    # Check if it's a sectioned structure
    if "sections" in data:
        sections = []
        for section_dict in data["sections"]:
            conditional_fields = None
            if "conditional_fields" in section_dict:
                conditional_fields = {
                    key: [FieldSchema(**field_dict) for field_dict in fields_list]
                    for key, fields_list in section_dict["conditional_fields"].items()
                }

            sections.append(SectionSchema(
                name=section_dict["name"],
                label=section_dict["label"],
                fields=[FieldSchema(**field_dict) for field_dict in section_dict.get("fields", [])],
                conditional_fields=conditional_fields
            ))

        return TypeSchema(
            name=data["name"],
            description=data.get("description"),
            sections=sections,
            fields=None  # type: ignore[arg-type]
        )

    # Flat structure
    else:
        fields = []
        for field_dict in data.get("fields", []):
            # Handle conditional field
            conditional = None
            if "conditional" in field_dict:
                cond_data = field_dict["conditional"]
                conditional = ConditionalField(
                    field=cond_data["field"],
                    value=cond_data["value"]
                )

            fields.append(FieldSchema(
                **{k: v for k, v in field_dict.items() if k != "conditional"},
                conditional=conditional
            ))

        return TypeSchema(
            name=data["name"],
            description=data.get("description"),
            fields=fields,
            sections=None  # type: ignore[arg-type]
        )


def convert_schemas_dict_to_typed(schemas_dict: Dict[str, Dict[str, Any]]) -> Dict[str, TypeSchema]:
    """Convert a dictionary of schemas to typed TypeSchema dictionary."""
    return {
        key: convert_dict_to_type_schema(value)
        for key, value in schemas_dict.items()
    }


def convert_typed_schemas_to_dict(schemas_dict: Dict[str, TypeSchema]) -> Dict[str, Dict[str, Any]]:
    """Convert typed TypeSchema dictionary back to plain dictionaries for API responses."""
    return {
        key: schema.model_dump_dict()
        for key, schema in schemas_dict.items()
    }
