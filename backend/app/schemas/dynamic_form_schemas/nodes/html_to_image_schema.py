from typing import List

from ..base import ConditionalField, FieldSchema

HTML_TO_IMAGE_NODE_DIALOG_SCHEMA: List[FieldSchema] = [
    FieldSchema(
        name="name",
        type="text",
        label="Node Name",
        required=False,
    ),
    FieldSchema(
        name="html",
        type="text",
        label="HTML",
        required=True,
    ),
    FieldSchema(
        name="captureMode",
        type="select",
        label="Capture Mode",
        default="fullPage",
        options=[
            {"label": "Full Page", "value": "fullPage"},
            {"label": "Viewport", "value": "viewport"},
        ],
    ),
    FieldSchema(
        name="viewportWidth",
        type="number",
        label="Viewport Width",
        default=1280,
        min=1,
    ),
    FieldSchema(
        name="viewportHeight",
        type="number",
        label="Viewport Height",
        default=720,
        min=1,
        advanced=True,
        conditional=ConditionalField(field="captureMode", value="viewport"),
    ),
    FieldSchema(
        name="waitFor",
        type="number",
        label="Wait For (ms)",
        default=0,
        min=0,
        advanced=True,
    ),
]
