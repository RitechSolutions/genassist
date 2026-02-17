from typing import List

from ..base import ConditionalField, FieldSchema

SQL_NODE_DIALOG_SCHEMA: List[FieldSchema] = [
    FieldSchema(name="name", type="text", label="Node Name", required=False),
    FieldSchema(name="dataSourceId", type="select", label="Data Source", required=True),
    FieldSchema(
        name="mode",
        type="select",
        label="Mode",
        required=True,
        options=[
            {"label": "Write SQL Manually", "value": "sqlQuery"},
            {"label": "Generate SQL from Text", "value": "humanQuery"},
        ],
    ),
    FieldSchema(
        name="sqlQuery",
        type="text",
        label="SQL Query",
        required=True,
        conditional=ConditionalField(field="mode", value="sqlQuery"),
    ),
    FieldSchema(
        name="providerId",
        type="select",
        label="LLM Provider",
        required=True,
        conditional=ConditionalField(field="mode", value="humanQuery"),
    ),
    FieldSchema(
        name="systemPrompt",
        type="text",
        label="System Prompt",
        required=False,
        conditional=ConditionalField(field="mode", value="humanQuery"),
    ),
    FieldSchema(
        name="humanQuery",
        type="text",
        label="Query in Plain English",
        required=True,
        conditional=ConditionalField(field="mode", value="humanQuery"),
    ),
]
