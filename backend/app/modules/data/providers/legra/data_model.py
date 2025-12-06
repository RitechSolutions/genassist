from typing import Any, Dict, List

from pydantic import BaseModel, Field


class Identified(BaseModel):
    """
    A base object for identified items.
    """
    model_config = {
        'arbitrary_types_allowed': True,
        'extra': 'forbid',
        'validate_default': True,
        'validate_assignment': True,
        'validate_return': True,
    }

    idx: str  # Item ID


class Named(Identified):
    """
    A base class for named objects.
    """
    name: str  # The name of the item


class Document(Named):
    """
    A protocol for documents.
    """

    doc_type: str = "text"  # The document type
    text: str = ""   # The raw text content

    # Additional attributes associated with the document
    attributes: Dict[str, Any] = Field(default_factory=dict)


class Relationship(Identified):
    """
    A base relationship class.
    """
    source: str  # source entity name
    target: str  # target entity name
    weight: float = 1.0  # weight of the relationship

    description: str | None = None  # A description for the relationship
    # Semantic embedding of the relationship description
    description_embedding: List[float] | None = None

    # Additional attributes associated with the relationship
    attributes: Dict[str, Any] = Field(default_factory=dict)
