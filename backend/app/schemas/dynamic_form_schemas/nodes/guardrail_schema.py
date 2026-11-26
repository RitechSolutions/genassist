from typing import List

from ..base import FieldSchema

GUARDRAIL_NODE_DIALOG_SCHEMA: List[FieldSchema] = [
    FieldSchema(
        name="name",
        type="text",
        label="Node Name",
        required=False,
    ),
    FieldSchema(
        name="text",
        type="text",
        label="Text to check",
        required=True,
        description="The text to check, usually a variable such as {{session.message}}.",
    ),
    FieldSchema(
        name="providerId",
        type="select",
        label="Judge model",
        required=False,
        description="Needed for prompt attack, harmful content and topic checks.",
    ),
    FieldSchema(
        name="prompt_attack",
        type="select",
        label="Prompt attacks",
        required=False,
        default="off",
        options=[
            {"label": "Off", "value": "off"},
            {"label": "Low", "value": "low"},
            {"label": "Medium", "value": "medium"},
            {"label": "High", "value": "high"},
        ],
    ),
    FieldSchema(
        name="blocked_words",
        type="tags",
        label="Blocked words",
        required=False,
    ),
    FieldSchema(
        name="blocked_message",
        type="text",
        label="Blocked message",
        required=False,
        description="Sent on the Blocked exit.",
    ),
]
