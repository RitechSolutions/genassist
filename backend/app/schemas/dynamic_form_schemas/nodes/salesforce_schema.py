from typing import List

from ..base import FieldSchema

# SalesForce Case node config. Only ``subject``, ``description`` and
# ``app_settings_id`` are required. ``labels`` are assigned to the created Case as
# SalesForce Topics; further Case fields go via the dynamic ``custom_fields`` editor.
SALESFORCE_CASE_NODE_DIALOG_SCHEMA: List[FieldSchema] = [
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
        name="subject",
        type="text",
        label="Subject",
        required=True
    ),
    FieldSchema(
        name="description",
        type="text",
        label="Description",
        required=True
    ),
    FieldSchema(
        name="labels",
        type="tags",
        label="Labels",
        required=False
    ),
]
