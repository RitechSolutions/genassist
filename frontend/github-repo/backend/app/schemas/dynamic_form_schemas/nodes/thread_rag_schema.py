from typing import List
from ..base import FieldSchema

THREAD_RAG_NODE_DIALOG_SCHEMA: List[FieldSchema] = [
    FieldSchema(
        name="name",
        type="text",
        label="Node Name",
        required=False
    ),
    FieldSchema(
        name="action",
        type="select",
        label="Action",
        required=True
    ),
    FieldSchema(
        name="query",
        type="text",
        label="Query",
        required=False
    ),
    FieldSchema(
        name="top_k",
        type="number",
        label="Top K",
        required=False
    ),
    FieldSchema(
        name="message",
        type="text",
        label="Message",
        required=False
    )
]
