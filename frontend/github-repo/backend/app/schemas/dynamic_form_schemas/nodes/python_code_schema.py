from typing import List
from ..base import FieldSchema

PYTHON_CODE_NODE_DIALOG_SCHEMA: List[FieldSchema] = [
    FieldSchema(
        name="name",
        type="text",
        label="Node Name",
        required=False
    ),
    FieldSchema(
        name="code",
        type="text",
        label="Python Code",
        required=True
    )
]
