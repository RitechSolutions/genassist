from typing import List
from ..base import FieldSchema

WEB_SCRAPER_NODE_DIALOG_SCHEMA: List[FieldSchema] = [
    FieldSchema(
        name="name",
        type="text",
        label="Node Name",
        required=False
    ),
    FieldSchema(
        name="url",
        type="text",
        label="URL",
        required=True,
        default="https://"
    ),
    FieldSchema(
        name="format",
        type="select",
        label="Output Format",
        required=True,
        default="markdown",
        options=[
            {"label": "Markdown", "value": "markdown"},
            {"label": "HTML", "value": "html"},
            {"label": "Both", "value": "both"},
        ]
    ),
    FieldSchema(
        name="renderJs",
        type="boolean",
        label="Render JavaScript",
        default=False
    )
]
