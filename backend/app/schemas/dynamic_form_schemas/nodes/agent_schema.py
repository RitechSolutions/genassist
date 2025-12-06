from typing import List
from ..base import FieldSchema

AGENT_NODE_DIALOG_SCHEMA: List[FieldSchema] = [
    FieldSchema(
        name="name",
        type="text",
        label="Node Name",
        required=False
    ),
    FieldSchema(
        name="providerId",
        type="select",
        label="LLM Provider",
        required=True
    ),
    FieldSchema(
        name="systemPrompt",
        type="text",
        label="System Prompt",
        required=True
    ),
    FieldSchema(
        name="userPrompt",
        type="text",
        label="User Prompt",
        required=True
    ),
    FieldSchema(
        name="type",
        type="select",
        label="Agent Type",
        required=True
    ),
    FieldSchema(
        name="maxIterations",
        type="number",
        label="Max Iterations",
        required=True
    ),
    FieldSchema(
        name="memory",
        type="boolean",
        label="Enable Memory",
        required=True
    ),
]
