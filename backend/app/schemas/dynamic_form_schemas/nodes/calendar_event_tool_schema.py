from typing import List
from ..base import FieldSchema

CALENDAR_EVENT_TOOL_NODE_DIALOG_SCHEMA: List[FieldSchema] = [
    FieldSchema(
        name="name",
        type="text",
        label="Node Name",
        required=False
    ),
    FieldSchema(
        name="dataSourceId",
        type="select",
        label="Connector",
        required=True
    ),
    FieldSchema(
        name="summary",
        type="text",
        label="Summary",
        required=True
    ),
    FieldSchema(
        name="operation",
        type="select",
        label="Operation",
        required=True
    ),
    FieldSchema(
        name="start",
        type="text",
        label="Start Time",
        required=False
    ),
    FieldSchema(
        name="end",
        type="text",
        label="End Time",
        required=False
    ),
    FieldSchema(
        name="subjectContains",
        type="text",
        label="Subject Contains",
        required=False
    )
]
