"""Registration tests for FinalizeConversationNode ("End Conversation").

Asserts the node type is wired end-to-end: resolvable in the engine registry and
present in the dialog / handler / label schema maps (AC-3, AC-8).
"""

from app.modules.workflow.engine.nodes.finalize_conversation_node import FinalizeConversationNode
from app.modules.workflow.engine.workflow_engine import WorkflowEngine
from app.schemas.dynamic_form_schemas.nodes import (
    NODE_DIALOG_SCHEMAS,
    NODE_HANDLERS_SCHEMAS,
    NODE_TYPE_LABELS,
)

_NODE_TYPE = "finalizeConversationNode"


def test_node_type_resolves_to_class_in_engine_registry():
    """FR-3: engine registry maps the type to FinalizeConversationNode after init."""
    WorkflowEngine._initialize_node_registry()
    assert WorkflowEngine._node_registry.get(_NODE_TYPE) is FinalizeConversationNode


def test_node_type_present_in_dialog_schema():
    """FR-3: dialog schema is registered (builder can render the config dialog)."""
    assert _NODE_TYPE in NODE_DIALOG_SCHEMAS


def test_node_type_present_in_handlers_with_input_and_output():
    """FR-3/FR-7: handler schema declares both an input (target) and output (source) handler."""
    assert _NODE_TYPE in NODE_HANDLERS_SCHEMAS
    handlers = NODE_HANDLERS_SCHEMAS[_NODE_TYPE]
    types = {h["type"] for h in handlers}
    assert "target" in types
    assert "source" in types


def test_node_type_label_registered():
    """FR-1: human label is registered for the node-type endpoint / log enrichment."""
    assert NODE_TYPE_LABELS.get(_NODE_TYPE) == "End Conversation"


def test_node_not_in_no_db_deny_list():
    """The node needs DB access (it finalizes a conversation), so it must not be
    in the engine's no-DB deny-list (deny-list semantics in _node_needs_db_access)."""
    engine = WorkflowEngine.__new__(WorkflowEngine)
    assert engine._node_needs_db_access(_NODE_TYPE) is True
