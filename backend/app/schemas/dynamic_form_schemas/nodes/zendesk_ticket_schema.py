from typing import List
from ..base import FieldSchema

ZENDESK_TICKET_NODE_DIALOG_SCHEMA: List[FieldSchema] = [
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
        name="requester_name",
        type="text",
        label="Requester Name",
        required=True
    ),
    FieldSchema(
        name="requester_email",
        type="text",
        label="Requester Email",
        required=True
    ),
    FieldSchema(
        name="tags",
        type="tags",
        label="Tags",
        required=False
    )
]
