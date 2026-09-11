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
        required=True,
        default="http://loclahost/api/endpoint"
    ),
    FieldSchema(
        name="method",
        type="select",
        label="HTTP Method",
        required=True,
        default="GET"
    ),
    FieldSchema(
        name="requestBody",
        type="textarea",
        size="code",
        label="Request Body (JSON)",
        required=False
    )
]
