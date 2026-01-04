from typing import List
from ..base import FieldSchema

AGGREGATOR_NODE_DIALOG_SCHEMA: List[FieldSchema] = [
    FieldSchema(
        name="name",
        type="text",
        label="Node Name",
        required=False
    ),
    FieldSchema(
        name="aggregationStrategy",
        type="select",
        label="Aggregation Strategy",
        required=True
    ),
    FieldSchema(
        name="timeoutSeconds",
        type="number",
        label="Timeout (seconds)",
        required=True
    ),
    FieldSchema(
        name="forwardTemplate",
        type="text",
        label="Forward Template",
        required=False
    )
]
