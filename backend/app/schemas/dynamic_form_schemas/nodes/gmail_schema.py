from typing import List
from ..base import FieldSchema

GMAIL_NODE_DIALOG_SCHEMA: List[FieldSchema] = [
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
        name="operation",
        type="select",
        label="Operation",
        required=True
    ),
    FieldSchema(
        name="to",
        type="text",
        label="To",
        required=True
    ),
    FieldSchema(
        name="cc",
        type="text",
        label="CC",
        required=False
    ),
    FieldSchema(
        name="bcc",
        type="text",
        label="BCC",
        required=False
    ),
    FieldSchema(
        name="subject",
        type="text",
        label="Subject",
        required=True
    ),
    FieldSchema(
        name="body",
        type="text",
        label="Body",
        required=True
    )
]
