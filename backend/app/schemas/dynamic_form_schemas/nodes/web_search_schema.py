from typing import List

from ..base import FieldSchema

WEB_SEARCH_NODE_DIALOG_SCHEMA: List[FieldSchema] = [
    FieldSchema(
        name="name",
        type="text",
        label="Node Name",
        required=False,
    ),
    FieldSchema(
        name="query",
        type="text",
        label="Query",
        required=True,
    ),
    FieldSchema(
        name="maxResults",
        type="number",
        label="Max Results",
        default=5,
        min=1,
        max=20,
    ),
    FieldSchema(
        name="searchDepth",
        type="select",
        label="Search Depth",
        default="basic",
        options=[
            {"label": "Basic", "value": "basic"},
            {"label": "Advanced", "value": "advanced"},
        ],
    ),
    FieldSchema(
        name="includeDomains",
        type="text",
        label="Include Domain",
        required=False,
        advanced=True,
    ),
    FieldSchema(
        name="excludeDomains",
        type="text",
        label="Exclude Domains",
        required=False,
        advanced=True,
    ),
    # per-result content cap for advanced depth
    FieldSchema(
        name="maxContentChars",
        type="number",
        label="Max Content Chars (per result)",
        default=2000,
        min=200,
        max=4000,
        advanced=True,
    ),
    # total enrichment budget for advanced depth; bounds worst-case payload
    FieldSchema(
        name="maxTotalContentChars",
        type="number",
        label="Max Total Content Chars",
        default=8000,
        min=1000,
        max=16000,
        advanced=True,
    ),
    # default-on result cache; 0 disables. Tenant-scoped, capped at 7d server-side
    FieldSchema(
        name="maxAge",
        type="number",
        label="Cache Max Age (seconds)",
        default=600,
        min=0,
        advanced=True,
    ),
]
