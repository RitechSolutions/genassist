"""Registration tests for HtmlToImageNode ("HTML to Image").

Asserts the node type is wired end-to-end: resolvable in the engine registry,
present in the dialog / handler / label schema maps, and reported as needing DB
access (image hosting reads app settings from the DB).
"""

from app.modules.workflow.engine.nodes.html_to_image_node import HtmlToImageNode
from app.modules.workflow.engine.workflow_engine import WorkflowEngine
from app.schemas.dynamic_form_schemas.nodes import (
    NODE_DIALOG_SCHEMAS,
    NODE_HANDLERS_SCHEMAS,
    NODE_TYPE_LABELS,
)

_NODE_TYPE = "htmlToImageNode"


def test_node_type_resolves_to_class_in_engine_registry():
    """Engine registry maps the type to HtmlToImageNode after init."""
    WorkflowEngine._initialize_node_registry()
    assert WorkflowEngine._node_registry.get(_NODE_TYPE) is HtmlToImageNode


def test_node_type_present_in_dialog_schema():
    """Dialog schema is registered (builder can render the config dialog)."""
    assert _NODE_TYPE in NODE_DIALOG_SCHEMAS


def test_dialog_schema_contains_required_fields():
    """Dialog exposes the HTML-to-image fields; only html is required."""
    schema = {field.name: field for field in NODE_DIALOG_SCHEMAS[_NODE_TYPE]}
    assert {
        "html",
        "captureMode",
        "viewportWidth",
        "viewportHeight",
        "waitFor",
    } <= set(schema)
    assert schema["html"].required is True
    assert schema["captureMode"].default == "fullPage"


def test_node_type_present_in_handlers_with_input_and_output():
    """Handler schema declares both an input (target) and output (source) handler."""
    assert _NODE_TYPE in NODE_HANDLERS_SCHEMAS
    types = {h["type"] for h in NODE_HANDLERS_SCHEMAS[_NODE_TYPE]}
    assert "target" in types
    assert "source" in types


def test_node_type_label_registered():
    """Human label is registered for the node-type endpoint / log enrichment."""
    assert NODE_TYPE_LABELS.get(_NODE_TYPE) == "HTML to Image"


def test_node_reported_as_needing_db_access():
    engine = WorkflowEngine.__new__(WorkflowEngine)
    assert engine._node_needs_db_access(_NODE_TYPE) is True
