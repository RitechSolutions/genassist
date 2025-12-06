from typing import List
from ..base import FieldSchema

ML_MODEL_INFERENCE_NODE_DIALOG_SCHEMA: List[FieldSchema] = [
    FieldSchema(
        name="name",
        type="text",
        label="Node Name",
        required=False
    ),
    FieldSchema(
        name="modelId",
        type="select",
        label="ML Model",
        required=True
    ),
    FieldSchema(
        name="modelName",
        type="text",
        label="Model Name",
        required=True
    )
]
