"""Registration tests for SalesforceToolNode ("Salesforce Case").

Asserts the node type is wired end-to-end: resolvable in the engine registry and
present in the dialog / handler / label schema maps (FR-1, FR-2, FR-6, FR-7, FR-8).
"""

from app.modules.workflow.engine.nodes.salesforce_tool_node import SalesforceToolNode
from app.modules.workflow.engine.workflow_engine import WorkflowEngine
from app.schemas.dynamic_form_schemas.nodes import (
    NODE_DIALOG_SCHEMAS,
    NODE_HANDLERS_SCHEMAS,
    NODE_TYPE_LABELS,
)

_NODE_TYPE = "salesforceCaseNode"


def test_node_type_resolves_to_class_in_engine_registry():
    """FR-7: engine registry maps the type to SalesforceToolNode after init."""
    WorkflowEngine._initialize_node_registry()
    assert WorkflowEngine._node_registry.get(_NODE_TYPE) is SalesforceToolNode


def test_node_type_present_in_dialog_schema():
    """FR-2: dialog schema is registered (builder can render the config dialog)."""
    assert _NODE_TYPE in NODE_DIALOG_SCHEMAS


def test_dialog_schema_contains_required_case_fields():
    """FR-2/FR-6: dialog exposes subject, description and app_settings_id fields."""
    schema = NODE_DIALOG_SCHEMAS[_NODE_TYPE]
    field_names = {field.name for field in schema}
    assert {"subject", "description", "app_settings_id"} <= field_names


def test_only_subject_description_app_settings_are_required():
    """FR-9: only subject/description/app_settings_id are required; labels are optional."""
    schema = {field.name: field for field in NODE_DIALOG_SCHEMAS[_NODE_TYPE]}
    assert schema["subject"].required is True
    assert schema["description"].required is True
    assert schema["app_settings_id"].required is True
    assert schema["labels"].required is False


def test_node_type_present_in_handlers_with_input_and_output():
    """FR-8: handler schema declares both an input (target) and output (source) handler."""
    assert _NODE_TYPE in NODE_HANDLERS_SCHEMAS
    handlers = NODE_HANDLERS_SCHEMAS[_NODE_TYPE]
    types = {h["type"] for h in handlers}
    assert "target" in types
    assert "source" in types


def test_node_type_label_registered():
    """FR-1: human label is registered for the node-type endpoint / log enrichment."""
    assert NODE_TYPE_LABELS.get(_NODE_TYPE) == "Salesforce Case"
