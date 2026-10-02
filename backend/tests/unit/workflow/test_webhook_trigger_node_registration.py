"""Registration tests for WebhookTriggerNode ("Webhook Trigger").

Asserts the node type is wired end-to-end: resolvable in the engine registry,
accepted by the workflow API, present in the dialog / handler / label schema
maps, treated as an entry node, and reported as not needing DB access.
"""

from app.api.v1.routes.workflows import SUPPORTED_NODE_TYPES
from app.modules.workflow.engine.entry_nodes import ENTRY_NODE_TYPES, is_entry_node_type
from app.modules.workflow.engine.nodes.webhook_trigger_node import WebhookTriggerNode
from app.modules.workflow.engine.workflow_engine import WorkflowEngine
from app.schemas.dynamic_form_schemas.nodes import (
    NODE_DIALOG_SCHEMAS,
    NODE_HANDLERS_SCHEMAS,
    NODE_TYPE_LABELS,
)

_NODE_TYPE = "webhookTriggerNode"


def test_node_type_resolves_to_class_in_engine_registry():
    WorkflowEngine._initialize_node_registry()
    assert WorkflowEngine._node_registry.get(_NODE_TYPE) is WebhookTriggerNode


def test_node_type_is_supported_by_the_api():
    assert _NODE_TYPE in SUPPORTED_NODE_TYPES


def test_dialog_schema_exposes_mapping_fields_none_required():
    schema = {field.name: field for field in NODE_DIALOG_SCHEMAS[_NODE_TYPE]}
    assert {"name", "messagePath", "threadIdPath", "idempotencyPath", "samplePayload"} <= set(schema)
    # A trigger works with zero configuration: the raw delivery is always available.
    assert not any(field.required for field in schema.values())


def test_handlers_declare_only_an_output():
    handlers = NODE_HANDLERS_SCHEMAS[_NODE_TYPE]
    assert [h["id"] for h in handlers] == ["output"]
    assert handlers[0]["type"] == "source"


def test_node_type_label_registered():
    assert NODE_TYPE_LABELS.get(_NODE_TYPE) == "Webhook Trigger"


def test_node_is_an_entry_node_like_chat_input():
    assert is_entry_node_type(_NODE_TYPE)
    assert is_entry_node_type("chatInputNode")
    assert {"chatInputNode", _NODE_TYPE} <= set(ENTRY_NODE_TYPES)
    assert not is_entry_node_type("agentNode")


def test_node_reported_as_not_needing_db_access():
    engine = WorkflowEngine.__new__(WorkflowEngine)
    assert engine._node_needs_db_access(_NODE_TYPE) is False
