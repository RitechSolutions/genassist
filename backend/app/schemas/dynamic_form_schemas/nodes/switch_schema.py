from typing import List

from ..base import ConditionalField, FieldSchema

# The per-branch `cases` list ([{id, label, value}]) is edited in the node's own
# dialog; it has no field here because FieldSchema has no list type.
SWITCH_NODE_DIALOG_SCHEMA: List[FieldSchema] = [
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
        name="switchValue",
        type="text",
        label="Value",
        required=True,
        description="The single value compared against every case.",
        conditional=ConditionalField(field="smartModeEnabled", value=False),
    ),
    FieldSchema(
        name="matchMode",
        type="select",
        label="Match Mode",
        required=False,
        default="equal",
        options=[
            {"label": "Equals", "value": "equal"},
            {"label": "Contains", "value": "contains"},
            {"label": "Starts with", "value": "starts_with"},
            {"label": "Ends with", "value": "ends_with"},
            {"label": "Matches regex", "value": "regex"},
        ],
        conditional=ConditionalField(field="smartModeEnabled", value=False),
    ),
    FieldSchema(
        name="caseSensitive",
        type="boolean",
        label="Case sensitive",
        required=False,
        default=False,
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
]
