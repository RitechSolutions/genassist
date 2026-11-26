from typing import List

from ..base import ConditionalField, FieldSchema

GUARDRAIL_PROVENANCE_NODE_DIALOG_SCHEMA: List[FieldSchema] = [
    FieldSchema(
        name="name",
        type="text",
        label="Node Name",
        required=False,
    ),
    FieldSchema(
        name="answer_field",
        type="text",
        label="Answer",
        required=True,
        description="The answer to check, usually a variable from an upstream node.",
    ),
    FieldSchema(
        name="context_field",
        type="text",
        label="Context",
        required=True,
        description="The sources the answer must be supported by.",
    ),
    FieldSchema(
        name="min_score",
        type="number",
        label="Minimum provenance score (0-1)",
        required=False,
        default=0.5,
        min=0,
        max=1,
        step=0.01,
    ),
    FieldSchema(
        name="provenance_mode",
        type="select",
        label="Provenance mode",
        required=False,
        default="embeddings",
        options=[
            {"label": "Provenance (Embeddings)", "value": "embeddings"},
            {"label": "Provenance (LLM judge)", "value": "llm"},
        ],
    ),
    FieldSchema(
        name="llm_provider_id",
        type="select",
        label="LLM Provider",
        required=False,
        conditional=ConditionalField(field="provenance_mode", value="llm"),
    ),
    FieldSchema(
        name="llm_judge_system_prompt_suffix",
        type="textarea",
        label="Additional judge instructions",
        required=False,
        conditional=ConditionalField(field="provenance_mode", value="llm"),
    ),
    FieldSchema(
        name="fail_on_violation",
        type="boolean",
        label="Fail on violation",
        required=False,
        default=False,
    ),
    FieldSchema(
        name="fallback_answer_enabled",
        type="boolean",
        label="Fallback answer on violation",
        required=False,
        default=False,
    ),
    FieldSchema(
        name="fallback_answer",
        type="text",
        label="Fallback answer text",
        required=False,
        conditional=ConditionalField(field="fallback_answer_enabled", value=True),
    ),
]
