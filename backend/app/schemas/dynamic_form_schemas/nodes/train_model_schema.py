from typing import List
from ..base import FieldSchema

TRAIN_MODEL_NODE_DIALOG_SCHEMA: List[FieldSchema] = [
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
        name="modelType",
        type="select",
        label="Model Type",
        required=True
    ),
    FieldSchema(
        name="targetColumn",
        type="text",
        label="Target Column",
        required=True
    ),
    FieldSchema(
        name="featureColumns",
        type="tags",
        label="Feature Columns",
        required=True
    ),
    FieldSchema(
        name="validationSplit",
        type="number",
        label="Validation Split",
        required=True
    )
]
