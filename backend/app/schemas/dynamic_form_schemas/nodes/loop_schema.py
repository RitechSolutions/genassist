from typing import List

from ..base import ConditionalField, FieldSchema

_STOP_OPERATORS = [
    {"label": "Equals", "value": "equal"},
    {"label": "Does not equal", "value": "not_equal"},
    {"label": "Contains", "value": "contains"},
    {"label": "Does not contain", "value": "not_contain"},
    {"label": "Starts with", "value": "starts_with"},
    {"label": "Does not start with", "value": "not_starts_with"},
    {"label": "Ends with", "value": "ends_with"},
    {"label": "Does not end with", "value": "not_ends_with"},
    {"label": "Matches regex", "value": "regex"},
    {"label": "Greater than", "value": "greater_than"},
    {"label": "Greater than or equal", "value": "greater_than_or_equal"},
    {"label": "Less than", "value": "less_than"},
    {"label": "Less than or equal", "value": "less_than_or_equal"},
    {"label": "Is empty", "value": "is_empty"},
    {"label": "Is not empty", "value": "is_not_empty"},
]

LOOP_NODE_DIALOG_SCHEMA: List[FieldSchema] = [
    FieldSchema(
        name="name",
        type="text",
        label="Node Name",
        required=False,
    ),
    FieldSchema(
        name="mode",
        type="select",
        label="Mode",
        required=False,
        default="forEach",
        options=[
            {"label": "For each item", "value": "forEach"},
            {"label": "Repeat until", "value": "repeatUntil"},
        ],
    ),
    # Only used by "For each item"; "Repeat until" has no list.
    FieldSchema(
        name="items",
        type="text",
        label="Items",
        required=True,
        conditional=ConditionalField(field="mode", value="forEach"),
        description="The list to go through, usually a variable from an upstream node. A number repeats that many times; plain text is split on lines or commas.",
    ),
    FieldSchema(
        name="batchSize",
        type="number",
        label="Batch size",
        required=False,
        default=1,
        min=1,
        conditional=ConditionalField(field="mode", value="forEach"),
        description="Items per pass. With more than one, the body receives a list in {{source.item}}.",
    ),
    FieldSchema(
        name="maxIterations",
        type="number",
        label="Maximum iterations",
        required=False,
        default=100,
        min=1,
        description="The loop never runs more passes than this, whatever the list size or stop condition.",
    ),
    # The stop condition is optional for "For each item" (an early exit) and is
    # the exit of "Repeat until". It is resolved after every pass, so it can read
    # the body's outputs ({{node_outputs.<id>...}}).
    FieldSchema(
        name="stopField",
        type="text",
        label="Stop when",
        required=False,
        description="The value to check after each pass, usually an output of a node inside the loop.",
    ),
    FieldSchema(
        name="stopOperator",
        type="select",
        label="Operator",
        required=False,
        default="equal",
        options=_STOP_OPERATORS,
    ),
    FieldSchema(
        name="stopValue",
        type="text",
        label="Value",
        required=False,
        description="What the value is compared with (unused by Is empty / Is not empty).",
    ),
    FieldSchema(
        name="stopCaseSensitive",
        type="boolean",
        label="Case sensitive",
        required=False,
        default=False,
    ),
    FieldSchema(
        name="onError",
        type="select",
        label="When a pass fails",
        required=False,
        default="stop",
        options=[
            {"label": "Stop the loop", "value": "stop"},
            {"label": "Continue with the next pass", "value": "continue"},
        ],
    ),
    FieldSchema(
        name="delaySeconds",
        type="number",
        label="Wait between passes (seconds)",
        required=False,
        default=0,
        min=0,
        max=60,
    ),
    FieldSchema(
        name="delayBackoff",
        type="boolean",
        label="Double the wait after every pass",
        required=False,
        default=False,
    ),
    FieldSchema(
        name="timeLimitSeconds",
        type="number",
        label="Time limit (seconds)",
        required=False,
        default=0,
        min=0,
        description="No new pass starts once the loop has run this long. 0 means no limit.",
    ),
    FieldSchema(
        name="collect",
        type="select",
        label="Results to keep",
        required=False,
        default="all",
        options=[
            {"label": "Every pass", "value": "all"},
            {"label": "Only the last pass", "value": "last"},
            {"label": "None", "value": "none"},
        ],
    ),
]
