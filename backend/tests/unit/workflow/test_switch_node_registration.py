"""Registration tests for SwitchNode ("Switch").

Asserts the node type is wired end-to-end: resolvable in the engine registry,
accepted by the workflow API, present in the dialog / handler / label schema maps,
and reported as not needing DB access (it only compares strings).
"""

from app.api.v1.routes.workflows import SUPPORTED_NODE_TYPES
from app.modules.workflow.engine.nodes.switch_node import SwitchNode
from app.modules.workflow.engine.workflow_engine import WorkflowEngine
from app.schemas.dynamic_form_schemas.nodes import (
    NODE_DIALOG_SCHEMAS,
    NODE_HANDLERS_SCHEMAS,
    NODE_TYPE_LABELS,
)

_NODE_TYPE = "switchNode"


def test_node_type_resolves_to_class_in_engine_registry():
    WorkflowEngine._initialize_node_registry()
    assert WorkflowEngine._node_registry.get(_NODE_TYPE) is SwitchNode


def test_node_type_is_supported_by_the_api():
    assert _NODE_TYPE in SUPPORTED_NODE_TYPES


def test_dialog_schema_requires_the_fields_of_the_active_mode():
    schema = {field.name: field for field in NODE_DIALOG_SCHEMAS[_NODE_TYPE]}
    assert {
        "name",
        "smartModeEnabled",
        "switchValue",
        "matchMode",
        "caseSensitive",
        "providerId",
        "smartPrompt",
        "systemPrompt",
    } <= set(schema)
    assert schema["smartModeEnabled"].default is False
    assert schema["matchMode"].default == "equal"
    assert schema["caseSensitive"].default is False
    # Rule mode needs a value; Smart Mode needs a provider and a prompt instead.
    assert schema["switchValue"].required is True
    assert schema["switchValue"].conditional.value is False
    for field in ("providerId", "smartPrompt"):
        assert schema[field].required is True
        assert schema[field].conditional.value is True


def test_handlers_declare_input_and_default_output():
    handler_ids = {h["id"] for h in NODE_HANDLERS_SCHEMAS[_NODE_TYPE]}
    assert handler_ids == {"input", "output_default"}


def test_node_type_label_registered():
    assert NODE_TYPE_LABELS.get(_NODE_TYPE) == "Switch"


def test_node_reported_as_not_needing_db_access():
    engine = WorkflowEngine.__new__(WorkflowEngine)
    assert engine._node_needs_db_access(_NODE_TYPE) is False
