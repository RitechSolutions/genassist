from typing import List
from ..base import FieldSchema

TEMPLATE_NODE_DIALOG_SCHEMA: List[FieldSchema] = [
    FieldSchema(
        name="name",
        type="text",
        label="Node Name",
        required=False
    ),
    FieldSchema(
        name="template",
        type="text",
        label="Template",
        required=True
    )
]
