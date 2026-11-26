from typing import List

from app.constants import DEFAULT_NLI_MODEL, FORM_OPTIONS_NLI

from ..base import ConditionalField, FieldSchema

GUARDRAIL_NLI_NODE_DIALOG_SCHEMA: List[FieldSchema] = [
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
        name="evidence_field",
        type="text",
        label="Evidence",
        required=True,
        description="The text the answer must agree with.",
    ),
    FieldSchema(
        name="nli_model_name",
        type="select",
        label="NLI model",
        required=False,
        default=DEFAULT_NLI_MODEL,
        options=FORM_OPTIONS_NLI,
    ),
    FieldSchema(
        name="min_entail_score",
        type="number",
        label="Minimum entailment score (0-1)",
        required=False,
        default=0.5,
        min=0,
        max=1,
        step=0.01,
    ),
    FieldSchema(
        name="fail_on_contradiction",
        type="boolean",
        label="Fail on contradiction",
        required=False,
        default=False,
    ),
    FieldSchema(
        name="fallback_answer_enabled",
        type="boolean",
        label="Fallback answer on contradiction",
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
