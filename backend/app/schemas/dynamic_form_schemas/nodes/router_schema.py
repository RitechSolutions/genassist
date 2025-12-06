from typing import List
from ..base import FieldSchema

ROUTER_NODE_DIALOG_SCHEMA: List[FieldSchema] = [
    FieldSchema(
        name="name",
        type="text",
        label="Node Name",
        required=False
    ),
    FieldSchema(
        name="first_value",
        type="text",
        label="First Value",
        required=True
    ),
    FieldSchema(
        name="compare_condition",
        type="select",
        label="Compare Condition",
        required=True
    ),
    FieldSchema(
        name="second_value",
        type="text",
        label="Second Value",
        required=True
    )
]
