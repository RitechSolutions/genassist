from typing import List

from ..base import FieldSchema

FILTER_NODE_DIALOG_SCHEMA: List[FieldSchema] = [
    FieldSchema(
        name="name",
        type="text",
        label="Node Name",
        required=False,
    ),
    FieldSchema(
        name="field",
        type="text",
        label="Field",
        required=True,
        description="The value to check, usually a variable from an upstream node.",
    ),
    FieldSchema(
        name="operator",
        type="select",
        label="Operator",
        required=False,
        default="equal",
        options=[
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
        ],
    ),
    # Not required: "Is empty" / "Is not empty" take no value. The engine treats a
    # missing value as a false condition for every operator that needs one.
    FieldSchema(
        name="value",
        type="text",
        label="Value",
        required=False,
        description="What the field is compared with (unused by Is empty / Is not empty).",
    ),
    FieldSchema(
        name="caseSensitive",
        type="boolean",
        label="Case sensitive",
        required=False,
        default=False,
    ),
    FieldSchema(
        name="stopMessage",
        type="text",
        label="Message when stopped",
        required=False,
        description="Optional chat reply used when the filter stops the conversation's main path.",
    ),
]
