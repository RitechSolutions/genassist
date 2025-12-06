from typing import List
from ..base import FieldSchema

DATA_MAPPER_NODE_DIALOG_SCHEMA: List[FieldSchema] = [
    FieldSchema(
        name="name",
        type="text",
        label="Node Name",
        required=False
    ),
    FieldSchema(
        name="pythonScript",
        type="text",
        label="Python Script",
        required=True
    )
]
