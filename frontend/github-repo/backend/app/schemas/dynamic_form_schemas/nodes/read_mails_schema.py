from typing import List
from ..base import FieldSchema

READ_MAILS_NODE_DIALOG_SCHEMA: List[FieldSchema] = [
    FieldSchema(
        name="name",
        type="text",
        label="Node Name",
        required=False
    ),
    FieldSchema(
        name="dataSourceId",
        type="select",
        label="Gmail Data Source",
        required=True
    ),
    FieldSchema(
        name="searchCriteria.from",
        type="text",
        label="From Email",
        required=False
    ),
    FieldSchema(
        name="searchCriteria.to",
        type="text",
        label="To Email",
        required=False
    ),
    FieldSchema(
        name="searchCriteria.subject",
        type="text",
        label="Subject Contains",
        required=False
    ),
    FieldSchema(
        name="searchCriteria.label",
        type="select",
        label="Gmail Label",
        required=False
    ),
    FieldSchema(
        name="searchCriteria.newer_than",
        type="select",
        label="Newer Than",
        required=False
    ),
    FieldSchema(
        name="searchCriteria.older_than",
        type="select",
        label="Older Than",
        required=False
    ),
    FieldSchema(
        name="searchCriteria.max_results",
        type="number",
        label="Max Results",
        required=False
    ),
    FieldSchema(
        name="searchCriteria.has_attachment",
        type="boolean",
        label="Has Attachment",
        required=False
    ),
    FieldSchema(
        name="searchCriteria.is_unread",
        type="boolean",
        label="Unread Only",
        required=False
    ),
    FieldSchema(
        name="searchCriteria.custom_query",
        type="text",
        label="Custom Gmail Query",
        required=False
    )
]
