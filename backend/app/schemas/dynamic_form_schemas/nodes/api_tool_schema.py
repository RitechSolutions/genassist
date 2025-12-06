from typing import List
from ..base import FieldSchema

API_TOOL_NODE_DIALOG_SCHEMA: List[FieldSchema] = [
    FieldSchema(
        name="name",
        type="text",
        label="Node Name",
        required=False
    ),
    FieldSchema(
        name="endpoint",
        type="text",
        label="Endpoint URL",
        required=True
    ),
    FieldSchema(
        name="method",
        type="select",
        label="HTTP Method",
        required=True
    ),
    FieldSchema(
        name="requestBody",
        type="text",
        label="Request Body (JSON)",
        required=False
    )
]
