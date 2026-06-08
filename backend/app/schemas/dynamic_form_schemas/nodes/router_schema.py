from typing import List

from ..base import ConditionalField, FieldSchema

ROUTER_NODE_DIALOG_SCHEMA: List[FieldSchema] = [
    FieldSchema(
        name="name",
        type="text",
        label="Node Name",
        required=False,
    ),
    FieldSchema(
        name="smartModeEnabled",
        type="boolean",
        label="Smart Mode (LLM routing)",
        required=False,
        default=False,
    ),
    FieldSchema(
        name="first_value",
        type="text",
        label="First Value",
        required=True,
        conditional=ConditionalField(field="smartModeEnabled", value=False),
    ),
    FieldSchema(
        name="compare_condition",
        type="select",
        label="Compare Condition",
        required=True,
        default="contains",
        conditional=ConditionalField(field="smartModeEnabled", value=False),
    ),
    FieldSchema(
        name="second_value",
        type="text",
        label="Second Value",
        required=True,
        conditional=ConditionalField(field="smartModeEnabled", value=False),
    ),
    FieldSchema(
        name="providerId",
        type="select",
        label="LLM Provider",
        required=True,
        conditional=ConditionalField(field="smartModeEnabled", value=True),
    ),
    FieldSchema(
        name="smartPrompt",
        type="text",
        label="Routing prompt",
        required=True,
        conditional=ConditionalField(field="smartModeEnabled", value=True),
    ),
    FieldSchema(
        name="systemPrompt",
        type="text",
        label="System Prompt",
        required=False,
        conditional=ConditionalField(field="smartModeEnabled", value=True),
    ),
    FieldSchema(
        name="fallbackRoute",
        type="select",
        label="Fallback route",
        required=False,
        default="false",
        options=[
            {"label": "false", "value": "false"},
            {"label": "true", "value": "true"},
        ],
        conditional=ConditionalField(field="smartModeEnabled", value=True),
    ),
]
