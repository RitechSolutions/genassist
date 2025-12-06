from typing import List
from ..base import FieldSchema

SLACK_OUTPUT_NODE_DIALOG_SCHEMA: List[FieldSchema] = [
    FieldSchema(
        name="name",
        type="text",
        label="Node Name",
        required=False
    ),
    FieldSchema(
        name="app_settings_id",
        type="select",
        label="Configuration Vars",
        required=True
    ),
    FieldSchema(
        name="channel",
        type="text",
        label="Channel ID",
        required=True
    ),
    FieldSchema(
        name="message",
        type="text",
        label="Message",
        required=True
    )
]
