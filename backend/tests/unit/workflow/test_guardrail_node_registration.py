"""Registration tests for the Guardrail, NLI and Provenance nodes."""

import pytest

from app.api.v1.routes.workflows import SUPPORTED_NODE_TYPES
from app.modules.workflow.engine.nodes import GuardrailNliNode, GuardrailNode, GuardrailProvenanceNode
from app.modules.workflow.engine.workflow_engine import WorkflowEngine
from app.schemas.dynamic_form_schemas.nodes import (
    NODE_DIALOG_SCHEMAS,
    NODE_HANDLERS_SCHEMAS,
    NODE_TYPE_LABELS,
)

NODES = [
    ("guardrailNode", GuardrailNode, "Guardrail"),
    ("guardrailNliNode", GuardrailNliNode, "Guardrail: NLI Fact-check"),
    ("guardrailProvenanceNode", GuardrailProvenanceNode, "Guardrail: Provenance"),
]


@pytest.mark.parametrize(("node_type", "cls", "label"), NODES)
def test_node_is_registered_everywhere(node_type, cls, label):
    WorkflowEngine._initialize_node_registry()
    assert WorkflowEngine._node_registry.get(node_type) is cls
    assert node_type in SUPPORTED_NODE_TYPES
    assert node_type in NODE_DIALOG_SCHEMAS
    assert NODE_TYPE_LABELS.get(node_type) == label


@pytest.mark.parametrize("node_type", [n for n, _, _ in NODES])
def test_handlers_declare_a_passed_and_a_blocked_exit(node_type):
    assert [(h["id"], h["type"]) for h in NODE_HANDLERS_SCHEMAS[node_type]] == [
        ("input", "target"),
        ("output", "source"),
        ("output_blocked", "source"),
    ]


def test_guardrail_dialog_requires_the_text_only():
    schema = {field.name: field for field in NODE_DIALOG_SCHEMAS["guardrailNode"]}
    assert {"name", "text", "providerId", "prompt_attack", "blocked_words", "blocked_message"} <= set(schema)
    assert [name for name, field in schema.items() if field.required] == ["text"]
