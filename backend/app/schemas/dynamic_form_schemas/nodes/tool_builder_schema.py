from typing import List
from ..base import FieldSchema

TOOL_BUILDER_NODE_DIALOG_SCHEMA: List[FieldSchema] = [
    FieldSchema(
        name="name",
        type="text",
        label="Node Name",
        required=False
    ),
    FieldSchema(
        name="description",
        type="text",
        label="Description",
        required=True
    ),
    FieldSchema(
        name="forwardTemplate",
        type="boolean",
        label="Return data directly as agent output",
        required=True
    )
]
