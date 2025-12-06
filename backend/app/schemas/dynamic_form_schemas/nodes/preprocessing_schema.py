from typing import List
from ..base import FieldSchema

PREPROCESSING_NODE_DIALOG_SCHEMA: List[FieldSchema] = [
    FieldSchema(
        name="name",
        type="text",
        label="Node Name",
        required=False
    ),
    FieldSchema(
        name="fileUrl",
        type="text",
        label="File URL",
        required=True
    ),
    FieldSchema(
        name="pythonCode",
        type="text",
        label="Python Code",
        required=False
    )
]
