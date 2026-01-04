from typing import List
from ..base import FieldSchema

SQL_NODE_DIALOG_SCHEMA: List[FieldSchema] = [
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
        name="dataSourceId",
        type="select",
        label="Data Source",
        required=True
    ),
    FieldSchema(
        name="systemPrompt",
        type="text",
        label="System Prompt",
        required=False
    ),
    FieldSchema(
        name="query",
        type="text",
        label="Human Query",
        required=True
    )
]
