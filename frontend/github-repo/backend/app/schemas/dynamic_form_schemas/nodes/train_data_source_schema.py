from typing import List
from ..base import FieldSchema

TRAIN_DATA_SOURCE_NODE_DIALOG_SCHEMA: List[FieldSchema] = [
    FieldSchema(
        name="name",
        type="text",
        label="Node Name",
        required=False
    ),
    FieldSchema(
        name="sourceType",
        type="select",
        label="Source Type",
        required=True
    ),
    FieldSchema(
        name="dataSourceType",
        type="select",
        label="Data Source Type",
        required=False
    ),
    FieldSchema(
        name="dataSourceId",
        type="text",
        label="Data Source",
        required=False
    ),
    FieldSchema(
        name="query",
        type="text",
        label="Query",
        required=False
    ),
    FieldSchema(
        name="csvFile",
        type="text",
        label="CSV File",
        required=False
    )
]
