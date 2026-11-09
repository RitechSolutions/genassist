from typing import List

from ..base import FieldSchema

# SalesForce Case node config. Only ``subject``, ``description`` and
# ``app_settings_id`` are required. ``web_email``/``web_name``/``web_phone`` fill the Case's
# SuppliedEmail/SuppliedName/SuppliedPhone. ``labels`` are assigned to the created Case as
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
        name="web_email",
        type="text",
        label="Web Email",
        required=False
    ),
    FieldSchema(
        name="web_name",
        type="text",
        label="Web Name",
        required=False
    ),
    FieldSchema(
        name="web_phone",
        type="text",
        label="Web Phone",
        required=False
    ),
    FieldSchema(
        name="labels",
        type="tags",
        label="Labels",
        required=False
    ),
]
