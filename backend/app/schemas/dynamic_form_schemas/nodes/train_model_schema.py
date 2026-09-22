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
        name="scalingMethod",
        type="select",
        label="Feature Scaling",
        required=False,
        default="auto",
        options=[
            {"label": "None", "value": "none"},
            {"label": "Standardized (Z-score)", "value": "standard"},
            {"label": "Min-Max", "value": "minmax"},
            {"label": "Abs-Max", "value": "maxabs"},
            {"label": "Robust", "value": "robust"},
            {"label": "Auto (Recommended)", "value": "auto"},
        ]
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
