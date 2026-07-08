from typing import List

from ..base import FieldSchema

WEB_SCRAPER_NODE_DIALOG_SCHEMA: List[FieldSchema] = [
    FieldSchema(
        name="name",
        type="text",
        label="Node Name",
        required=False,
    ),
    FieldSchema(
        name="url",
        type="text",
        label="URL",
        required=True,
        default="https://",
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
        ],
    ),
    FieldSchema(
        name="renderJs",
        type="boolean",
        label="Render JavaScript",
        default=False,
    ),
    FieldSchema(
        name="onlyMainContent",
        type="boolean",
        label="Only Main Content",
        default=True,
    ),
    FieldSchema(
        name="includeLinks",
        type="boolean",
        label="Include Links",
        default=True,
    ),
    FieldSchema(
        name="includeMetadata",
        type="boolean",
        label="Include Metadata",
        default=True,
    ),
    FieldSchema(
        name="screenshot",
        type="select",
        label="Screenshot",
        default="off",
        options=[
            {"label": "Off", "value": "off"},
            {"label": "Viewport", "value": "viewport"},
            {"label": "Full Page", "value": "fullPage"},
        ],
    ),
    # FieldType has no key-value type; headers are modeled loosely as a JSON-object text field
    FieldSchema(
        name="headers",
        type="text",
        label="Headers (JSON object)",
        required=False,
    ),
]
