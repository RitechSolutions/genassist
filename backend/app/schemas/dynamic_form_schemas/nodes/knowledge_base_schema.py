from typing import List
from ..base import FieldSchema

KNOWLEDGE_BASE_NODE_DIALOG_SCHEMA: List[FieldSchema] = [
    FieldSchema(
        name="name",
        type="text",
        label="Node Name",
        required=False
    ),
    FieldSchema(
        name="query",
        type="text",
        label="Query",
        required=True
    ),
    FieldSchema(
        name="limit",
        type="number",
        label="Limit",
        required=True
    ),
    FieldSchema(
        name="force",
        type="boolean",
        label="Force Limit",
        required=True
    ),
    FieldSchema(
        name="selectedBases",
        type="tags",
        label="Knowledge Bases",
        required=True
    )
]
