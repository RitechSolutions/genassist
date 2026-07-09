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
        name="onlyMainContent",
        type="boolean",
        label="Only Main Content",
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
    # render-timing controls
    FieldSchema(
        name="waitFor",
        type="number",
        label="Wait For (ms)",
        default=0,
        min=0,
        advanced=True,
    ),
    FieldSchema(
        name="waitUntil",
        type="select",
        label="Wait Until",
        default="domcontentloaded",
        options=[
            {"label": "DOM Content Loaded", "value": "domcontentloaded"},
            {"label": "Load", "value": "load"},
            {"label": "Network Idle", "value": "networkidle"},
            {"label": "Commit", "value": "commit"},
        ],
        advanced=True,
    ),
    FieldSchema(
        name="scrollToBottom",
        type="boolean",
        label="Scroll To Bottom",
        default=False,
        advanced=True,
    ),
    # opt-in result cache; 0 disables. Tenant-scoped, capped at 7d server-side
    FieldSchema(
        name="maxAge",
        type="number",
        label="Cache Max Age (seconds)",
        default=0,
        min=0,
        advanced=True,
    ),
]
