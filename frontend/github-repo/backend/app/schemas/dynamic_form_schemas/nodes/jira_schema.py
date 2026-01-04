from typing import List
from ..base import FieldSchema

JIRA_NODE_DIALOG_SCHEMA: List[FieldSchema] = [
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
        name="spaceKey",
        type="text",
        label="Space Key",
        required=True
    ),
    FieldSchema(
        name="taskName",
        type="text",
        label="Task Name",
        required=True
    ),
    FieldSchema(
        name="taskDescription",
        type="text",
        label="Task Description",
        required=False
    )
]
