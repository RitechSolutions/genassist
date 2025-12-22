from typing import List
from ..base import FieldSchema

OPEN_API_NODE_DIALOG_SCHEMA: List[FieldSchema] = [
    FieldSchema(
        name="name",
        type="text",
        label="Node Name",
        required=False
    ),
    FieldSchema(
        name="providerId",
        type="select",
        label="LLM Provider",
        required=True
    ),
    FieldSchema(
        name="originalFileName",
        type="text",
        label="Specification File",
        required=True
    ),
    FieldSchema(
        name="query",
        type="text",
        label="Query",
        required=True
    )
]
