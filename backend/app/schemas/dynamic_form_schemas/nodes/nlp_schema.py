from typing import List

from ..base import ConditionalField, FieldSchema

NLP_NODE_DIALOG_SCHEMA: List[FieldSchema] = [
    FieldSchema(
        name="name",
        type="text",
        label="Node Name",
        required=False,
    ),
    FieldSchema(
        name="providerId",
        type="select",
        label="LLM Provider",
        required=True,
    ),
    FieldSchema(
        name="inputField",
        type="text",
        label="Input",
        required=False,
        default="{{source.message}}",
        placeholder="Text to analyze",
    ),
    FieldSchema(
        name="task",
        type="select",
        label="Task",
        required=True,
        default="classify",
        options=[
            {"label": "Classify", "value": "classify"},
            {"label": "Sentiment & Urgency", "value": "sentiment"},
            {"label": "Extract Entities", "value": "extract"},
            {"label": "Summarize", "value": "summarize"},
        ],
    ),
    # --- classify ---
    FieldSchema(
        name="categories",
        type="tags",
        label="Categories",
        required=True,
        description="Labels the input can be classified into",
        conditional=ConditionalField(field="task", value="classify"),
    ),
    FieldSchema(
        name="multiLabel",
        type="boolean",
        label="Allow Multiple Labels",
        required=False,
        default=False,
        conditional=ConditionalField(field="task", value="classify"),
    ),
    # --- sentiment ---
    FieldSchema(
        name="scale",
        type="select",
        label="Score Scale",
        required=False,
        default="1-5",
        options=[
            {"label": "1-5", "value": "1-5"},
            {"label": "1-10", "value": "1-10"},
        ],
        conditional=ConditionalField(field="task", value="sentiment"),
    ),
    # --- extract ---
    FieldSchema(
        name="schema",
        type="text",
        label="Fields to Extract",
        required=True,
        placeholder="order_number, email, plan",
        description="Comma-separated field names or a JSON description of the fields to extract",
        conditional=ConditionalField(field="task", value="extract"),
    ),
    # --- summarize ---
    FieldSchema(
        name="maxLength",
        type="number",
        label="Max Words",
        required=False,
        default=200,
        min=10,
        step=10,
        description="Approximate maximum length of the summary in words",
        conditional=ConditionalField(field="task", value="summarize"),
    ),
    FieldSchema(
        name="style",
        type="select",
        label="Style",
        required=False,
        default="concise",
        options=[
            {"label": "Concise", "value": "concise"},
            {"label": "Bullets", "value": "bullets"},
            {"label": "Detailed", "value": "detailed"},
        ],
        conditional=ConditionalField(field="task", value="summarize"),
    ),
]
