"""Registration tests for FilterNode ("Filter")."""

from app.api.v1.routes.workflows import SUPPORTED_NODE_TYPES
from app.modules.workflow.engine.conditions import OPERATORS
from app.modules.workflow.engine.nodes.filter_node import FilterNode
from app.modules.workflow.engine.workflow_engine import WorkflowEngine
from app.schemas.dynamic_form_schemas.nodes import (
    NODE_DIALOG_SCHEMAS,
    NODE_HANDLERS_SCHEMAS,
    NODE_TYPE_LABELS,
)

_NODE_TYPE = "filterNode"


def test_node_type_resolves_to_class_in_engine_registry():
    WorkflowEngine._initialize_node_registry()
    assert WorkflowEngine._node_registry.get(_NODE_TYPE) is FilterNode


def test_node_type_is_supported_by_the_api():
    assert _NODE_TYPE in SUPPORTED_NODE_TYPES


def test_dialog_schema_fields_and_operators():
    schema = {field.name: field for field in NODE_DIALOG_SCHEMAS[_NODE_TYPE]}
    assert {"name", "field", "operator", "value", "caseSensitive", "stopMessage"} <= set(schema)
    assert schema["field"].required is True
    # Is empty / Is not empty take no value, so the value is not required.
    assert schema["value"].required is False
    assert schema["operator"].default == "equal"
    assert [o["value"] for o in schema["operator"].options] == list(OPERATORS)


def test_handlers_declare_one_input_and_one_output():
    assert [(h["id"], h["type"]) for h in NODE_HANDLERS_SCHEMAS[_NODE_TYPE]] == [("input", "target"), ("output", "source")]


def test_node_type_label_registered():
    assert NODE_TYPE_LABELS.get(_NODE_TYPE) == "Filter"


def test_node_reported_as_not_needing_db_access():
    engine = WorkflowEngine.__new__(WorkflowEngine)
    assert engine._node_needs_db_access(_NODE_TYPE) is False
